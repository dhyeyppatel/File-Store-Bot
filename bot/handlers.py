from bot.telegram import bot
from bot import upload_session
from bot import storage
from bot import keyboards
import os
import telebot

@bot.message_handler(commands=['start'])
def handle_start(message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        # Deep link handling
        token = args[1]
        upload_doc = storage.retrieve_upload_by_token(token)
        if upload_doc:
            item_count = upload_doc['item_count']
            bot.send_message(
                message.chat.id,
                f"📦 File Collection\n\nItems: {item_count}",
                reply_markup=keyboards.retrieve_keyboard(token)
            )
        else:
            bot.send_message(message.chat.id, "❌ Invalid or expired link.")
    else:
        bot.send_message(
            message.chat.id,
            "Welcome to the File Store Bot!\nUse /upload to start uploading files."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('send_all_'))
def handle_send_all(call):
    token = call.data.split('_', 2)[2]
    upload_doc = storage.retrieve_upload_by_token(token)
    if upload_doc:
        bot.answer_callback_query(call.id, "Sending files...")
        storage.send_upload_items(call.message.chat.id, upload_doc)
    else:
        bot.answer_callback_query(call.id, "❌ Invalid or expired link.", show_alert=True)

@bot.message_handler(commands=['upload'])
def handle_upload(message):
    upload_session.start_session(message.chat.id)
    bot.send_message(
        message.chat.id,
        "📤 Upload Mode\n\nSend me any files, media, or messages you want to store.\n\nYou can send multiple items.\n\nWhen you're finished, press the button below.\n\nEverything will be stored together as one collection.",
        reply_markup=keyboards.upload_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "❌ Cancel")
def handle_cancel(message):
    upload_session.delete_session(message.chat.id)
    bot.send_message(
        message.chat.id,
        "❌ Upload cancelled.\n\nNothing was stored.",
        reply_markup=keyboards.remove_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "✅ Done")
def handle_done(message):
    user_id = message.chat.id
    session = upload_session.lock_session(user_id)
    
    if not session:
        # Already processing or no session
        bot.send_message(user_id, "⚠️ No active upload session.")
        return
        
    items = session.get('items', [])
    if not items:
        upload_session.start_session(user_id) # Unlock by recreating
        bot.send_message(user_id, "⚠️ You haven't uploaded anything yet.\n\nSend at least one file or message.")
        return
        
    bot.send_message(user_id, f"📦 Preparing your files...\n\nItems received: {len(session.get('items', []))}", reply_markup=keyboards.remove_keyboard())
    bot.send_message(user_id, "⏳ Large upload detected.\nYour files are being stored in batches.\nPlease wait...")
    
    # Get user setting
    user_settings = settings.get_user_settings(user_id)
    grouping = user_settings.get("group_media", False)
    
    # Store session
    result = storage.store_session(user_id, session.get('items', []), grouping)
    
    # Clean up session
    upload_session.delete_session(user_id)
    
    if result:
        token, count, failed_count = result
        bot_username = os.getenv('BOT_USERNAME', 'YourBot')
        url = f"https://t.me/{bot_username}?start={token}"
        
        message_text = f"✅ Upload complete!\n\n📦 Items successfully stored: {count}\n\n🔗 Your secure link:\n{url}"
        
        if failed_count > 0:
            message_text += f"\n\n⚠️ {failed_count} items failed to store due to Telegram's Strict Rate Limit (Max 20 items per minute for free bots). To store larger batches, please wait 1 minute between uploads."
            
        bot.send_message(
            user_id,
            message_text,
            reply_markup=keyboards.share_keyboard(token)
        )
    else:
        bot.send_message(user_id, "❌ Failed to store items. Telegram might have blocked the bot temporarily. Please try again later.")

from bot import settings

@bot.message_handler(commands=['settings'])
def handle_settings(message):
    user_settings = settings.get_user_settings(message.chat.id)
    grouping = user_settings.get("group_media", False)
    status = "ON 🟢" if grouping else "OFF 🔴"
    text = (f"⚙️ Settings\n\n"
            f"Group Media: {status}\n\n"
            f"If ON, the bot will group media into albums (up to 10 items) when storing, allowing you to bypass the 20-item rate limit by bundling them together.\n"
            f"If OFF, the bot will store them normally (max 20 per minute).")
            
    bot.send_message(
        message.chat.id, 
        text, 
        reply_markup=keyboards.settings_keyboard(grouping)
    )

@bot.callback_query_handler(func=lambda call: call.data == 'toggle_grouping')
def handle_toggle_grouping(call):
    new_val = settings.toggle_group_media(call.message.chat.id)
    status = "ON 🟢" if new_val else "OFF 🔴"
    bot.answer_callback_query(call.id, f"Group Media turned {status}")
    
    text = (f"⚙️ Settings\n\n"
            f"Group Media: {status}\n\n"
            f"If ON, the bot will group media into albums (up to 10 items) when storing, allowing you to bypass the 20-item rate limit by bundling them together.\n"
            f"If OFF, the bot will store them normally (max 20 per minute).")
            
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboards.settings_keyboard(new_val)
    )

def extract_media_info(message):
    if message.photo:
        return 'photo', message.photo[-1].file_id
    elif message.video:
        return 'video', message.video.file_id
    elif message.document:
        return 'document', message.document.file_id
    elif message.audio:
        return 'audio', message.audio.file_id
    elif message.text:
        return 'text', None
    return 'other', None

@bot.message_handler(content_types=['audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact', 'text', 'animation', 'poll', 'dice'])
def handle_all_messages(message):
    if message.text in ["✅ Done", "❌ Cancel"]:
        return # Handled by specific handlers
    
    user_id = message.chat.id
    
    # Check if session active
    session = upload_session.get_session(user_id)
    if not session or session.get('status') != 'uploading':
        return
        
    media_type, file_id = extract_media_info(message)
    item_data = {
        "message_id": message.message_id,
        "chat_id": user_id,
        "media_type": media_type,
        "file_id": file_id
    }
        
    # Add item to session
    upload_session.add_item_to_session(user_id, item_data)
