import os
import telebot

# Avoid telebot from using threads for processing to be compatible with Serverless
telebot.apihelper.ENABLE_MIDDLEWARE = True

def get_bot():
    token = os.getenv('BOT_TOKEN')
    if not token:
        # Fallback for development if needed, or raise Error
        token = "dummy_token" # You should raise an error in production, but let's allow it to start without crashing on import
        if os.getenv('VERCEL') == '1' or os.getenv('BOT_TOKEN'):
             token = os.getenv('BOT_TOKEN')
             if not token:
                 raise ValueError("BOT_TOKEN not set")
    # threaded=False is important for serverless execution
    bot = telebot.TeleBot(token, threaded=False)
    return bot

bot = get_bot()

# Import handlers here to register them with the bot instance
from bot import handlers
