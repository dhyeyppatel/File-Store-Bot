import os
import telebot

def get_bot():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("BOT_TOKEN environment variable is not set")
    # threaded=False is required for serverless execution
    return telebot.TeleBot(token, threaded=False)

bot = get_bot()

# Import handlers to register them with the bot instance.
# Use relative import style to avoid shadowing the 'bot' variable above.
from bot import handlers
