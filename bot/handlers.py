import os
import re
import telebot

from bot import upload_session, storage, keyboards, settings, database

def register_handlers(bot):
    
    # ─────────────────────────────────────────────
    # /start — deep link, clone, or welcome
    # ─────────────────────────────────────────────

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            token = args[1]
            
            if token == 'clone':
                if not getattr(bot, 'is_main_bot', False):
                    bot.send_message(message.chat.id, "❌ Cloning is only available on the main bot.")
                    return
                database.set_user_state(message.chat.id, "awaiting_bot_token")
                bot.send_message(message.chat.id, "🤖 Send me the Bot Token from @BotFather to clone this bot:")
                return
                
            upload_doc = storage.retrieve_upload_by_token(token)
            if upload_doc:
                count = upload_doc.get('item_count', len(upload_doc.get('items', [])))
                bot.send_message(
                    message.chat.id,
                    f"📦 File Collection\n\nItems: {count}",
                    reply_markup=keyboards.retrieve_keyboard(token)
                )
            else:
                bot.send_message(message.chat.id, "❌ Invalid or expired link.")
        else:
            msg = "Welcome to the File Store Bot!\nUse the menu below to navigate."
            is_main = getattr(bot, 'is_main_bot', False)
            if is_main:
                msg += "\n\nYou can also manage your bots using /mybots."
            bot.send_message(
                message.chat.id, 
                msg, 
                reply_markup=keyboards.main_menu_keyboard(is_main)
            )

    # ─────────────────────────────────────────────
    # Bot Cloning logic
    # ─────────────────────────────────────────────

    @bot.message_handler(commands=['clone'])
    @bot.message_handler(func=lambda m: m.text == "🤖 Clone Bot")
    def handle_clone_cmd(message):
        if getattr(bot, 'is_main_bot', False):
            database.set_user_state(message.chat.id, "awaiting_bot_token")
            bot.send_message(message.chat.id, "🤖 Send me the Bot Token from @BotFather to clone this bot:", reply_markup=keyboards.cancel_keyboard())
        else:
            bot.send_message(message.chat.id, "❌ This command is only available on the main bot.")
            
    @bot.message_handler(commands=['mybots'])
    def handle_mybots(message):
        if not getattr(bot, 'is_main_bot', False):
            return
            
        bots = database.get_cloned_bots(message.chat.id)
        if not bots:
            bot.send_message(message.chat.id, "You haven't cloned any bots yet. Use /clone to start!")
            return
            
        text = "🤖 **Your Cloned Bots:**\n\n"
        for b in bots:
            text += f"• @{b['username']}\n"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    # ─────────────────────────────────────────────
    # Send all files when user clicks the button
    # ─────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda call: call.data.startswith('send_all_'))
    def handle_send_all(call):
        token = call.data.split('_', 2)[2]
        upload_doc = storage.retrieve_upload_by_token(token)
        if upload_doc:
            bot.answer_callback_query(call.id, "Sending files...")
            storage.send_upload_items(bot, call.message.chat.id, upload_doc)
        else:
            bot.answer_callback_query(call.id, "❌ Invalid or expired link.", show_alert=True)

    # ─────────────────────────────────────────────
    # /upload
    # ─────────────────────────────────────────────

    @bot.message_handler(commands=['upload'])
    @bot.message_handler(func=lambda m: m.text == "📤 Upload Files")
    def handle_upload(message):
        upload_session.start_session(message.chat.id)
        user_settings = settings.get_user_settings(message.chat.id)
        grouping = user_settings.get("group_media", False)
        limit_note = "" if grouping else "\n\n⚠️ Group Media is OFF — max 20 items. Use /settings to increase."
        bot.send_message(
            message.chat.id,
            f"📤 Upload Mode\n\nSend me any files or messages you want to store.\nWhen finished, press ✅ Done.{limit_note}",
            reply_markup=keyboards.upload_keyboard()
        )

    @bot.message_handler(func=lambda m: m.text == "❌ Cancel")
    def handle_cancel(message):
        user_id = message.chat.id
        upload_session.delete_session(user_id)
        database.set_user_state(user_id, None)
        is_main = getattr(bot, 'is_main_bot', False)
        bot.send_message(user_id, "❌ Operation cancelled.", reply_markup=keyboards.main_menu_keyboard(is_main))

    @bot.message_handler(func=lambda m: m.text == "✅ Done")
    def handle_done(message):
        user_id = message.chat.id

        # Atomically lock the session — prevents double-processing on Telegram retries
        session = upload_session.pop_session(user_id)

        if not session:
            # Check if already processing (Telegram retry) — silently ignore
            existing = upload_session.get_session(user_id)
            if existing and existing.get('status') == 'processing':
                return
            bot.send_message(user_id, "⚠️ No active upload session. Use /upload to start.")
            return

        message_ids = session.get('message_ids', [])
        if not message_ids:
            upload_session.delete_session(user_id)
            bot.send_message(user_id, "⚠️ You haven't sent anything yet.\n\nSend at least one file, then press ✅ Done.")
            return

        is_main = getattr(bot, 'is_main_bot', False)
        bot.send_message(user_id, f"⏳ Storing {len(message_ids)} item(s)...", reply_markup=keyboards.main_menu_keyboard(is_main))

        result = storage.store_session(bot, user_id, message_ids)
        upload_session.delete_session(user_id)

        if result:
            token, count, failed = result
            
            # Use current bot's username instead of env var
            if not hasattr(bot, 'bot_username'):
                bot.bot_username = bot.get_me().username
            bot_username = bot.bot_username
            
            url = f"https://t.me/{bot_username}?start={token}"
            text = f"✅ Done!\n\n📦 Stored: {count} item(s)\n🔗 Link:\n{url}"
            if failed:
                text += f"\n\n⚠️ {failed} item(s) could not be copied."
            bot.send_message(user_id, text, reply_markup=keyboards.share_keyboard(token, bot_username))
        else:
            bot.send_message(user_id, "❌ Failed to store files. Please try again.")

    # ─────────────────────────────────────────────
    # /settings
    # ─────────────────────────────────────────────

    @bot.message_handler(commands=['settings'])
    @bot.message_handler(func=lambda m: m.text == "⚙️ Settings")
    def handle_settings(message):
        user_settings = settings.get_user_settings(message.chat.id)
        grouping = user_settings.get("group_media", False)
        status = "ON 🟢" if grouping else "OFF 🔴"
        text = (f"⚙️ Settings\n\n"
                f"Group Media: {status}\n\n"
                f"If ON — files are grouped into albums when storing (no upload limit).\n"
                f"If OFF — files stored individually, max 20 items per upload.")
        bot.send_message(message.chat.id, text, reply_markup=keyboards.settings_keyboard(grouping))

    @bot.callback_query_handler(func=lambda call: call.data == 'toggle_grouping')
    def handle_toggle_grouping(call):
        new_val = settings.toggle_group_media(call.message.chat.id)
        status = "ON 🟢" if new_val else "OFF 🔴"
        bot.answer_callback_query(call.id, f"Group Media {status}")
        text = (f"⚙️ Settings\n\n"
                f"Group Media: {status}\n\n"
                f"If ON — files are grouped into albums when storing (no upload limit).\n"
                f"If OFF — files stored individually, max 20 items per upload.")
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=keyboards.settings_keyboard(new_val))

    # ─────────────────────────────────────────────
    # /batch
    # ─────────────────────────────────────────────

    def extract_batch_info(message):
        if message.forward_from_chat:
            return message.forward_from_message_id, message.forward_from_chat.id
        if message.text:
            match = re.search(r't\.me/(?:c/)?([^/]+)/(\d+)', message.text.strip())
            if match:
                chat_str = match.group(1)
                msg_id = int(match.group(2))
                chat_id = int("-100" + chat_str) if chat_str.isdigit() else "@" + chat_str
                return msg_id, chat_id
        return None, None

    @bot.message_handler(commands=['batch'])
    @bot.message_handler(func=lambda m: m.text == "📦 Create Batch")
    def handle_batch(message):
        user_id = message.chat.id
        database.set_user_state(user_id, "batch_first")
        bot.send_message(user_id,
            "Forward the first message from your batch channel (with forward tag), "
            "or send its link (e.g. https://t.me/c/123456/1).", reply_markup=keyboards.cancel_keyboard())

    # ─────────────────────────────────────────────
    # Catch-all — handles file collection during upload + batch states + clone states
    # ─────────────────────────────────────────────

    @bot.message_handler(content_types=[
        'audio', 'document', 'photo', 'sticker', 'video',
        'video_note', 'voice', 'location', 'contact',
        'text', 'animation', 'poll', 'dice'
    ])
    def handle_all_messages(message):
        user_id = message.chat.id

        # Skip keyboard button texts
        if message.text in ["✅ Done", "❌ Cancel"]:
            return

        # ── State machine ──
        state, state_data = database.get_user_state(user_id)
        
        if state == "awaiting_bot_token" and getattr(bot, 'is_main_bot', False):
            if not message.text:
                return
            token = message.text.strip()
            
            bot_msg = bot.send_message(user_id, "⏳ Verifying bot token...")
            
            try:
                new_bot = telebot.TeleBot(token)
                bot_info = new_bot.get_me()
                
                base_url = (os.getenv('BASE_URL') or '').rstrip('/')
                if not base_url:
                    base_url = os.getenv('VERCEL_PROJECT_PRODUCTION_URL', '')
                    if base_url:
                        base_url = f"https://{base_url}"
                
                if not base_url:
                    bot.edit_message_text("❌ Server missing BASE_URL. Cannot set webhook.", user_id, bot_msg.message_id)
                    return
                    
                webhook_url = f"{base_url}/api?token={token}"
                secret_token = os.getenv('WEBHOOK_SECRET')
                if secret_token:
                    new_bot.set_webhook(url=webhook_url, secret_token=secret_token)
                else:
                    new_bot.set_webhook(url=webhook_url)
                    
                # Auto-setup commands for the cloned bot
                from telebot.types import BotCommand
                commands = [
                    BotCommand("start", "Start the bot"),
                    BotCommand("upload", "Start a new file upload session"),
                    BotCommand("batch", "Create a link from existing channel messages"),
                    BotCommand("settings", "Configure bot preferences")
                ]
                new_bot.set_my_commands(commands)
                
                database.add_cloned_bot(user_id, token, bot_info.username)
                database.set_user_state(user_id, None)
                
                bot.edit_message_text(f"✅ Bot cloned successfully!\n\nYour bot is now live at @{bot_info.username}.", user_id, bot_msg.message_id)
                bot.send_message(user_id, "Use the menu below to navigate:", reply_markup=keyboards.main_menu_keyboard(getattr(bot, 'is_main_bot', False)))
            except Exception as e:
                bot.edit_message_text(f"❌ Invalid token or error connecting to Telegram: {e}", user_id, bot_msg.message_id)
                database.set_user_state(user_id, None)
                bot.send_message(user_id, "Please try again.", reply_markup=keyboards.main_menu_keyboard(getattr(bot, 'is_main_bot', False)))
            return

        if state == "batch_first":
            msg_id, chat_id = extract_batch_info(message)
            if not msg_id:
                bot.send_message(user_id, "❌ Please forward a message from the channel or send a valid link.")
                return
            try:
                bot.get_chat(chat_id)
            except Exception:
                bot.send_message(user_id, "❌ I can't access that channel. Make sure I'm an admin there.")
                return
            database.set_user_state(user_id, "batch_last", {"first_id": msg_id, "chat_id": chat_id})
            bot.send_message(user_id, "Now forward the last message (or send its link).")
            return

        if state == "batch_last":
            msg_id, chat_id = extract_batch_info(message)
            if not msg_id:
                bot.send_message(user_id, "❌ Please forward a message or send a valid link.")
                return
            first_id = state_data.get('first_id')
            first_chat_id = state_data.get('chat_id')
            if chat_id != first_chat_id:
                bot.send_message(user_id, "❌ Both messages must be from the same channel.")
                return
            if first_id > msg_id:
                first_id, msg_id = msg_id, first_id
            ids = list(range(first_id, msg_id + 1))
            if len(ids) > 1000:
                bot.send_message(user_id, "❌ Range too large. Maximum 1000 messages per batch.")
                return
            token, count = storage.store_batch_session(user_id, ids, source_chat_id=chat_id)
            database.set_user_state(user_id, None)
            
            if not hasattr(bot, 'bot_username'):
                bot.bot_username = bot.get_me().username
            bot_username = bot.bot_username
            
            url = f"https://t.me/{bot_username}?start={token}"
            bot.send_message(user_id, f"✅ Batch created!\n\n📦 Items: {count}\n🔗 Link:\n{url}",
                             reply_markup=keyboards.share_keyboard(token, bot_username))
            return

        # ── Upload session collection ──
        session = upload_session.get_session(user_id)
        if not session or session.get('status') != 'uploading':
            return

        user_settings = settings.get_user_settings(user_id)
        grouping = user_settings.get("group_media", False)

        # When OFF: silently cap at 20, store bare message ID
        if not grouping:
            if len(session.get('message_ids', [])) >= 20:
                return
            upload_session.add_message(user_id, message.message_id)
            return

        # When ON: store metadata so storage.py can group into albums
        if message.photo:
            mt, fid = 'photo', message.photo[-1].file_id
        elif message.video:
            mt, fid = 'video', message.video.file_id
        elif message.document:
            mt, fid = 'document', message.document.file_id
        elif message.audio:
            mt, fid = 'audio', message.audio.file_id
        else:
            mt, fid = 'other', None

        upload_session.add_message(user_id, {
            "message_id": message.message_id,
            "media_type": mt,
            "file_id": fid
        })
