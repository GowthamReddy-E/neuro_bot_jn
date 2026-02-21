from webex_bot.webex_bot import WebexBot
from handlers.status_command import JenkinsStatusCommand, USMStatusCommand, IMSStatusCommand, StatusCommand
from config import WEBEX_BOT_TOKEN

# Override the WebexBot to intercept unmatched messages
class NoCardWebexBot(WebexBot):
    def __init__(self, access_token):
        super().__init__(access_token)
        from webexteamssdk import WebexTeamsAPI
        self.api = WebexTeamsAPI(access_token=access_token)
        
    def process_raw_command(self, raw_message, teams_message, user_email, activity):
        """Override to prevent default help cards"""
        # First try to find a matching command
        user_command = raw_message.strip()
        
        # Check each registered command
        for command in self.commands:
            # Skip commands that don't have match_substring attribute (like HelpCommand)
            if not hasattr(command, 'match_substring'):
                continue
                
            if command.command_keyword and (
                (command.match_substring and command.command_keyword in user_command.lower()) or
                (not command.match_substring and user_command.lower().startswith(command.command_keyword.lower()))
            ):
                # Found a match, process normally
                return super().process_raw_command(raw_message, teams_message, user_email, activity)
        
        # No command keyword matched - try to process as Jenkins alias
        # Find the Jenkins command and let it handle alias matching
        jenkins_command = None
        for command in self.commands:
            if hasattr(command, 'command_keyword') and command.command_keyword == 'jenkins':
                jenkins_command = command
                break
        
        if jenkins_command:
            try:
                # Let the Jenkins command handle this - it will check for aliases
                jenkins_command.execute(raw_message, teams_message, activity)
                return
            except Exception as e:
                # If Jenkins command fails, fall through to error message
                pass
        
        # No match found - send our custom error message
        room_id = teams_message.roomId
        text = raw_message.strip()
        
        help_text = f"❌ No job found for `{text}`.\n\n"
        help_text += "**Available commands:**\n"
        help_text += "• `@DataDigger jenkins` - Show all jobs\n"
        help_text += "• `@DataDigger usm` - Show USM jobs\n"
        help_text += "• `@DataDigger ims` - Show IMS jobs\n"
        help_text += "• `@DataDigger status` - Show all jobs\n\n"
        help_text += "**Individual jobs (use aliases):**\n"
        help_text += "• `usm7.8`, `usm7.88_mian`, `usm_7.8_main`\n"
        help_text += "• `i10`, `main10` (for IMS 10.0)\n"
        help_text += "• `mr` (for USM 7.3 MR)\n\n"
        help_text += "Please use the correct keywords."
        
        self.api.messages.create(roomId=room_id, text=help_text)

bot = NoCardWebexBot(WEBEX_BOT_TOKEN)
bot.add_command(JenkinsStatusCommand())
bot.add_command(USMStatusCommand())
bot.add_command(IMSStatusCommand())
bot.add_command(StatusCommand())
bot.run()