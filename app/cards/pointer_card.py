def _format_date(iso_date):
    """Convert ISO or P4 date to readable format.

    Handles: 2025-05-20T10:30:00Z -> 2025-05-20 10:30
             2025/05/20            -> 2025-05-20
    """
    if not iso_date or iso_date == "N/A":
        return "N/A"
    # P4 dates use slashes
    date_str = iso_date.replace("/", "-").replace("T", " ").replace("Z", "")
    return date_str[:16]


def _build_diff(left_val, right_val, left_name):
    """Compute build difference between two combined values.

    Extracts the last numeric segment (build number) from values like
    '99.25.0.216' and computes how far left is behind/ahead of right.

    Returns a string like 'SAME', 'IMS_10_5_MAIN -1', 'IMS_10_5_MAIN +3'.
    """
    if left_val == right_val:
        return "SAME"

    try:
        left_build = int(left_val.rsplit(".", 1)[-1])
        right_build = int(right_val.rsplit(".", 1)[-1])
    except (ValueError, AttributeError):
        return "DIFF"

    diff = left_build - right_build
    if diff == 0:
        return "SAME"
    sign = f"{diff:+d}"
    return f"{left_name} {sign}"


def _latest_update(last_updated_dict):
    """Get the most recent update time from a dict of file -> ISO date."""
    dates = [d for d in last_updated_dict.values() if d and d != "N/A"]
    if not dates:
        return "N/A"
    return _format_date(max(dates))


