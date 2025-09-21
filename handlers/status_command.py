from webex_bot.models.command import Command
from config import WEBEX_BOT_PERSON_ID, WEBEX_BOT_TOKEN
from jenkins.jenkins_fetcher import read_credentials, fetch_job_status
from cards.job_card import build_job_card
from webexteamssdk import WebexTeamsAPI
import configparser
import time
import datetime

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
        # Clean the input text - remove bot mentions and common prefixes
        text = message.strip().lower()
        text = text.replace("datadigger", "").replace("jenkins", "").strip()
        
        # If text is empty after cleaning, show all jobs
        if not text:
            text = ""

        config_urls = configparser.ConfigParser()
        config_urls.read("jenkins/job_config.ini")

        config_groups = configparser.ConfigParser()
        config_groups.read("jenkins/groups.ini")

        username, token = read_credentials("jenkins/credentials.ini")

        matched_jobs = []

        if not text:
            # No input, show all grouped jobs
            for section in config_groups.sections():
                job_names = [j.strip() for j in config_groups[section]["jobs"].split(",")]
                for name in job_names:
                    matched_jobs.append({"name": name, "url": config_urls["URLS"].get(name)})
        elif text.upper() in config_groups:
            # Match a group
            job_names = [j.strip() for j in config_groups[text.upper()]["jobs"].split(",")]
            for name in job_names:
                matched_jobs.append({"name": name, "url": config_urls["URLS"].get(name)})
        else:
            # Match individual job by fuzzy key or alias
            for section in config_urls.sections():
                if section == "URLS":
                    continue
                job_name = section
                aliases = config_urls[section].get("alias", "").lower().split(",")
                all_keywords = [job_name.lower()] + [a.strip() for a in aliases if a.strip()]
                
                # Check for exact match or substring match
                for keyword in all_keywords:
                    if text == keyword or text in keyword or keyword in text:
                        url = config_urls["URLS"].get(job_name)
                        if url:
                            matched_jobs.append({"name": job_name, "url": url})
                            break  # Avoid duplicate matches for same job

        if not matched_jobs:
            # Create a helpful error message with available options
            help_text = f"❌ No job found for `{text if text else message}`.\n\n"
            help_text += "**Available commands:**\n"
            help_text += "• `@DataDigger jenkins` - Show all jobs\n"
            help_text += "• `@DataDigger usm` - Show USM jobs\n"
            help_text += "• `@DataDigger ims` - Show IMS jobs\n"
            help_text += "• `@DataDigger status` - Show all jobs\n\n"
            help_text += "**Individual jobs (use aliases):**\n"
            help_text += "• `usm7.8`, `usm7.88_mian`, `usm_7.8_main`\n"
            help_text += "• `i10`, `main10` (for IMS 10.0)\n\n"
            help_text += "Please use the correct keywords."
            
            api.messages.create(roomId=room_id, text=help_text)
            return

        for job in matched_jobs:
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
            job_status["link_text"] = f"[{job_status['name']} #{job_status['number']}]({job_status['url']})"

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
        # Delegate to the main Jenkins command
        jenkins_cmd = JenkinsStatusCommand()
        jenkins_cmd.execute(f"jenkins {message}", teams_message, activity)
    
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
        # Delegate to the main Jenkins command
        jenkins_cmd = JenkinsStatusCommand()
        jenkins_cmd.execute(f"jenkins {message}", teams_message, activity)
    
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
        text = text.replace("datadigger", "").strip()
        
        # First try to delegate to specific commands
        jenkins_cmd = JenkinsStatusCommand()
        usm_cmd = USMStatusCommand()
        ims_cmd = IMSStatusCommand()
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
        elif text.startswith("status") or text == "":
            status_cmd.execute(message, teams_message, activity)
            return
        else:
            # Send helpful error message for unrecognized commands
            help_text = f"❌ No job found for `{text if text else message}`.\n\n"
            help_text += "**Available commands:**\n"
            help_text += "• `@DataDigger jenkins` - Show all jobs\n"
            help_text += "• `@DataDigger usm` - Show USM jobs\n"
            help_text += "• `@DataDigger ims` - Show IMS jobs\n"
            help_text += "• `@DataDigger status` - Show all jobs\n\n"
            help_text += "**Individual jobs (use aliases):**\n"
            help_text += "• `usm7.8`, `usm7.88_mian`, `usm_7.8_main`\n"
            help_text += "• `i10`, `main10` (for IMS 10.0)\n\n"
            help_text += "Please use the correct keywords."
            
            api.messages.create(roomId=room_id, text=help_text)
    
    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)
