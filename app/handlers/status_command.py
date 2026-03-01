from webex_bot.models.command import Command
from app.clients.jenkins_api import fetch_job_status
from app.services.jenkins.credentials_service import read_credentials, get_job_credentials
from app.services.jenkins.catalog_service import load_catalog, resolve_jobs
from app.cards.job_card import build_job_card
from webexteamssdk import WebexTeamsAPI
from app.core.settings import get_webex_settings
from app.core.paths import JOB_CONFIG_PATH, GROUPS_CONFIG_PATH
from app.core.messages import build_unknown_job_help_text
from app.core.command_utils import normalize_command_text, build_scoped_jenkins_message
import time
import datetime

FALLBACK_CREDENTIALS_PATH = "app/services/jenkins/config/credentials.ini"

WEBEX_BOT_TOKEN, WEBEX_BOT_PERSON_ID = get_webex_settings()

api = WebexTeamsAPI(access_token=WEBEX_BOT_TOKEN)

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
        text = normalize_command_text(message)
        config_urls, config_groups = load_catalog(JOB_CONFIG_PATH, GROUPS_CONFIG_PATH)
        matched_jobs = resolve_jobs(text, config_urls, config_groups)

        if not matched_jobs:
            help_text = build_unknown_job_help_text(text if text else message)
            api.messages.create(roomId=room_id, text=help_text)
            return

        for job in matched_jobs:
            # Get credentials for this specific job
            try:
                username, token = get_job_credentials(job["name"], JOB_CONFIG_PATH, FALLBACK_CREDENTIALS_PATH)
            except Exception as e:
                # Fallback to default credentials if job-specific credentials fail
                try:
                    username, token = read_credentials(FALLBACK_CREDENTIALS_PATH, "default")
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
        jenkins_cmd.execute(build_scoped_jenkins_message(message, "usm"), teams_message, activity)
    
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
        jenkins_cmd.execute(build_scoped_jenkins_message(message, "ims"), teams_message, activity)
    
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
        jenkins_cmd.execute(build_scoped_jenkins_message(message, "asa"), teams_message, activity)

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
        jenkins_cmd.execute(build_scoped_jenkins_message(message, "fxos"), teams_message, activity)

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
