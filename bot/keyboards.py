from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import os

def upload_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("✅ Done"), KeyboardButton("❌ Cancel"))
    return markup

def remove_keyboard():
    from telebot.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()

def share_keyboard(token):
    markup = InlineKeyboardMarkup()
    bot_username = os.getenv('BOT_USERNAME', 'YourBot')
    url = f"https://t.me/{bot_username}?start={token}"
    share_url = f"https://t.me/share/url?url={url}"
    markup.add(InlineKeyboardButton("🔗 Open Files", url=url))
    markup.add(InlineKeyboardButton("📋 Share Link", url=share_url))
    return markup

def retrieve_keyboard(token):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📥 Send All", callback_data=f"send_all_{token}"))
    return markup
