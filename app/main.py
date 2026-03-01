from webex_bot.webex_bot import WebexBot
from app.handlers.status_command import (
    JenkinsStatusCommand,
    USMStatusCommand,
    IMSStatusCommand,
    ASAStatusCommand,
    FXOSStatusCommand,
    StatusCommand,
)
from app.core.settings import get_webex_settings
from app.core.messages import build_unknown_job_help_text


WEBEX_BOT_TOKEN, _ = get_webex_settings()


class NoCardWebexBot(WebexBot):
    def __init__(self, access_token):
        super().__init__(access_token)
        from webexteamssdk import WebexTeamsAPI

        self.api = WebexTeamsAPI(access_token=access_token)

    def process_raw_command(self, raw_message, teams_message, user_email, activity):
        """Override to prevent default help cards."""
        user_command = raw_message.strip()

        for command in self.commands:
            if not hasattr(command, "match_substring"):
                continue

            if command.command_keyword and (
                (command.match_substring and command.command_keyword in user_command.lower())
                or (
                    not command.match_substring
                    and user_command.lower().startswith(command.command_keyword.lower())
                )
            ):
                return super().process_raw_command(
                    raw_message, teams_message, user_email, activity
                )

        jenkins_command = None
        for command in self.commands:
            if hasattr(command, "command_keyword") and command.command_keyword == "jenkins":
                jenkins_command = command
                break

        if jenkins_command:
            try:
                jenkins_command.execute(raw_message, teams_message, activity)
                return
            except Exception:
                pass

        room_id = teams_message.roomId
        text = raw_message.strip()
        help_text = build_unknown_job_help_text(text)
        self.api.messages.create(roomId=room_id, text=help_text)


def run():
    bot = NoCardWebexBot(WEBEX_BOT_TOKEN)
    bot.add_command(JenkinsStatusCommand())
    bot.add_command(USMStatusCommand())
    bot.add_command(IMSStatusCommand())
    bot.add_command(ASAStatusCommand())
    bot.add_command(FXOSStatusCommand())
    bot.add_command(StatusCommand())
    bot.run()
