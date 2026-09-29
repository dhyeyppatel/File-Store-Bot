from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import os

def upload_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False, row_width=2)
    markup.add(KeyboardButton("✅ Done"), KeyboardButton("❌ Cancel"))
    return markup

def cancel_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("❌ Cancel"))
    return markup

def remove_keyboard():
    from telebot.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()

def share_keyboard(token, bot_username):
    markup = InlineKeyboardMarkup()
    url = f"https://t.me/{bot_username}?start={token}"
    share_url = f"https://t.me/share/url?url={url}"
    markup.add(InlineKeyboardButton("🔗 Open Files", url=url))
    markup.add(InlineKeyboardButton("📋 Share Link", url=share_url))
    
    main_bot = os.getenv('BOT_USERNAME')
    if main_bot:
        markup.add(InlineKeyboardButton("🤖 Clone This Bot", url=f"https://t.me/{main_bot}?start=clone"))
        
    return markup

def retrieve_keyboard(token):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📥 Send All", callback_data=f"send_all_{token}"))
    return markup
    
def settings_keyboard(is_grouped):
    markup = InlineKeyboardMarkup()
    btn_text = "Disable Grouping 🔴" if is_grouped else "Enable Grouping 🟢"
    markup.add(InlineKeyboardButton(btn_text, callback_data="toggle_grouping"))
    return markup

def main_menu_keyboard(is_main_bot=False):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📤 Upload Files"),
        KeyboardButton("📦 Create Batch")
    )
    if is_main_bot:
        markup.add(
            KeyboardButton("🤖 Clone Bot"),
            KeyboardButton("⚙️ Settings")
        )
    else:
        markup.add(
            KeyboardButton("⚙️ Settings")
        )
    return markup
