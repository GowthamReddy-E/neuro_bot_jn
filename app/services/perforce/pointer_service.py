"""Perforce-based pointer service.

Reads pointer files from Perforce depot instead of GitHub.
Shares the same interface as the GitHub pointer service.
"""

import configparser
import re

from app.clients.p4_client import p4_print, p4_filelog, build_depot_path
from app.clients.jenkins_api import (
    find_build_by_number,
    fetch_component_report,
)
from app.services.jenkins.credentials_service import read_credentials


def load_pointer_config(config_path):
    """Load the pointer configuration INI file."""
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def parse_pointer_file(content):
    """Parse a shell-style KEY=VALUE file into a dict.

    Handles lines like:
        ASABUILD=217
        FXOS_BRANCH=82.19.0
    Ignores comments, blank lines, and lines with shell variable expansions.
    """
    values = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if match:
            key = match.group(1)
            val = match.group(2).strip().strip('"').strip("'")
            # Skip values that are pure shell variable expansions
            if "${" not in val:
                values[key] = val
    return values


def _build_display_values(all_values, display_spec):
    """Build combined display values from a display spec.

    display_spec example: "ASA=ASAVERSION.ASABUILD, FXOS=FXOS_BRANCH.FXOS_BUILD"
    Result: {"ASA": "99.25.0.217", "FXOS": "82.19.0.295"}
    """
    display = {}
    if not display_spec:
        return display

    for entry in display_spec.split(","):
        entry = entry.strip()
        if "=" not in entry:
            continue
        label, formula = entry.split("=", 1)
        label = label.strip()
        parts = [all_values.get(k.strip(), "N/A") for k in formula.strip().split(".")]
        display[label] = ".".join(parts)

    return display


def fetch_pointer_values(config, section):
    """Fetch pointer values for a single config section from Perforce.

    Returns a dict:
        {
            "section": "IMS_10_1",
            "branch": "IMS_10_1_MAIN",
            "raw_values": {"ASABUILD": "217", "FXOS_BUILD": "295", ...},
            "display": {"ASA": "99.25.0.217", "FXOS": "82.19.0.295"},
            "last_updated": {"product/ASABUILD": "2026/05/20", ...},
            "error": None
        }
    """
    depot_base = config[section].get("depot_base", "")
    p4_port = config[section].get("p4_port", None)
    branch = config[section]["branch"]
    files = [f.strip() for f in config[section]["files"].split(",")]
    keys = [k.strip() for k in config[section]["keys"].split(",")]
    display_spec = config[section].get("display", "")

    result = {
        "section": section,
        "repo": "",
        "branch": branch,
        "raw_values": {},
        "display": {},
        "last_updated": {},
        "error": None,
    }

    try:
        all_values = {}
        for file_path in files:
            depot_path = build_depot_path(depot_base, branch, file_path)
            content = p4_print(depot_path, p4_port)
            parsed = parse_pointer_file(content)
            all_values.update(parsed)

            # Get last changelist date
            try:
                entries = p4_filelog(depot_path, p4_port, limit=1)
                if entries:
                    result["last_updated"][file_path] = entries[0]["date"]
            except Exception:
                result["last_updated"][file_path] = "N/A"

        # Raw key values
        for key in keys:
            result["raw_values"][key] = all_values.get(key, "N/A")

        # Combined display values
        result["display"] = _build_display_values(all_values, display_spec)

    except Exception as exc:
        result["error"] = str(exc)

    return result


def fetch_pointer_history(config, section, limit=5):
    """Fetch recent changelist history for pointer files from Perforce."""
    depot_base = config[section].get("depot_base", "")
    p4_port = config[section].get("p4_port", None)
    branch = config[section]["branch"]
    files = [f.strip() for f in config[section]["files"].split(",")]

    history = []
    for file_path in files:
        try:
            depot_path = build_depot_path(depot_base, branch, file_path)
            entries = p4_filelog(depot_path, p4_port, limit=limit)
            commits = [
                {
                    "sha": e.get("change", ""),
                    "date": e.get("date", ""),
                    "message": e.get("description", ""),
                    "author": e.get("user", ""),
                }
                for e in entries
            ]
            history.append({"file": file_path, "commits": commits})
        except Exception as exc:
            history.append({"file": file_path, "error": str(exc)})

    return history


