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

    last_completed_text = ""
    if job.get("result") == "RUNNING" and "last_completed_number" in job:
        if "last_completed_status" in job:
            last_completed_text = (
                f"\nLast Completed: #{job['last_completed_number']} ({job['last_completed_status']})"
            )
        else:
            last_completed_text = f"\nLast Completed: #{job['last_completed_number']}"

    return (
        f"{emoji} [{job['name']}]({job['url']})\n"
        f"TRD: {job['triggered_date']} TRT: {job['triggered']} Duration: {job['duration']} Status: {job['result']}{last_completed_text}"
    )


