def normalize_command_text(message):
    """Normalize user text by removing bot prefixes and command keyword."""
    text = (message or "").strip().lower()
    text = text.replace("datadigger", "").replace("bot", "").replace("jenkins", "").strip()
    return text


def build_scoped_jenkins_message(message, scope_keyword):
    """Preserve scoped command input and convert it to jenkins command text."""
    raw = (message or "").strip()
    scope = scope_keyword.lower()
    lowered = raw.lower()
    known_prefixes = ("usm_", "ims_", "asa_", "fxos_", "lina_", "bazel_")

    if not raw or lowered == scope:
        return f"jenkins {scope_keyword}"

    if raw.startswith("_"):
        return f"jenkins {scope}{raw}"

    if " " not in raw and "_" in raw and not lowered.startswith(known_prefixes):
        return f"jenkins {scope}_{raw.lstrip('_')}"

    if lowered.startswith(f"{scope} "):
        suffix = raw[len(scope_keyword):].strip()
        return f"jenkins {suffix}" if suffix else f"jenkins {scope_keyword}"

    return f"jenkins {raw}"
