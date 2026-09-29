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
        
    message_ids = session.get('message_ids', [])
    if not message_ids:
        # Empty upload
        upload_session.start_session(user_id) # Unlock by recreating
        bot.send_message(user_id, "⚠️ You haven't uploaded anything yet.\n\nSend at least one file or message.")
        return
        
    bot.send_message(user_id, f"📦 Preparing your files...\n\nItems received: {len(message_ids)}", reply_markup=keyboards.remove_keyboard())
    bot.send_message(user_id, "📤 Storing files...")
    
    # Store session
    result = storage.store_session(user_id, message_ids)
    
    # Clean up session
    upload_session.delete_session(user_id)
    
    if result:
        token, count = result
        bot_username = os.getenv('BOT_USERNAME', 'YourBot')
        url = f"https://t.me/{bot_username}?start={token}"
        bot.send_message(
            user_id,
            f"✅ Upload complete!\n\n📦 Items: {count}\n\n🔗 Your secure link:\n{url}",
            reply_markup=keyboards.share_keyboard(token)
        )
    else:
        bot.send_message(user_id, "❌ Failed to store items.")

@bot.message_handler(content_types=['audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact', 'text', 'animation', 'poll', 'dice'])
def handle_all_messages(message):
    if message.text in ["✅ Done", "❌ Cancel"]:
        return # Handled by specific handlers
    
    user_id = message.chat.id
    
    # Check if session active
    session = upload_session.get_session(user_id)
    if not session or session.get('status') != 'uploading':
        # They are not in an upload session, ignore or notify
        # Let's not spam them if they just type hi, maybe just return
        return
        
    # Add message to session
    updated_session = upload_session.add_message_to_session(user_id, message.message_id)
    if updated_session:
        # Simply add message to session, no status updates needed per user request
        pass
