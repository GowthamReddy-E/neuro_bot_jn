from webex_bot.webex_bot import WebexBot
from handlers.status_command import JenkinsStatusCommand, USMStatusCommand, IMSStatusCommand, StatusCommand
from config import WEBEX_BOT_TOKEN

bot = WebexBot(WEBEX_BOT_TOKEN)
bot.add_command(JenkinsStatusCommand())
bot.add_command(USMStatusCommand())
bot.add_command(IMSStatusCommand())
bot.add_command(StatusCommand())
bot.run()
