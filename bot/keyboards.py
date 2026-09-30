from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import os

def upload_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Done", callback_data="upload_done"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")
    )
    return markup

def cancel_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"))
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
    
def settings_keyboard(is_grouped, is_admin=False, mode="public"):
    markup = InlineKeyboardMarkup()
    btn_text = "Disable Grouping 🔴" if is_grouped else "Enable Grouping 🟢"
    markup.add(InlineKeyboardButton(btn_text, callback_data="toggle_grouping"))
    if is_admin:
        mode_text = "Make Public 🔓" if mode == "private" else "Make Private 🔒"
        markup.add(InlineKeyboardButton(mode_text, callback_data="toggle_main_mode"))
    return markup

def main_menu_keyboard(is_main_bot=False):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📤 Upload Files", callback_data="menu_upload"),
        InlineKeyboardButton("📦 Create Batch", callback_data="menu_batch")
    )
    if is_main_bot:
        markup.add(
            InlineKeyboardButton("🤖 Clone Bot", callback_data="menu_clone"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")
        )
    else:
        markup.add(
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")
        )
        main_bot = os.getenv('BOT_USERNAME')
        if main_bot:
            markup.add(InlineKeyboardButton("🤖 Create Your Own Bot", url=f"https://t.me/{main_bot}?start=clone"))
    return markup

def mybots_keyboard(bots):
    markup = InlineKeyboardMarkup(row_width=1)
    for b in bots:
        markup.add(InlineKeyboardButton(f"🤖 @{b['username']}", callback_data=f"clone_set_{str(b['_id'])}"))
    return markup

def clone_settings_keyboard(bot_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("START MSG", callback_data=f"clone_startmsg_{bot_id}"),
        InlineKeyboardButton("FORCE SUB", callback_data=f"clone_forcesub_{bot_id}")
    )
    markup.add(
        InlineKeyboardButton("MODERATORS", callback_data=f"clone_mods_{bot_id}"),
        InlineKeyboardButton("AUTO DELETE", callback_data=f"clone_autodel_{bot_id}")
    )
    markup.add(
        InlineKeyboardButton("NO FORWARD", callback_data=f"clone_nofwd_{bot_id}"),
        InlineKeyboardButton("ACCESS TOKEN", callback_data=f"clone_token_{bot_id}")
    )
    markup.add(
        InlineKeyboardButton("TRANSFER DB", callback_data=f"clone_db_{bot_id}"),
        InlineKeyboardButton("DEACTIVATE", callback_data=f"clone_deact_{bot_id}")
    )
    markup.add(
        InlineKeyboardButton("MODE", callback_data=f"clone_mode_{bot_id}"),
        InlineKeyboardButton("RESTART", callback_data=f"clone_restart_{bot_id}")
    )
    markup.add(
        InlineKeyboardButton("STATS", callback_data=f"clone_stats_{bot_id}"),
        InlineKeyboardButton("DELETE", callback_data=f"clone_delete_{bot_id}")
    )
    markup.add(
        InlineKeyboardButton("BACK", callback_data="mybots_back")
    )
    return markup

def force_sub_keyboard(channel_url, bot_username=None, original_text=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 Join Channel", url=channel_url))
    if original_text and bot_username and '/start ' in original_text:
        # Pass the original command back so the user can just click it after joining
        markup.add(InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{bot_username}?start={original_text.replace('/start ', '')}"))
    return markup
