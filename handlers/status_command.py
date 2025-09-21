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
            api.messages.create(roomId=room_id, text=f"❌ No job found for `{message}`.")
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
            api.messages.create(roomId=room_id, text=f"❌ No job found for `{message}`.")
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