def _days_ago(left_date, right_date):
    """Show how long since the left (IMS) branch was updated."""
    from datetime import datetime, timezone

    date_str = left_date
    if not date_str or date_str == "N/A":
        return ""

    # Normalize P4 slashes
    normalized = date_str.replace("/", "-")
    try:
        if " " in normalized and len(normalized) >= 16:
            dt = datetime.strptime(normalized[:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.strptime(normalized[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return ""

    days = (datetime.now(timezone.utc).date() - dt.date()).days
    if days == 0:
        return "updated today"
    elif days == 1:
        return "1 day ago"
    elif days >= 3:
        return f"🚨 {days} days ago"
    else:
        return f"{days} days ago"


def build_pointer_card(result):
    """Build a markdown card for pointer values from a single branch.

    Shows combined display values like:
        📌 IMS_10_5 — IMS_10_5_MAIN
        ASA: 99.25.0.216
        FXOS: 82.19.0.293
        Updated: 2025-05-20 10:30
    """
    if result.get("error"):
        return f"❌ **{result['branch']}** - {result['error']}"

    updated = _latest_update(result.get("last_updated", {}))
    lines = [f"📌 **{result['branch']}**", ""]

    # Use combined display values if available, fallback to raw
    if result.get("display"):
        for label, val in result["display"].items():
            lines.append(f"**{label}**: `{val}`")
    else:
        for key, val in result.get("raw_values", {}).items():
            lines.append(f"**{key}**: `{val}`")

    lines.append(f"\n🕐 Updated: `{updated}`")

    return "\n".join(lines)


def build_pointer_compare_card(results, jenkins_results=None, source="github"):
    """Build an enhanced comparison table with pointer + Jenkins data.

    Format:
    - Per component: codebase values, build values, match status
    - After first component: job status, tag, IMS build number
    - Footer: pointer update timestamps
    """
    if len(results) < 2:
        return "❌ Need at least two branches to compare."

    left, right = results[0], results[1]
    jk_left = (jenkins_results or [{}])[0] if jenkins_results else {}
    jk_right = (jenkins_results or [{}, {}])[1] if jenkins_results and len(jenkins_results) > 1 else {}

    if left.get("error"):
        return f"❌ **{left['section']}** - {left['error']}"
    if right.get("error"):
        return f"❌ **{right['section']}** - {right['error']}"

    left_updated_map = left.get("last_updated", {})
    right_updated_map = right.get("last_updated", {})

    # Get display labels (ASA, FXOS etc.)
    all_labels = list(
        dict.fromkeys(
            list(left.get("display", {}).keys()) + list(right.get("display", {}).keys())
        )
    )

    if not all_labels:
        all_labels = list(
            dict.fromkeys(
                list(left.get("raw_values", {}).keys()) + list(right.get("raw_values", {}).keys())
            )
        )
        left_vals = left.get("raw_values", {})
        right_vals = right.get("raw_values", {})
    else:
        left_vals = left.get("display", {})
        right_vals = right.get("display", {})

    # Jenkins display values
    jk_left_vals = jk_left.get("report_display", {})
    jk_right_vals = jk_right.get("report_display", {})
    jk_left_match = jk_left.get("ptr_vs_job", {})
    jk_right_match = jk_right.get("ptr_vs_job", {})

    # Build column widths — account for long Tag values
    left_branch = left["branch"]
    right_branch = right["branch"]
    lt = jk_left.get("build_description", "")
    rt = jk_right.get("build_description", "")
    label_w = 22
    col_w = max(18, len(left_branch) + 2, len(right_branch) + 2, len(lt) + 2, len(rt) + 2)
    diff_col = max(16, len(left_branch) + 8)

    rows = []

    # Map display labels to file paths for per-component timestamps
    label_file_map = {}
    for fpath in left_updated_map:
        fname = fpath.rsplit("/", 1)[-1].upper()
        for label in all_labels:
            if label.upper() in fname:
                label_file_map[label] = fpath
                break

    # Per-component rows: codebase, builds, sync, updated
    for label in all_labels:
        lv = left_vals.get(label, "N/A")
        rv = right_vals.get(label, "N/A")
        diff_str = _build_diff(lv, rv, left_branch)
        rows.append((f"{label}[codebase]", lv, rv, diff_str))

        jlv = jk_left_vals.get(label, "N/A")
        jrv = jk_right_vals.get(label, "N/A")

        # Only show Builds/Sync rows for GitHub sources with Jenkins data
        if source != "p4" and (jlv != "N/A" or jrv != "N/A"):
            jdiff = _build_diff(jlv, jrv, left_branch) if jlv != "N/A" else ""
            rows.append((f"{label}(Builds)", jlv, jrv, jdiff))

            # Sync status right after component
            lm = jk_left_match.get(label, "N/A")
            rm = jk_right_match.get(label, "N/A")
            l_sync = "IN SYNC" if lm == "MATCH" else f"OUT OF SYNC({lv}->{jlv})" if lm != "N/A" else "N/A"
            r_sync = "IN SYNC" if rm == "MATCH" else f"OUT OF SYNC({rv}->{jrv})" if rm != "N/A" else "N/A"
            rows.append((f"{label} Sync", l_sync, r_sync, ""))

        # Per-component pointer update time
        fpath = label_file_map.get(label)
        if fpath:
            l_date = _format_date(left_updated_map.get(fpath, "N/A"))
            r_date = _format_date(right_updated_map.get(fpath, "N/A"))
            time_diff = _days_ago(l_date, r_date)
            rows.append((f"{label} Updated", l_date, r_date, time_diff))

        rows.append(("", "", "", ""))

    # Jenkins job details — skip for P4 sources
    if source != "p4":
        lb = jk_left.get("build_number", "N/A")
        rb = jk_right.get("build_number", "N/A")
        rows.append(("IMS", lb, rb, ""))

        lt = jk_left.get("build_description", "")
        rt = jk_right.get("build_description", "")
        if lt or rt:
            rows.append(("Tag", lt, rt, ""))

        ls = jk_left.get("job_status", "N/A")
        rs = jk_right.get("job_status", "N/A")
        rows.append(("Job Status", ls, rs, ""))

        rows.append(("", "", "", ""))

        # Jenkins errors (if any)
        if jk_left.get("error"):
            rows.append(("JK Error", jk_left["error"][:col_w], "", ""))
        if jk_right.get("error"):
            rows.append(("JK Error", "", jk_right["error"][:col_w], ""))


    # Build preformatted table
    hdr = f"{'Component':<{label_w}} {left_branch:<{col_w}} {right_branch:<{col_w}} {'Diff':<{diff_col}}"
    sep = f"{'─' * label_w} {'─' * col_w} {'─' * col_w} {'─' * diff_col}"

    table_lines = [hdr, sep]
    for label, lv, rv, diff_str in rows:
        table_lines.append(f"{label:<{label_w}} {lv:<{col_w}} {rv:<{col_w}} {diff_str:<{diff_col}}")

    table_text = "\n".join(table_lines)

    lines = [
        "🔀 **Pointer Compare**",
        "",
        f"```\n{table_text}\n```",
    ]

    return "\n".join(lines)


def build_pointer_history_card(section, branch, history_list):
    """Build a markdown card showing recent commits for pointer files."""
    lines = [f"📜 **History**: **{section}** — `{branch}`"]

    for entry in history_list:
        file_path = entry["file"]
        if "error" in entry:
            lines.append(f"\n**{file_path}**: ❌ {entry['error']}")
            continue

        lines.append(f"\n**{file_path}**:")
        for commit in entry.get("commits", []):
            date_str = _format_date(commit["date"])
            lines.append(
                f"  `{commit['sha']}` {date_str} — {commit['message']} ({commit['author']})"
            )

    return "\n".join(lines)
