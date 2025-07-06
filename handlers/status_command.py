# from webex_bot.models.command import Command
# from config import WEBEX_BOT_TOKEN, WEBEX_BOT_PERSON_ID
# from webexteamssdk import WebexTeamsAPI
# from jenkins.jenkins_fetcher import read_jenkins_jobs, read_credentials, fetch_job_status
# from cards.job_card import build_job_card
# import time

# api = WebexTeamsAPI(access_token=WEBEX_BOT_TOKEN)

# class JenkinsStatusCommand(Command):
#     def __init__(self):
#         super().__init__(
#             command_keyword="jenkins",
#             help_message="Show latest Jenkins build status.",
#             card=None,
#         )

#     def execute(self, message, teams_message, activity):
#         if activity.get("personId") == WEBEX_BOT_PERSON_ID:
#             return

#         room_id = teams_message.roomId
#         username, token = read_credentials("jenkins/credentials.ini")
#         jobs = read_jenkins_jobs("jenkins/job_config.ini")

#         for job in jobs:
#             job_status = fetch_job_status(job, username, token)
#             card_text = build_job_card(job_status)
#             api.messages.create(roomId=room_id, markdown=card_text)
#             time.sleep(1)

from webex_bot.models.command import Command
from config import WEBEX_BOT_PERSON_ID, WEBEX_BOT_TOKEN
from jenkins.jenkins_fetcher import read_jenkins_jobs, read_credentials, fetch_job_status
from cards.job_card import build_job_card
from webexteamssdk import WebexTeamsAPI
import time
import datetime
import pytz

api = WebexTeamsAPI(access_token=WEBEX_BOT_TOKEN)

class JenkinsStatusCommand(Command):
    def __init__(self):
        super().__init__(
            command_keyword="jenkins",
            help_message="Show latest Jenkins build status.",
            card=None,
        )

    def execute(self, message, teams_message, activity):
        if activity.get("personId") == WEBEX_BOT_PERSON_ID:
            return

        room_id = teams_message.roomId
        jobs = read_jenkins_jobs("jenkins/job_config.ini")
        username, token = read_credentials("jenkins/credentials.ini")

        for job in jobs:
            job_status = fetch_job_status(job, username, token)

            # Adjust TRT to America/New_York timezone + 4 hours for correction
            if "time_obj" in job_status:
                est = pytz.timezone('America/New_York')
                corrected_time = job_status["time_obj"].astimezone(est) + datetime.timedelta(hours=4)
                job_status["time"] = corrected_time.strftime('%I:%M %p')
                job_status["date"] = corrected_time.strftime('%Y-%m-%d')
            else:
                job_status["date"] = "N/A"
                job_status["time"] = "N/A"

            # Fix RUNNING detection: Jenkins may return "result": null
            if job_status.get("result") is None:
                job_status["result"] = "RUNNING"

            # Build markdown clickable link text using display name
            if "url" in job_status and "display_name" in job_status:
                job_status["link_text"] = f"[{job_status['display_name']}]({job_status['url']})"
            else:
                job_status["link_text"] = job_status.get("name", "Unknown")

            card_text = build_job_card(job_status)
            api.messages.create(roomId=room_id, markdown=card_text)
            time.sleep(1)
