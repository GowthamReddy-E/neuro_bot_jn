from datetime import datetime, timedelta

import requests
from requests.auth import HTTPBasicAuth


def fetch_job_status(job, username, token):
    try:
        url = f"{job['url']}lastBuild/api/json"
        response = requests.get(url, auth=HTTPBasicAuth(username, token))

        if response.status_code != 200:
            return {
                "name": job["name"],
                "error": f"HTTP {response.status_code}: {response.reason}",
            }

        data = response.json()

        if "number" not in data:
            return {
                "name": job["name"],
                "error": "No build number found - job may never have been built",
            }

        full_display_name = data.get("fullDisplayName") or job["name"]
        custom_display_name = job.get("display_name", "").strip()

        if custom_display_name:
            base_display_name = custom_display_name
        else:
            base_display_name = full_display_name
            if " #" in full_display_name:
                name_part, build_part = full_display_name.rsplit(" #", 1)
                if build_part.isdigit():
                    base_display_name = name_part
            elif " " in full_display_name:
                name_part, maybe_number = full_display_name.rsplit(" ", 1)
                if maybe_number.isdigit():
                    base_display_name = name_part

        build_display = (data.get("displayName") or f"#{data['number']}").strip()
        display_name = f"{base_display_name} {build_display}"
        result = "RUNNING" if data.get("building") else data.get("result") or "UNKNOWN"
        last_completed_number = data.get("lastCompletedBuild", {}).get("number")
        last_completed_status = None

        if result == "RUNNING":
            if last_completed_number is None:
                last_completed_number = data.get("previousBuild", {}).get("number")

            if last_completed_number is None:
                current_number = data.get("number")
                if isinstance(current_number, int) and current_number > 1:
                    last_completed_number = current_number - 1

            last_completed_url = data.get("lastCompletedBuild", {}).get("url")
            if not last_completed_url:
                last_completed_url = data.get("previousBuild", {}).get("url")

            if last_completed_number is not None and not last_completed_url:
                last_completed_url = f"{job['url']}{last_completed_number}/"

        if result == "RUNNING" and last_completed_number is not None:
            try:
                completed_response = requests.get(
                    f"{last_completed_url}api/json",
                    auth=HTTPBasicAuth(username, token),
                )
                if completed_response.status_code == 200:
                    completed_data = completed_response.json()
                    last_completed_status = completed_data.get("result") or "UNKNOWN"
            except requests.exceptions.RequestException:
                pass

        duration_secs = int(data.get("duration", 0) / 1000)
        duration_str = f"{duration_secs//3600:02}:{(duration_secs % 3600)//60:02}:{duration_secs % 60:02}"

        timestamp = data.get("timestamp", 0) / 1000
        triggered = datetime.utcfromtimestamp(timestamp) + timedelta(hours=5, minutes=30)
        triggered_time = triggered.strftime("%I:%M %p")
        triggered_date = triggered.strftime("%Y-%m-%d")

        status = {
            "name": display_name,
            "number": data["number"],
            "url": f"{job['url']}{data['number']}/",
            "link_text": f"[{display_name}]({job['url']}{data['number']}/)",
            "result": result,
            "duration": duration_str,
            "triggered": triggered_time,
            "triggered_date": triggered_date,
        }

        if result == "RUNNING" and last_completed_number is not None:
            status["last_completed_number"] = last_completed_number
            if last_completed_status:
                status["last_completed_status"] = last_completed_status

        return status

    except requests.exceptions.RequestException as exc:
        return {
            "name": job["name"],
            "error": f"Network error: {str(exc)}",
        }
    except ValueError as exc:
        return {
            "name": job["name"],
            "error": f"Invalid JSON response: {str(exc)}",
        }
    except Exception as exc:
        return {
            "name": job["name"],
            "error": f"Unexpected error: {str(exc)}",
        }
