from webex_bot.webex_bot import WebexBot
from handlers.status_command import JenkinsStatusCommand
from config import WEBEX_BOT_TOKEN

bot = WebexBot(WEBEX_BOT_TOKEN)
bot.add_command(JenkinsStatusCommand())
bot.run()
