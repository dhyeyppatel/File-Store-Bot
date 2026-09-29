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
            item_count = upload_doc.get('processed_items', upload_doc.get('item_count', 0))
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
        # Check if it's already processing (Telegram retry) vs truly no session
        existing = upload_session.get_session(user_id)
        if existing and existing.get('status') == 'processing':
            # This is a Telegram webhook retry — silently ignore it
            return
        # Genuinely no session
        bot.send_message(user_id, "⚠️ No active upload session.")
        return
        
    items = session.get('items', [])
    if not items:
        upload_session.start_session(user_id) # Unlock by recreating
        bot.send_message(user_id, "⚠️ You haven't uploaded anything yet.\n\nSend at least one file or message.")
        return
    
    # Get user setting
    user_settings = settings.get_user_settings(user_id)
    grouping = user_settings.get("group_media", False)
    
    bot.send_message(user_id, f"📦 Storing {len(items)} item(s)...", reply_markup=keyboards.remove_keyboard())
    
    # Store session
    result = storage.store_session(user_id, items, grouping)
    
    # Clean up session
    upload_session.delete_session(user_id)
    
    if result:
        token, count, failed_count = result
        bot_username = os.getenv('BOT_USERNAME', 'YourBot')
        url = f"https://t.me/{bot_username}?start={token}"
        
        message_text = f"✅ Upload complete!\n\n📦 Items successfully stored: {count}\n\n🔗 Your secure link:\n{url}"
        
        if failed_count > 0:
            message_text += f"\n\n⚠️ {failed_count} item(s) could not be stored."
            
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
            f"If ON, the bot will group media into albums (up to 10 items) when storing.\n"
            f"If OFF, the bot will store them normally, but you are limited to a maximum of 20 items per upload. If you need to upload more than 20 items at once, please turn on Group Media.")
            
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
            f"If ON, the bot will group media into albums (up to 10 items) when storing.\n"
            f"If OFF, the bot will store them normally, but you are limited to a maximum of 20 items per upload. If you need to upload more than 20 items at once, please turn on Group Media.")
            
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

import re

def extract_batch_info(message):
    if message.forward_from_chat:
        return message.forward_from_message_id, message.forward_from_chat.id
    elif message.text:
        match = re.search(r't\.me/(?:c/)?([^/]+)/(\d+)', message.text.strip())
        if match:
            chat_str = match.group(1)
            msg_id = int(match.group(2))
            if chat_str.isdigit():
                chat_id = int("-100" + chat_str)
            else:
                chat_id = "@" + chat_str
            return msg_id, chat_id
    return None, None

from bot import database

@bot.message_handler(commands=['batch'])
def handle_batch(message):
    user_id = message.chat.id
    database.set_user_state(user_id, "batch_first")
    bot.send_message(
        user_id,
        "Forward The Batch First Message From your Batch Channel (With Forward Tag).. or Give Me Batch First Message link from your batch channel"
    )

@bot.message_handler(content_types=['audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact', 'text', 'animation', 'poll', 'dice'])
def handle_all_messages(message):
    user_id = message.chat.id
    
    # Check for batch states first
    state, state_data = database.get_user_state(user_id)
    if state == "batch_first":
        msg_id, chat_id = extract_batch_info(message)
        if not msg_id or not chat_id:
            bot.send_message(user_id, "❌ Please provide a valid forwarded message or link from a channel.")
            return
            
        try:
            bot.get_chat(chat_id)
        except Exception:
            bot.send_message(user_id, "❌ I cannot access this channel. Make sure I am added as an Admin there!")
            return
            
        database.set_user_state(user_id, "batch_last", {"first_id": msg_id, "chat_id": chat_id})
        bot.send_message(
            user_id,
            "Forward The Batch Last Message From Your Batch Channel (With Forward Tag).. or  Give Me Batch last message link from your batch channel"
        )
        return
    elif state == "batch_last":
        msg_id, chat_id = extract_batch_info(message)
        if not msg_id or not chat_id:
            bot.send_message(user_id, "❌ Please provide a valid forwarded message or link from a channel.")
            return
            
        first_id = state_data.get('first_id')
        first_chat_id = state_data.get('chat_id')
        last_id = msg_id
        
        if chat_id != first_chat_id:
            bot.send_message(user_id, "❌ The first and last messages must be from the same channel.")
            return
        
        if first_id > last_id:
            first_id, last_id = last_id, first_id
            
        ids = list(range(first_id, last_id + 1))
        
        # Protect against massive ranges
        if len(ids) > 1000:
            bot.send_message(user_id, "❌ Range is too large. Maximum 1000 items per batch.")
            return
            
        token, count = storage.store_batch_session(user_id, ids, source_chat_id=chat_id)
        database.set_user_state(user_id, None)
        
        bot_username = os.getenv('BOT_USERNAME', 'YourBot')
        url = f"https://t.me/{bot_username}?start={token}"
        bot.send_message(
            user_id, 
            f"✅ Batch created!\n\n📦 Items: {count}\n\n🔗 Your secure link:\n{url}",
            reply_markup=keyboards.share_keyboard(token)
        )
        return

    if message.text in ["✅ Done", "❌ Cancel"]:
        return # Handled by specific handlers
    
    user_id = message.chat.id
    
    # Check if session active
    session = upload_session.get_session(user_id)
    if not session or session.get('status') != 'uploading':
        return
        
    # Get user setting to check limit
    user_settings = settings.get_user_settings(user_id)
    grouping = user_settings.get("group_media", False)
    
    if not grouping:
        # Silently ignore messages past 20 as instructed
        if len(session.get('items', [])) >= 20:
            return
        # Store bare integer message_id when OFF to avoid live metadata extraction processing
        upload_session.add_item_to_session(user_id, message.message_id)
    else:
        # Extract live metadata for albums when ON
        media_type, file_id = extract_media_info(message)
        item_data = {
            "message_id": message.message_id,
            "chat_id": user_id,
            "media_type": media_type,
            "file_id": file_id
        }
        # Add dictionary to session
        upload_session.add_item_to_session(user_id, item_data)
