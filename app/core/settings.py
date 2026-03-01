import os


def get_webex_settings():
    """Read bot settings from environment first, then optional config.py fallback."""
    token = os.getenv("WEBEX_BOT_TOKEN")
    person_id = os.getenv("WEBEX_BOT_PERSON_ID")

    if token and person_id:
        return token, person_id

    try:
        from config import WEBEX_BOT_TOKEN, WEBEX_BOT_PERSON_ID  # type: ignore

        return WEBEX_BOT_TOKEN, WEBEX_BOT_PERSON_ID
    except Exception as exc:
        raise ValueError(
            "Missing WEBEX bot credentials. Set WEBEX_BOT_TOKEN and WEBEX_BOT_PERSON_ID "
            "in the environment (preferred) or provide config.py."
        ) from exc
