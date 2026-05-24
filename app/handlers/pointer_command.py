from webex_bot.models.command import Command
from webexteamssdk import WebexTeamsAPI
from app.core.settings import get_webex_settings
from app.core.paths import POINTER_CONFIG_PATH
from app.clients.github_api import GitHubAPI
from app.services.github.pointer_service import (
    load_pointer_config,
    fetch_pointer_values,
    fetch_pointer_history,
    fetch_jenkins_build_data,
    compare_pointer_vs_jenkins,
    resolve_pointer_sections,
    resolve_compare_group,
)
from app.cards.pointer_card import (
    build_pointer_card,
    build_pointer_compare_card,
    build_pointer_history_card,
)
import time

WEBEX_BOT_TOKEN, WEBEX_BOT_PERSON_ID = get_webex_settings()
api = WebexTeamsAPI(access_token=WEBEX_BOT_TOKEN)
github_client = GitHubAPI()


class PointerCommand(Command):
    """Show pointer file values from configured GitHub branches.

    Usage:
        @bot pointer              — show all branches
        @bot pointer ims_10_5     — show specific branch
        @bot pointer lina_pointer — use alias
        @bot pointer compare      — compare IMS vs LINA
        @bot pointer history      — show recent file changes
    """

    def __init__(self):
        super().__init__(
            command_keyword="pointer",
            help_message="",
            card=None,
        )
        self.match_substring = True

    def execute(self, message, teams_message, activity):
        if activity and activity.get("personId") == WEBEX_BOT_PERSON_ID:
            return

        room_id = teams_message.roomId
        raw = (message or "").strip()
        text = raw.lower().replace("pointers", "").replace("pointer", "").replace("datadigger", "").replace("bot", "").strip()

        config = load_pointer_config(POINTER_CONFIG_PATH)

        if not github_client.is_configured():
            api.messages.create(
                roomId=room_id,
                markdown="❌ GitHub is not configured. Set `GITHUB_TOKEN` environment variable.",
            )
            return

        # Handle "pointer compare [group]"
        if text.startswith("compare"):
            compare_query = text.replace("compare", "").strip()
            self._handle_compare(room_id, config, compare_query)
            return

        # Handle "pointer history [section]"
        if text.startswith("history"):
            history_query = text.replace("history", "").strip()
            self._handle_history(room_id, config, history_query)
            return

        # Try compare group alias (e.g. "10.5" triggers compare)
        compare_sections = resolve_compare_group(text, config)
        if compare_sections and len(compare_sections) >= 2:
            self._handle_compare(room_id, config, text)
            return

        # Handle "pointer [section/alias]" or just "pointer"
        sections = resolve_pointer_sections(text, config)

        if not sections:
            help_text = self._build_help(config, text)
            api.messages.create(roomId=room_id, markdown=help_text)
            return

        for section in sections:
            result = fetch_pointer_values(config, section, github_client)
            card = build_pointer_card(result)
            api.messages.create(roomId=room_id, markdown=card)
            time.sleep(1)

    def _handle_compare(self, room_id, config, query):
        sections = resolve_compare_group(query, config)
        if len(sections) < 2:
            api.messages.create(
                roomId=room_id,
                markdown="❌ No compare group found. Check `pointer_config.ini`.",
            )
            return

        results = []
        jenkins_results = []
        for section in sections[:2]:
            ptr = fetch_pointer_values(config, section, github_client)
            results.append(ptr)
            # Fetch Jenkins build data
            jk = fetch_jenkins_build_data(config, section, github_client)
            # Compare pointer vs Jenkins
            jk["ptr_vs_job"] = compare_pointer_vs_jenkins(ptr, jk)
            jenkins_results.append(jk)

        card = build_pointer_compare_card(results, jenkins_results)

        # Check for stale pointers and tag notify list
        stale_msg = self._check_stale_pointers(config, sections[:2], results)
        if stale_msg:
            card += "\n\n" + stale_msg

        api.messages.create(roomId=room_id, markdown=card)

    def _handle_history(self, room_id, config, query):
        sections = resolve_pointer_sections(query, config)
        if not sections:
            sections = [s for s in config.sections() if s != "COMPARE_GROUPS"]

        for section in sections:
            branch = config[section]["branch"]
            history = fetch_pointer_history(config, section, github_client, limit=5)
            card = build_pointer_history_card(section, branch, history)
            api.messages.create(roomId=room_id, markdown=card)
            time.sleep(1)

    def _check_stale_pointers(self, config, sections, results):
        """Check if any pointers are stale and return mention string."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        stale_sections = []
        notify_emails = set()

        for section, result in zip(sections, results):
            stale_days = int(config[section].get("stale_days", 2))
            last_updated = result.get("last_updated", {})
            dates = [d for d in last_updated.values() if d and d != "N/A"]
            if not dates:
                continue

            latest_str = max(dates)[:16].replace("T", " ").replace("Z", "")
            try:
                latest = datetime.strptime(latest_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                age = (now.date() - latest.date()).days
                if age >= stale_days:
                    branch = config[section].get("branch", section)
                    stale_sections.append(f"**{branch}** ({age} days old)")
                    emails = config[section].get("notify", "")
                    for e in emails.split(","):
                        e = e.strip()
                        if e:
                            notify_emails.add(e)
            except ValueError:
                continue

        if not stale_sections or not notify_emails:
            return ""

        mentions = " ".join(f"<@personEmail:{e}>" for e in notify_emails)
        branches = ", ".join(stale_sections)
        return f"⚠️ **Stale Pointers**: {branches}\n{mentions} — pointers need attention!"

    def _build_help(self, config, query):
        rendered = query if query else "(empty)"
        lines = [f"❌ No pointer config found for `{rendered}`.\n"]
        lines.append("**Available pointer commands:**")
        lines.append("• `@bot pointer` - Show all branches")
        lines.append("• `@bot pointer compare` - Compare IMS vs LINA")
        lines.append("• `@bot pointer history` - Recent changes\n")
        lines.append("**Configured branches:**")
        for section in config.sections():
            if section == "COMPARE_GROUPS":
                continue
            aliases = config[section].get("alias", "")
            branch = config[section].get("branch", "")
            lines.append(f"• `{section}` ({branch}) — aliases: `{aliases}`")
        return "\n".join(lines)

    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)
