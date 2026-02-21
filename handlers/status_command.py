from webex_bot.models.command import Command
from config import WEBEX_BOT_PERSON_ID, WEBEX_BOT_TOKEN
from jenkins.jenkins_fetcher import read_credentials, fetch_job_status, get_job_credentials
from cards.job_card import build_job_card
from webexteamssdk import WebexTeamsAPI
import configparser
import time
import datetime

api = WebexTeamsAPI(access_token=WEBEX_BOT_TOKEN)


def _build_scoped_jenkins_message(message, scope_keyword):
    """Keep scoped command input when present; fall back to group view when empty."""
    raw = (message or "").strip()
    scope = scope_keyword.lower()
    lowered = raw.lower()
    known_prefixes = ("usm_", "ims_", "asa_", "fxos_", "lina_", "bazel_")

    if not raw or lowered == scope:
        return f"jenkins {scope_keyword}"

    # Some command parsers strip only the matched keyword and leave a leading
    # underscore suffix (for example: "ims_10_0_main" -> "_10_0_main").
    if raw.startswith("_"):
        return f"jenkins {scope}{raw}"

    # If a scoped command receives a bare suffix like "10_0_main", rebuild
    # the alias as "<scope>_10_0_main".
    if " " not in raw and "_" in raw and not lowered.startswith(known_prefixes):
        return f"jenkins {scope}_{raw.lstrip('_')}"

    if lowered.startswith(f"{scope} "):
        suffix = raw[len(scope_keyword):].strip()
        return f"jenkins {suffix}" if suffix else f"jenkins {scope_keyword}"

    return f"jenkins {raw}"

class JenkinsStatusCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="jenkins",
            help_message="",
            card=None,
        )
        self.match_substring = True

    def execute(self, message, teams_message, activity):
        if activity.get("personId") == WEBEX_BOT_PERSON_ID:
            return

        room_id = teams_message.roomId
        # Clean the input text - remove bot mentions and common prefixes
        text = message.strip().lower()
        text = text.replace("datadigger", "").replace("bot", "").replace("jenkins", "").strip()
        
        # If text is empty after cleaning, show all jobs
        if not text:
            text = ""

        config_urls = configparser.ConfigParser()
        config_urls.read("jenkins/job_config.ini")

        config_groups = configparser.ConfigParser()
        config_groups.read("jenkins/groups.ini")

        matched_jobs = []

        if not text:
            # No input, show all grouped jobs
            for section in config_groups.sections():
                job_names = [j.strip() for j in config_groups[section]["jobs"].split(",")]
                for name in job_names:
                    matched_jobs.append({
                        "name": name,
                        "url": config_urls["URLS"].get(name),
                        "display_name": config_urls[name].get("display_name", name) if name in config_urls else name,
                    })
        elif text.upper() in config_groups:
            # Match a group
            job_names = [j.strip() for j in config_groups[text.upper()]["jobs"].split(",")]
            for name in job_names:
                matched_jobs.append({
                    "name": name,
                    "url": config_urls["URLS"].get(name),
                    "display_name": config_urls[name].get("display_name", name) if name in config_urls else name,
                })
        else:
            # Match individual job by fuzzy key or alias
            for section in config_urls.sections():
                if section == "URLS":
                    continue
                job_name = section
                aliases = config_urls[section].get("alias", "").lower().split(",")
                all_keywords = [job_name.lower()] + [a.strip() for a in aliases if a.strip()]
                
                # Strict matching: only exact job name or alias matches are valid.
                for keyword in all_keywords:
                    if text == keyword:
                        url = config_urls["URLS"].get(job_name)
                        if url:
                            matched_jobs.append({
                                "name": job_name,
                                "url": url,
                                "display_name": config_urls[job_name].get("display_name", job_name),
                            })
                            break  # Avoid duplicate matches for same job

        if not matched_jobs:
            # Create a helpful error message with available options
            help_text = f"❌ No job found for `{text if text else message}`.\n\n"
            help_text += "**Available commands:**\n"
            help_text += "• `@bot jenkins` - Show all jobs\n"
            help_text += "• `@bot usm` - Show USM jobs\n"
            help_text += "• `@bot ims` - Show IMS jobs\n"
            help_text += "• `@bot asa` - Show ASA jobs\n"
            help_text += "• `@bot fxos` - Show FXOS jobs\n"
            help_text += "• `@bot status` - Show all jobs\n\n"
            help_text += "**Individual jobs (use aliases):**\n"
            help_text += "• `usm_10_0_main`, `usm_7.8_main`\n"
            help_text += "Please use the correct keywords."
            
            api.messages.create(roomId=room_id, text=help_text)
            return

        for job in matched_jobs:
            # Get credentials for this specific job
            try:
                username, token = get_job_credentials(job["name"], "jenkins/job_config.ini", "jenkins/credentials.ini")
            except Exception as e:
                # Fallback to default credentials if job-specific credentials fail
                try:
                    username, token = read_credentials("jenkins/credentials.ini", "default")
                except Exception as fallback_error:
                    error_job = {
                        "name": job["name"],
                        "error": f"Credentials config error: {fallback_error}"
                    }
                    card_text = build_job_card(error_job)
                    api.messages.create(roomId=room_id, markdown=card_text)
                    time.sleep(1)
                    continue
            
            job_status = fetch_job_status(job, username, token)

            # Handle error cases
            if "error" in job_status:
                card_text = build_job_card(job_status)
                api.messages.create(roomId=room_id, markdown=card_text)
                time.sleep(1)
                continue

            # Only process successful responses that have required fields
            if "number" not in job_status or "url" not in job_status:
                error_job = {
                    "name": job["name"],
                    "error": "Missing build information from Jenkins API"
                }
                card_text = build_job_card(error_job)
                api.messages.create(roomId=room_id, markdown=card_text)
                time.sleep(1)
                continue

            if "time_obj" in job_status:
                ist_time = job_status["time_obj"] + datetime.timedelta(hours=5, minutes=30)
                job_status["time"] = ist_time.strftime('%I:%M %p')
                job_status["date"] = ist_time.strftime('%Y-%m-%d')
            else:
                job_status["time"] = "N/A"
                job_status["date"] = "N/A"

            job_status["result"] = job_status.get("result") or "RUNNING"
            job_status["link_text"] = f"[{job_status['name']}]({job_status['url']})"

            card_text = build_job_card(job_status)
            api.messages.create(roomId=room_id, markdown=card_text)
            time.sleep(1)

    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)

class USMStatusCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="usm",
            help_message="",
            card=None,
        )
        self.match_substring = True
    
    def execute(self, message, teams_message, activity):
        # Preserve job-specific target like "usm_10_1_main" when provided.
        jenkins_cmd = JenkinsStatusCommand()
        jenkins_cmd.execute(_build_scoped_jenkins_message(message, "usm"), teams_message, activity)
    
    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)

class IMSStatusCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="ims",
            help_message="",
            card=None,
        )
        self.match_substring = True
    
    def execute(self, message, teams_message, activity):
        # Preserve job-specific target like "ims_10_1_main" when provided.
        jenkins_cmd = JenkinsStatusCommand()
        jenkins_cmd.execute(_build_scoped_jenkins_message(message, "ims"), teams_message, activity)
    
    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)

class ASAStatusCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="asa",
            help_message="",
            card=None,
        )
        self.match_substring = True

    def execute(self, message, teams_message, activity):
        # Preserve job-specific target like "apollo_main" when provided.
        jenkins_cmd = JenkinsStatusCommand()
        jenkins_cmd.execute(_build_scoped_jenkins_message(message, "asa"), teams_message, activity)

    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)

class FXOSStatusCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="fxos",
            help_message="",
            card=None,
        )
        self.match_substring = True

    def execute(self, message, teams_message, activity):
        # Preserve job-specific target like "fxos_2_19_main" when provided.
        jenkins_cmd = JenkinsStatusCommand()
        jenkins_cmd.execute(_build_scoped_jenkins_message(message, "fxos"), teams_message, activity)

    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)

class StatusCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="status",
            help_message="",
            card=None,
        )
        self.match_substring = True
    
    def execute(self, message, teams_message, activity):
        # Delegate to the main Jenkins command  
        jenkins_cmd = JenkinsStatusCommand()
        jenkins_cmd.execute(f"jenkins {message}", teams_message, activity)
    
    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)

class CatchAllCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="*",  # Use a wildcard-like character
            help_message=None,  # Set to None instead of empty string
            card=None,
        )
        self.match_substring = True
    
    def pre_execute(self, message, teams_message, activity):
        """Override to completely bypass framework's default card behavior"""
        # Call our execute method directly and return False to stop framework processing
        self.execute(message, teams_message, activity)
        return False  # This prevents the framework from continuing with default behavior
    
    def pre_card_load_reply(self, message, teams_message, activity):
        """Override to prevent any card loading"""
        return ""  # Return empty string to prevent card loading
    
    def execute(self, message, teams_message, activity):
        if activity.get("personId") == WEBEX_BOT_PERSON_ID:
            return

        room_id = teams_message.roomId
        text = message.strip().lower()
        text = text.replace("datadigger", "").replace("bot", "").strip()
        
        # First try to delegate to specific commands
        jenkins_cmd = JenkinsStatusCommand()
        usm_cmd = USMStatusCommand()
        ims_cmd = IMSStatusCommand()
        asa_cmd = ASAStatusCommand()
        fxos_cmd = FXOSStatusCommand()
        status_cmd = StatusCommand()
        
        # Check if it matches any of our specific commands
        if "jenkins" in text:
            jenkins_cmd.execute(message, teams_message, activity)
            return
        elif text.startswith("usm") or "usm" in text:
            usm_cmd.execute(message, teams_message, activity)
            return
        elif text.startswith("ims") or "ims" in text:
            ims_cmd.execute(message, teams_message, activity)
            return
        elif text.startswith("asa") or "asa" in text:
            asa_cmd.execute(message, teams_message, activity)
            return
        elif text.startswith("fxos") or "fxos" in text:
            fxos_cmd.execute(message, teams_message, activity)
            return
        elif text.startswith("status") or text == "":
            status_cmd.execute(message, teams_message, activity)
            return
        else:
            # Send helpful error message for unrecognized commands
            help_text = f"❌ No job found for `{text if text else message}`.\n\n"
            help_text += "Please use the correct keywords."
            
            api.messages.create(roomId=room_id, text=help_text)
    
    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)
