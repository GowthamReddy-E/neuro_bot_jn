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
            # Match individual job by fuzzy key or alias
            for section in config_urls.sections():
                if section == "URLS":
                    continue
                job_name = section
                aliases = config_urls[section].get("alias", "").lower().split(",")
                all_keywords = [job_name.lower()] + [a.strip() for a in aliases]
                if text in all_keywords:
                    url = config_urls["URLS"].get(job_name)
                    if url:
                        matched_jobs.append({"name": job_name, "url": url})

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
