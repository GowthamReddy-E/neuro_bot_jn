def build_job_card(job):
    if "error" in job:
        return f"❌ **{job['name']}** - {job['error']}"

    emoji = {
        "SUCCESS": "🟢",
        "FAILURE": "🔴",
        "ABORTED": "⚫",
        "UNSTABLE": "🟡",
        "RUNNING": "🔁"
    }.get(job["result"], "❓")

    return (
        f"{emoji} [{job['name']} #{job['number']}]({job['url']})\n"
        f"TRD: {job['triggered_date']} TRT: {job['triggered']} Duration: {job['duration']} Status: {job['result']}"
    )