def resolve_pointer_sections(query, config):
    """Resolve a user query to matching pointer config sections."""
    if not query:
        return [s for s in config.sections() if s != "COMPARE_GROUPS"]

    query_lower = query.lower()

    # Exact section match
    for section in config.sections():
        if section == "COMPARE_GROUPS":
            continue
        if query_lower == section.lower():
            return [section]

    # Alias match
    for section in config.sections():
        if section == "COMPARE_GROUPS":
            continue
        aliases = config[section].get("alias", "").lower().split(",")
        aliases = [a.strip() for a in aliases if a.strip()]
        if query_lower in aliases:
            return [section]

    return []


def resolve_compare_group(query, config):
    """Resolve a user query to a compare group's sections."""
    if "COMPARE_GROUPS" not in config:
        return []

    groups = config["COMPARE_GROUPS"]
    query_lower = (query or "").strip().lower()

    for key in groups:
        if key.startswith("alias_"):
            continue

        group_name = key
        sections_str = groups[key]
        alias_key = f"alias_{group_name}"
        aliases = []
        if alias_key in groups:
            aliases = [a.strip().lower() for a in groups[alias_key].split(",") if a.strip()]

        if query_lower == group_name.lower() or query_lower in aliases:
            section_names = [s.strip() for s in sections_str.split(",") if s.strip()]
            return section_names

    # Default: return first non-alias group if no query
    if not query_lower:
        for key in groups:
            if not key.startswith("alias_"):
                section_names = [s.strip() for s in groups[key].split(",") if s.strip()]
                return section_names

    return []


def fetch_jenkins_build_data(config, section):
    """Fetch Jenkins build data for a Perforce-based pointer config section.

    Flow:
    1. Read product/BUILD from Perforce to get the current build number
    2. Find matching Jenkins build
    3. Fetch Component Version Report
    4. Extract ASA and FXOS values from the report
    """
    jenkins_url = config[section].get("jenkins_url", "")
    jenkins_instance = config[section].get("jenkins_instance", "")
    report_path = config[section].get("report_path", "Component_20Version_20Report/")
    build_file = config[section].get("build_file", "")
    display_spec = config[section].get("display", "")
    depot_base = config[section].get("depot_base", "")
    p4_port = config[section].get("p4_port", None)

    result = {
        "build_number": "N/A",
        "jenkins_build": None,
        "job_status": "N/A",
        "report_title": "",
        "report_display": {},
        "error": None,
    }

    if not jenkins_url or not jenkins_instance:
        result["error"] = "Jenkins not configured for this section"
        return result

    # 1. Read product/BUILD from Perforce
    if build_file:
        try:
            branch = config[section]["branch"]
            depot_path = build_depot_path(depot_base, branch, build_file)
            content = p4_print(depot_path, p4_port)
            result["build_number"] = content.strip()
        except Exception as exc:
            result["error"] = f"Failed to read {build_file}: {exc}"
            return result

    # 2. Get Jenkins credentials
    try:
        username, token = read_credentials(instance=jenkins_instance)
    except Exception as exc:
        result["error"] = f"Jenkins credentials error: {exc}"
        return result

    # 3. Find matching Jenkins build
    jenkins_build, job_status, build_desc = find_build_by_number(
        jenkins_url, username, token, result["build_number"]
    )

    if jenkins_build is None:
        result["error"] = "No matching Jenkins build found"
        return result

    result["jenkins_build"] = jenkins_build
    result["job_status"] = job_status or "UNKNOWN"
    result["build_description"] = build_desc or ""

    # 4. Fetch Component Version Report
    report = fetch_component_report(jenkins_url, jenkins_build, username, token, report_path)
    if not report:
        result["error"] = f"Failed to fetch Component Report for build #{jenkins_build}"
        return result

    result["report_title"] = report.get("_title", "")

    # 5. Extract values from report and build display values
    report_values = {}
    for component_name, component_data in report.items():
        if component_name.startswith("_"):
            continue
        if isinstance(component_data, dict):
            report_values.update(component_data)

    result["report_display"] = _build_display_values(report_values, display_spec)

    return result


def compare_pointer_vs_jenkins(pointer_result, jenkins_result):
    """Compare pointer display values with Jenkins report display values."""
    ptr_display = pointer_result.get("display", {})
    job_display = jenkins_result.get("report_display", {})
    comparison = {}

    for label in ptr_display:
        ptr_val = ptr_display.get(label, "N/A")
        job_val = job_display.get(label, "N/A")
        comparison[label] = "MATCH" if ptr_val == job_val else "MISMATCH"

    return comparison
