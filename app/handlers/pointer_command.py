from webex_bot.models.command import Command
from webexteamssdk import WebexTeamsAPI
from app.core.settings import get_webex_settings
from app.core.paths import POINTER_CONFIG_PATH, P4_POINTER_CONFIG_PATH
from app.clients.github_api import GitHubAPI
from app.services.github.pointer_service import (
    load_pointer_config as gh_load_config,
    fetch_pointer_values as gh_fetch_values,
    fetch_pointer_history as gh_fetch_history,
    fetch_jenkins_build_data as gh_fetch_jenkins,
    compare_pointer_vs_jenkins as gh_compare,
    resolve_pointer_sections as gh_resolve_sections,
    resolve_compare_group as gh_resolve_compare,
)
from app.services.perforce.pointer_service import (
    load_pointer_config as p4_load_config,
    fetch_pointer_values as p4_fetch_values,
    fetch_pointer_history as p4_fetch_history,
    fetch_jenkins_build_data as p4_fetch_jenkins,
    compare_pointer_vs_jenkins as p4_compare,
    resolve_pointer_sections as p4_resolve_sections,
    resolve_compare_group as p4_resolve_compare,
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

    def _detect_source(self, text):
        """Detect which source (github/perforce) to use based on the query.

        Returns (source, config, query) tuple.
        - Tries P4 config first for compare group or section match.
        - Falls back to GitHub config.
        """
        gh_config = gh_load_config(POINTER_CONFIG_PATH)
        p4_config = p4_load_config(P4_POINTER_CONFIG_PATH)

        # Check P4 compare groups
        p4_compare = p4_resolve_compare(text, p4_config)
        if p4_compare and len(p4_compare) >= 2:
            return "p4", p4_config, text

        # Check P4 sections
        p4_sections = p4_resolve_sections(text, p4_config)
        if p4_sections:
            return "p4", p4_config, text

        # Check GitHub compare groups
        gh_compare_result = gh_resolve_compare(text, gh_config)
        if gh_compare_result and len(gh_compare_result) >= 2:
            return "github", gh_config, text

        # Check GitHub sections
        gh_sections = gh_resolve_sections(text, gh_config)
        if gh_sections:
            return "github", gh_config, text

        # Default to GitHub
        return "github", gh_config, text

    def execute(self, message, teams_message, activity):
        if activity and activity.get("personId") == WEBEX_BOT_PERSON_ID:
            return

        room_id = teams_message.roomId
        raw = (message or "").strip()
        text = raw.lower().replace("pointers", "").replace("pointer", "").replace("datadigger", "").replace("bot", "").strip()

        # Handle "pointer compare [group]"
        if text.startswith("compare"):
            compare_query = text.replace("compare", "").strip()
            source, config, _ = self._detect_source(compare_query)
            self._handle_compare(room_id, config, compare_query, source)
            return

        # Handle "pointer history [section]"
        if text.startswith("history"):
            history_query = text.replace("history", "").strip()
            source, config, _ = self._detect_source(history_query)
            self._handle_history(room_id, config, history_query, source)
            return

        # Detect source and try compare group alias or section
        source, config, _ = self._detect_source(text)

        # Try compare group alias (e.g. "10.5" or "10.1" triggers compare)
        if source == "p4":
            compare_sections = p4_resolve_compare(text, config)
        else:
            compare_sections = gh_resolve_compare(text, config)
        if compare_sections and len(compare_sections) >= 2:
            self._handle_compare(room_id, config, text, source)
            return

        # Handle "pointer [section/alias]" or just "pointer"
        if source == "p4":
            sections = p4_resolve_sections(text, config)
        else:
            sections = gh_resolve_sections(text, config)

        if not sections:
            gh_config = gh_load_config(POINTER_CONFIG_PATH)
            p4_config = p4_load_config(P4_POINTER_CONFIG_PATH)
            help_text = self._build_help(gh_config, p4_config, text)
            api.messages.create(roomId=room_id, markdown=help_text)
            return

        for section in sections:
            if source == "p4":
                result = p4_fetch_values(config, section)
            else:
                result = gh_fetch_values(config, section, github_client)
            card = build_pointer_card(result)
            api.messages.create(roomId=room_id, markdown=card)
            time.sleep(1)

    def _handle_compare(self, room_id, config, query, source="github"):
        if source == "p4":
            sections = p4_resolve_compare(query, config)
        else:
            sections = gh_resolve_compare(query, config)

        if len(sections) < 2:
            api.messages.create(
                roomId=room_id,
                markdown="❌ No compare group found. Check `pointer_config.ini`.",
            )
            return

        results = []
        jenkins_results = []
        for section in sections[:2]:
            if source == "p4":
                ptr = p4_fetch_values(config, section)
                jk = p4_fetch_jenkins(config, section)
                jk["ptr_vs_job"] = p4_compare(ptr, jk)
            else:
                ptr = gh_fetch_values(config, section, github_client)
                jk = gh_fetch_jenkins(config, section, github_client)
                jk["ptr_vs_job"] = gh_compare(ptr, jk)
            results.append(ptr)
            jenkins_results.append(jk)

        card = build_pointer_compare_card(results, jenkins_results, source=source)

        # Check for stale pointers and tag notify list
        stale_msg = self._check_stale_pointers(config, sections[:2], results)
        if stale_msg:
            card += "\n\n" + stale_msg

        api.messages.create(roomId=room_id, markdown=card)

    def _handle_history(self, room_id, config, query, source="github"):
        if source == "p4":
            sections = p4_resolve_sections(query, config)
        else:
            sections = gh_resolve_sections(query, config)
        if not sections:
            sections = [s for s in config.sections() if s != "COMPARE_GROUPS"]

        for section in sections:
            branch = config[section]["branch"]
            if source == "p4":
                history = p4_fetch_history(config, section, limit=5)
            else:
                history = gh_fetch_history(config, section, github_client, limit=5)
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

            oldest_str = min(dates)[:16].replace("T", " ").replace("Z", "").replace("/", "-")
            try:
                if len(oldest_str.strip()) <= 10:
                    oldest = datetime.strptime(oldest_str.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                else:
                    oldest = datetime.strptime(oldest_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                age = (now.date() - oldest.date()).days
                if age >= stale_days:
                    branch = config[section].get("branch", section)
                    day_word = "day" if age == 1 else "days"
                    stale_sections.append(f"**{branch}** ({age} {day_word} old)")
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

    def _build_help(self, gh_config, p4_config, query):
        rendered = query if query else "(empty)"
        lines = [f"❌ No pointer config found for `{rendered}`.\n"]
        lines.append("**Available pointer commands:**")
        lines.append("• `@bot pointer` - Show all branches")
        lines.append("• `@bot pointer compare` - Compare IMS vs LINA")
        lines.append("• `@bot pointer history` - Recent changes\n")
        lines.append("**GitHub branches:**")
        for section in gh_config.sections():
            if section == "COMPARE_GROUPS":
                continue
            aliases = gh_config[section].get("alias", "")
            branch = gh_config[section].get("branch", "")
            lines.append(f"• `{section}` ({branch}) — aliases: `{aliases}`")
        lines.append("\n**Perforce branches:**")
        for section in p4_config.sections():
            if section == "COMPARE_GROUPS":
                continue
            aliases = p4_config[section].get("alias", "")
            branch = p4_config[section].get("branch", "")
            lines.append(f"• `{section}` ({branch}) — aliases: `{aliases}`")
        return "\n".join(lines)

    def card_callback(self, message, teams_message, activity=None):
        self.execute(message, teams_message, activity)
