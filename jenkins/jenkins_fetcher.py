import configparser
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta

def read_jenkins_jobs(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    return [{"name": section, "url": config[section]["url"]} for section in config.sections()]

def read_credentials(credentials_file):
    config = configparser.ConfigParser()
    config.read(credentials_file)
    return config["default"]["username"], config["default"]["token"]

def fetch_job_status(job, username, token):
    try:
        url = f"{job['url']}lastBuild/api/json"
        response = requests.get(url, auth=HTTPBasicAuth(username, token))
        data = response.json()

        display_name = data.get("fullDisplayName")
        result = "RUNNING" if data.get("building") else data.get("result") or "UNKNOWN"

        duration_secs = int(data.get("duration", 0) / 1000)
        duration_str = f"{duration_secs//3600:02}:{(duration_secs % 3600)//60:02}:{duration_secs % 60:02}"

        timestamp = data.get("timestamp", 0) / 1000
        triggered = datetime.utcfromtimestamp(timestamp) + timedelta(hours=5, minutes=30)  # Convert to IST
        triggered_str = triggered.strftime("%I:%M %p")

        return {
            "name": job["name"],
            "number": data["number"],
            "url": f"{job['url']}{data['number']}/",
            "result": result,
            "duration": duration_str,
            "triggered": triggered.strftime("%I:%M %p"),
            "triggered_date": triggered.strftime("%Y-%m-%d")
        }

    except Exception as e:
        return {
            "name": job["name"],
            "error": str(e)
        }
