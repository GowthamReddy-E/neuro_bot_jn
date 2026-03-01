import configparser
import os
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


def _instance_env_vars(instance):
    key = (instance or "default").upper().replace("-", "_").replace(".", "_")
    key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in key)
    return f"JENKINS_{key}_USERNAME", f"JENKINS_{key}_TOKEN"


def _read_credentials_from_env(instance="default"):
    """Read instance credentials from environment variables."""
    user_var, token_var = _instance_env_vars(instance)
    username = os.getenv(user_var)
    token = os.getenv(token_var)
    if username and token:
        return username, token

    # Fallback to default environment credentials if instance-specific values are absent.
    if instance != "default":
        user_var, token_var = _instance_env_vars("default")
        username = os.getenv(user_var)
        token = os.getenv(token_var)
        if username and token:
            return username, token

    raise ValueError(
        f"Missing Jenkins environment credentials for instance '{instance}'."
    )


def read_credentials(credentials_file=None, instance="default"):
    """
    Read credentials for a specific Jenkins instance
    
    Args:
        credentials_file: Optional path to credentials.ini file
        instance: Instance name (section in credentials.ini)
    
    Returns:
        tuple: (username, token)
    """
    # Preferred source: environment variables.
    try:
        return _read_credentials_from_env(instance)
    except ValueError:
        pass

    if not credentials_file:
        raise ValueError(
            f"No credentials file provided and env credentials missing for instance '{instance}'"
        )

    config = configparser.ConfigParser()
    config.read(credentials_file)

    if instance in config:
        return config[instance]["username"], config[instance]["token"]

    if "default" in config:
        return config["default"]["username"], config["default"]["token"]

    # Final fallback: use the first configured section to avoid command failure.
    sections = config.sections()
    if sections:
        fallback_instance = sections[0]
        return config[fallback_instance]["username"], config[fallback_instance]["token"]

    raise ValueError(f"No credentials found in '{credentials_file}'")

def get_job_credentials(job_name, job_config_file, credentials_file=None):
    """
    Get credentials for a specific job based on its instance configuration
    
    Args:
        job_name: Name of the job
        job_config_file: Path to job_config.ini file
        credentials_file: Optional path to credentials.ini file
    
    Returns:
        tuple: (username, token)
    """
    config = configparser.ConfigParser()
    config.read(job_config_file)
    
    # Check if job has a specific instance defined
    instance = "default"
    if job_name in config and "instance" in config[job_name]:
        instance = config[job_name]["instance"]
    
    return read_credentials(credentials_file, instance)

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

        full_display_name = data.get("fullDisplayName") or job["name"]
        custom_display_name = job.get("display_name", "").strip()

        if custom_display_name:
            base_display_name = custom_display_name
        else:
            # Normalize Jenkins display text by removing trailing build number if present.
            base_display_name = full_display_name
            if " #" in full_display_name:
                name_part, build_part = full_display_name.rsplit(" #", 1)
                if build_part.isdigit():
                    base_display_name = name_part
            elif " " in full_display_name:
                name_part, maybe_number = full_display_name.rsplit(" ", 1)
                if maybe_number.isdigit():
                    base_display_name = name_part

        # Prefer Jenkins displayName (display build number) over raw numeric build number.
        # Example: displayName can be custom while number is always integer.
        build_display = (data.get("displayName") or f"#{data['number']}").strip()
        display_name = f"{base_display_name} {build_display}"
        result = "RUNNING" if data.get("building") else data.get("result") or "UNKNOWN"
        last_completed_number = data.get("lastCompletedBuild", {}).get("number")
        last_completed_status = None

        if result == "RUNNING":
            if last_completed_number is None:
                # Some Jenkins jobs expose previousBuild even when lastCompletedBuild is missing.
                last_completed_number = data.get("previousBuild", {}).get("number")

            if last_completed_number is None:
                # Fallback for jobs that omit both fields while running.
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
                # Ignore this optional enrichment if the lookup fails.
                pass

        # Duration in HH:MM:SS
        duration_secs = int(data.get("duration", 0) / 1000)
        duration_str = f"{duration_secs//3600:02}:{(duration_secs % 3600)//60:02}:{duration_secs % 60:02}"

        # Timestamp -> IST conversion (UTC + 5:30)
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
            "triggered_date": triggered_date
        }

        if result == "RUNNING" and last_completed_number is not None:
            status["last_completed_number"] = last_completed_number
            if last_completed_status:
                status["last_completed_status"] = last_completed_status

        return status

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
