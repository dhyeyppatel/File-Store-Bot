import os
import telebot

bot_instances = {}

def get_bot(token=None):
    """Get or create a cached TeleBot instance for the given token."""
    main_token = os.getenv('BOT_TOKEN')
    if not token:
        token = main_token
        if not token:
            raise ValueError("BOT_TOKEN environment variable is not set")
            
    if token not in bot_instances:
        # threaded=False is required for serverless execution
        bot = telebot.TeleBot(token, threaded=False)
        bot.is_main_bot = (token == main_token)
        
        # Import handlers inside to register them with this specific bot instance
        from bot.handlers import register_handlers
        register_handlers(bot)
        
        bot_instances[token] = bot
        
    return bot_instances[token]
