# from webex_bot.models.command import Command
# from config import WEBEX_BOT_PERSON_ID, WEBEX_BOT_TOKEN
# from jenkins.jenkins_fetcher import read_jenkins_jobs, read_credentials, fetch_job_status
# from cards.job_card import build_job_card
# from webexteamssdk import WebexTeamsAPI
# import time

# api = WebexTeamsAPI(access_token=WEBEX_BOT_TOKEN)
# from webexteamssdk import WebexTeamsAPI
# from config import WEBEX_BOT_TOKEN

# class JenkinsStatusCommand(Command):
#     def __init__(self):
#         super().__init__(
#             command_keyword="jenkins",
#             help_message="Show Jenkins build status for all or specific job.",
#             card=None,
#         )
#         self.api = WebexTeamsAPI(access_token=WEBEX_BOT_TOKEN)



#     def execute(self, message, teams_message, activity):
#         self._handle_status_request(message, teams_message)

#     def card_callback(self, message, teams_message, activity=None):
#         # This handles "IMS_10_0_MAIN" style messages
#         self._handle_status_request(message, teams_message)
    
#     def _handle_status_request(self, message, teams_message):
#         from jenkins.jenkins_fetcher import read_jenkins_jobs, read_credentials, fetch_job_status
#         from cards.job_card import build_job_card
#         from config import WEBEX_BOT_PERSON_ID

#         if teams_message.personId == WEBEX_BOT_PERSON_ID:
#             return

#         room_id = teams_message.roomId
#         jobs = read_jenkins_jobs("jenkins/job_config.ini")
#         username, token = read_credentials("jenkins/credentials.ini")

#         user_text = message.lower().replace("datadigger", "").replace("jenkins", "").strip()

#         matched_jobs = []
#         for job in jobs:
#             name_match = job["name"].lower().replace("/", "_")
#             alias_match = user_text in job.get("aliases", [])
#             if user_text == name_match or alias_match:
#                 matched_jobs.append(job)

#         if not matched_jobs:
#             self.api.messages.create(roomId=room_id, text=f"❌ No job found for `{message.strip()}`.")
#             return

#         for job in matched_jobs:
#             status = fetch_job_status(job, username, token)
#             card_text = build_job_card(status)
#             self.api.messages.create(roomId=room_id, markdown=card_text)

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
            help_message="Show Jenkins build status for all or specific job or group.",
            card=None,
        )
        self.match_substring = True

    def execute(self, message, teams_message, activity):
        if activity.get("personId") == WEBEX_BOT_PERSON_ID:
            return

        room_id = teams_message.roomId
        text = message.strip().lower().replace("datadigger", "").replace("jenkins", "").strip()

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
            # Match individual job by fuzzy key
            for key in config_urls["URLS"]:
                if text in key.lower():
                    matched_jobs.append({"name": key, "url": config_urls["URLS"][key]})

        if not matched_jobs:
            api.messages.create(roomId=room_id, text=f"❌ No job found for `{message}`.")
            return

        for job in matched_jobs:
            job_status = fetch_job_status(job, username, token)

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
