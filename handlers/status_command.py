from webex_bot.models.command import Command
from config import WEBEX_BOT_TOKEN, WEBEX_BOT_PERSON_ID
from webexteamssdk import WebexTeamsAPI
from jenkins.jenkins_fetcher import read_jenkins_jobs, read_credentials, fetch_job_status
from cards.job_card import build_job_card
import time

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
        username, token = read_credentials("jenkins/credentials.ini")
        jobs = read_jenkins_jobs("jenkins/job_config.ini")

        for job in jobs:
            job_status = fetch_job_status(job, username, token)
            card_text = build_job_card(job_status)
            api.messages.create(roomId=room_id, markdown=card_text)
            time.sleep(1)
