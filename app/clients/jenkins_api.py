import re
from datetime import datetime, timedelta

import requests
from requests.auth import HTTPBasicAuth


def fetch_recent_builds(job_url, username, token, limit=20):
    """Fetch recent builds from a Jenkins job.

    Returns list of dicts: [{number, displayName, result}, ...]
    """
    url = f"{job_url}api/json"
    params = {"tree": f"builds[number,displayName,description,result]{{{0},{limit}}}"}
    try:
        resp = requests.get(url, auth=HTTPBasicAuth(username, token), params=params, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("builds", [])
    except Exception:
        return []


def fetch_component_report(job_url, build_number, username, token, report_path="Component_20Version_20Report/"):
    """Fetch and parse Component Version Report from a Jenkins build.

    Returns a dict of component -> {key: value, ...}
    Example: {"ASA": {"ASABUILD": "216", "ASAVERSION": "99.25.0"}, "FXOS": {...}, "IMS": {...}}
    """
    base_url = f"{job_url}{build_number}/{report_path}"

    # Try multiple URL patterns (some Jenkins reports need index.html)
    urls_to_try = [base_url, f"{base_url}index.html"]

    auth = HTTPBasicAuth(username, token)

    for url in urls_to_try:
        try:
            resp = requests.get(url, auth=auth, timeout=15)
            if resp.status_code != 200 or not resp.text.strip():
                continue

            html = resp.text

            # Jenkins HTML Publisher uses a wrapper page with JS-loaded iframe.
            # The actual content file is in <li value="components.html">.
            tab_match = re.search(r'<li[^>]+value=["\']([^"\']+\.html)["\']', html)
            if tab_match:
                tab_file = tab_match.group(1)
                tab_url = url.rstrip("/") + "/" + tab_file
                resp2 = requests.get(tab_url, auth=auth, timeout=15)
                if resp2.status_code == 200 and resp2.text.strip():
                    html = resp2.text

            parsed = _parse_component_report(html)
            if len(parsed) > 1:
                return parsed
        except Exception:
            continue

    return None


def _parse_component_report(html_text):
    """Parse Component Version Report HTML into structured data.

    The HTML uses Bootstrap tables with malformed closing tags:
    - Section headers: <th colspan="2">ASA</th>
    - Key-value pairs:  <th><code>KEY</code></th><td><samp>VALUE</samp></td>

    Returns dict: {component_name: {key: value, ...}, "_title": "10.5.0.0-1495"}
    """
    result = {"_title": ""}

    # Extract title from navbar: "Components in IMS 10.5.0.0-1495"
    title_match = re.search(r"Components?\s+(?:in\s+|Report\s+for\s+)([\w\.\-\s]+)", html_text)
    if title_match:
        result["_title"] = title_match.group(1).strip()

    # Match section headers and key-value pairs directly (no <tr> dependency)
    pattern = re.compile(
        r'<th\s+colspan=["\']2["\'][^>]*>(.*?)</th>'
        r'|'
        r'<th(?!ead)[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>',
        re.DOTALL | re.IGNORECASE
    )

    current_section = None
    for m in pattern.finditer(html_text):
        if m.group(1) is not None:
            # Section header: <th colspan="2">ASA</th>
            section = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if section:
                current_section = section
                if current_section not in result:
                    result[current_section] = {}
        elif m.group(2) is not None and m.group(3) is not None:
            # Key-value: <th>KEY</th><td>VALUE</td>
            key = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            val = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            if current_section and current_section in result and key:
                result[current_section][key] = val

    return result


def find_build_by_number(job_url, username, token, target_build_num, limit=20):
    """Find a Jenkins build whose Component Report IMS BUILD matches target_build_num.

    Returns (jenkins_build_number, result_status, description) or (None, None, None).
    Also checks if the display name contains the build number.
    """
    builds = fetch_recent_builds(job_url, username, token, limit=limit)

    # First try: match display name containing the build number
    target_str = str(target_build_num)
    for build in builds:
        display = build.get("displayName", "")
        if target_str in display:
            desc = build.get("description") or display
            return build["number"], build.get("result", "UNKNOWN"), desc

    # Fallback: return last successful build
    for build in builds:
        if build.get("result") == "SUCCESS":
            desc = build.get("description") or build.get("displayName", "")
            return build["number"], "SUCCESS", desc

    # Last resort: return the latest build
    if builds:
        desc = builds[0].get("description") or builds[0].get("displayName", "")
        return builds[0]["number"], builds[0].get("result", "UNKNOWN"), desc

    return None, None, None


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
