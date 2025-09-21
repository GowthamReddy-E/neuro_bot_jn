import configparser
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta


def read_jenkins_jobs(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    jobs = []
    for section in config.sections():
        aliases = config[section].get("alias", "")
        alias_list = [a.strip().lower() for a in aliases.split(",") if a.strip()]
        jobs.append({
            "name": section,
            "url": config[section]["url"],
            "aliases": alias_list
        })
    return jobs


def read_credentials(credentials_file):
    config = configparser.ConfigParser()
    config.read(credentials_file)
    return config["default"]["username"], config["default"]["token"]

def fetch_job_status(job, username, token):
    try:
        url = f"{job['url']}lastBuild/api/json"
        response = requests.get(url, auth=HTTPBasicAuth(username, token))
        
        # Check HTTP response status
        if response.status_code != 200:
            return {
                "name": job["name"],
                "error": f"HTTP {response.status_code}: {response.reason}"
            }
        
        data = response.json()
        
        # Check if required fields are present
        if "number" not in data:
            return {
                "name": job["name"],
                "error": "No build number found - job may never have been built"
            }

        display_name = data.get("fullDisplayName") or f"{job['name']} #{data['number']}"
        result = "RUNNING" if data.get("building") else data.get("result") or "UNKNOWN"

        # Duration in HH:MM:SS
        duration_secs = int(data.get("duration", 0) / 1000)
        duration_str = f"{duration_secs//3600:02}:{(duration_secs % 3600)//60:02}:{duration_secs % 60:02}"

        # Timestamp -> IST conversion (UTC + 5:30)
        timestamp = data.get("timestamp", 0) / 1000
        triggered = datetime.utcfromtimestamp(timestamp) + timedelta(hours=5, minutes=30)
        triggered_time = triggered.strftime("%I:%M %p")
        triggered_date = triggered.strftime("%Y-%m-%d")

        return {
            "name": display_name,
            "number": data["number"],
            "url": f"{job['url']}{data['number']}/",
            "link_text": f"[{display_name}]({job['url']}{data['number']}/)",
            "result": result,
            "duration": duration_str,
            "triggered": triggered_time,
            "triggered_date": triggered_date
        }

    except requests.exceptions.RequestException as e:
        return {
            "name": job["name"],
            "error": f"Network error: {str(e)}"
        }
    except ValueError as e:
        return {
            "name": job["name"],
            "error": f"Invalid JSON response: {str(e)}"
        }
    except Exception as e:
        return {
            "name": job["name"],
            "error": f"Unexpected error: {str(e)}"
        }
