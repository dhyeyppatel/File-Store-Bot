import os
import re
import telebot

from bot import upload_session, storage, keyboards, settings, database

def check_permissions(bot, message, action="use"):
    user_id = message.chat.id
    
    if getattr(bot, 'is_main_bot', False):
        if action == "upload":
            main_settings = settings.get_global_settings()
            if main_settings.get("mode") == "private":
                admin_ids = [int(i.strip()) for i in os.getenv('ADMIN_IDS', '').split(',') if i.strip()]
                if user_id not in admin_ids:
                    bot.send_message(user_id, "❌ The main bot is in private mode. Only admins can upload files.")
                    return False
        return True
    
    clone_info = database.get_cloned_bot_by_token(bot.token)
    if not clone_info:
        return True
        
    if clone_info.get("deactivated", False):
        bot.send_message(user_id, "❌ This bot has been deactivated by its owner.")
        return False
        
    if action == "upload":
        if clone_info.get("mode", "public") == "private":
            if user_id == clone_info.get('owner_id'):
                return True
            mods = clone_info.get('moderators', [])
            if user_id in mods:
                return True
            bot.send_message(user_id, "❌ This bot is in private mode. You do not have permission to upload files.")
            return False
        return True
        
    if action == "use":
        force_sub = clone_info.get('force_sub')
        if force_sub:
            try:
                member = bot.get_chat_member(force_sub, user_id)
                if member.status in ['left', 'kicked']:
                    bot_username = clone_info.get('username')
                    if str(force_sub).startswith('-100'):
                        url = bot.export_chat_invite_link(force_sub)
                    else:
                        url = f"https://t.me/{str(force_sub).replace('@', '')}"
                        
                    bot.send_message(
                        user_id, 
                        f"📢 You must join our channel to use this bot!",
                        reply_markup=keyboards.force_sub_keyboard(url, bot_username, message.text)
                    )
                    return False
            except telebot.apihelper.ApiTelegramException as e:
                # If an error happens (e.g. invalid channel ID, bot not admin), we should NOT let them pass!
                bot.send_message(
                    user_id,
                    f"❌ **Force Sub Error** ❌\n\nThis bot's Force Sub channel is misconfigured or the bot is not an admin in it.\n\n`{e.result.text if hasattr(e, 'result') else str(e)}`\n\nPlease contact the bot owner to fix this."
                )
                return False
                
    return True

def register_handlers(bot):
    
    # ─────────────────────────────────────────────
    # /start — deep link, clone, or welcome
    # ─────────────────────────────────────────────

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        if not getattr(bot, 'is_main_bot', False):
            database.track_clone_user(bot.token, message.chat.id)
            
        if not check_permissions(bot, message, "use"):
            return
            
        args = message.text.split(maxsplit=1)
        if len(args) > 1:
            token = args[1]
            
            if token == 'clone':
                if not getattr(bot, 'is_main_bot', False):
                    bot.send_message(message.chat.id, "❌ Cloning is only available on the main bot.")
                    return
                database.set_user_state(message.chat.id, "awaiting_bot_token")
                bot.send_message(message.chat.id, "🤖 Send me the Bot Token from @BotFather to clone this bot:", reply_markup=keyboards.cancel_keyboard())
                return
                
            if token == 'mybots':
                handle_mybots(message)
                return
                
            if token.startswith('verify_'):
                parts = token.split('_', 2)
                
                # Format: verify_USERID_FILETOKEN
                if len(parts) == 3:
                    target_user = parts[1]
                    original_token = parts[2]
                    
                    if str(message.chat.id) == target_user:
                        if not getattr(bot, 'is_main_bot', False):
                            clone_info = database.get_cloned_bot_by_token(bot.token)
                            if clone_info:
                                val = clone_info.get("shortener_validity", 24)
                                database.set_user_verified(message.chat.id, bot.token, val)
                                bot.send_message(message.chat.id, "✅ You have been successfully verified!")
                    else:
                        bot.send_message(message.chat.id, "❌ This verification link is invalid or belongs to another user.")
                else:
                    original_token = parts[1]
                    
                token = original_token
                
            upload_doc = storage.retrieve_upload_by_token(token)
            if upload_doc:
                # Check shortener
                if not getattr(bot, 'is_main_bot', False):
                    clone_info = database.get_cloned_bot_by_token(bot.token)
                    if clone_info and clone_info.get("shortener_status"):
                        if not database.is_user_verified(message.chat.id, bot.token):
                            api_url = clone_info.get("shortener_api_url")
                            api_key = clone_info.get("shortener_api_key")
                            if api_url and api_key:
                                import requests
                                import urllib.parse
                                dest_url = f"https://t.me/{bot.get_me().username}?start=verify_{message.chat.id}_{token}"
                                try:
                                    res = requests.get(f"{api_url}?api={api_key}&url={urllib.parse.quote(dest_url)}").json()
                                    short_url = res.get("shortenedUrl")
                                except:
                                    short_url = None
                                    
                                if short_url:
                                    tutorial = clone_info.get("shortener_tutorial")
                                    bot.send_message(
                                        message.chat.id,
                                        "🔒 **Verification Required**\n\nPlease verify your token to access this file.\nClick the link below and complete the steps.",
                                        parse_mode="Markdown",
                                        reply_markup=keyboards.shortener_verify_keyboard(short_url, tutorial)
                                    )
                                    return

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
            
    @bot.callback_query_handler(func=lambda call: call.data == 'menu_clone')
    def handle_menu_clone(call):
        bot.answer_callback_query(call.id)
        handle_clone_cmd(call.message)
            
    @bot.message_handler(commands=['mybots'])
    def handle_mybots(message):
        if not getattr(bot, 'is_main_bot', False):
            return
            
        bots = database.get_cloned_bots(message.chat.id)
        if not bots:
            bot.send_message(message.chat.id, "You haven't cloned any bots yet. Use /clone to start!")
            return
            
        text = "🤖 **Your Cloned Bots:**\n\nSelect a bot below to customize its settings:"
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboards.mybots_keyboard(bots))

    @bot.callback_query_handler(func=lambda call: call.data == 'mybots_back')
    def handle_mybots_back(call):
        bots = database.get_cloned_bots(call.message.chat.id)
        if not bots:
            bot.edit_message_text("You haven't cloned any bots yet. Use /clone to start!", call.message.chat.id, call.message.message_id)
            return
            
        text = "🤖 **Your Cloned Bots:**\n\nSelect a bot below to customize its settings:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=keyboards.mybots_keyboard(bots))

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clone_set_'))
    def handle_clone_settings(call):
        bot_id = call.data.split('_', 2)[2]
        bots = database.get_cloned_bots(call.message.chat.id)
        
        selected_bot = next((b for b in bots if str(b['_id']) == bot_id), None)
        if not selected_bot:
            bot.answer_callback_query(call.id, "Bot not found.", show_alert=True)
            return
            
        text = f"🪄 **Customize Clone**\n\n➔ *Name:* @{selected_bot['username']}\n\nConfigure Your Clone Settings Using Given Buttons"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=keyboards.clone_settings_keyboard(bot_id))

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clone_') and 'clone_set_' not in call.data and 'mybots' not in call.data)
    def handle_clone_action(call):
        # Allow pass-through for other specific clone action handlers, this is just a stub for unimplemented ones
        action = call.data.split('_')[1]
        
        # Check if we should stub it
        implemented_actions = ['forcesub', 'mods', 'mode', 'nofwd', 'deact', 'db', 'token', 'delete', 'confirmdel', 'cancel', 'restart', 'ignore', 'shortener', 'stats'] 
        
        if action not in implemented_actions and action != 'settings':
            bot.answer_callback_query(call.id, "Feature coming soon!", show_alert=True)
            return
            
        if action == 'ignore':
            bot.answer_callback_query(call.id)
            return
            
        bot_id = call.data.split('_', 2)[2]
        
        if action == 'mode':
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if selected_bot:
                token = selected_bot['token']
                current = selected_bot.get('mode', 'public')
                new_val = 'private' if current == 'public' else 'public'
                database.update_cloned_bot_setting(token, 'mode', new_val)
                bot.answer_callback_query(call.id, f"Mode changed to {new_val.upper()}!", show_alert=True)
            return
            
        if action == 'nofwd':
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if selected_bot:
                token = selected_bot['token']
                current = selected_bot.get('no_forward', False)
                new_val = not current
                database.update_cloned_bot_setting(token, 'no_forward', new_val)
                status = "ENABLED 🟢" if new_val else "DISABLED 🔴"
                bot.answer_callback_query(call.id, f"No Forward is now {status}", show_alert=True)
            return

        if action == 'deact':
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if selected_bot:
                token = selected_bot['token']
                current = selected_bot.get('deactivated', False)
                new_val = not current
                database.update_cloned_bot_setting(token, 'deactivated', new_val)
                status = "DEACTIVATED 🛑" if new_val else "ACTIVATED 🟢"
                bot.answer_callback_query(call.id, f"Bot is now {status}", show_alert=True)
            return
            
        if action == 'forcesub':
            database.set_user_state(call.message.chat.id, "awaiting_force_sub", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Choose your force sub channel using appeared buttons.\nOr forward any message from the channel.\n\nSend /disable to turn it off.\n\nMake sure your bot is admin in that channel!", reply_markup=keyboards.force_sub_select_keyboard())
            bot.answer_callback_query(call.id)
            
        elif action == 'mods':
            database.set_user_state(call.message.chat.id, "awaiting_mods", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Send a list of User IDs (separated by space) to set as moderators.\n\nSend /clear to remove all moderators.", reply_markup=keyboards.cancel_keyboard())
            bot.answer_callback_query(call.id)
            
        elif action == 'stats':
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if selected_bot:
                total_uploads = selected_bot.get("total_uploads", 0)
                total_users = database.get_clone_user_count(selected_bot["token"])
                
                text = (f"📊 **Clone Bot Statistics**\n\n"
                        f"👥 Total Users: `{total_users}`\n"
                        f"📤 Total Uploads: `{total_uploads}`")
                
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data=f"clone_cancel_{bot_id}"))
                
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
            return
            
        elif action == 'db':
            database.set_user_state(call.message.chat.id, "awaiting_db_channel", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Send the Database/Storage Channel ID (e.g. -100123456789) where this bot should store files.\n\n⚠️ Ensure your clone bot is an admin in that channel!", reply_markup=keyboards.cancel_keyboard())
            bot.answer_callback_query(call.id)
            
        elif action == 'token':
            database.set_user_state(call.message.chat.id, "awaiting_new_token", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Send the new Bot Token from @BotFather to update this bot:", reply_markup=keyboards.cancel_keyboard())
            bot.answer_callback_query(call.id)
            
        elif action == 'delete':
            bot.send_message(call.message.chat.id, "⚠️ Are you sure you want to completely delete this clone bot? This action cannot be undone.", reply_markup=keyboards.confirm_delete_keyboard(bot_id))
            bot.answer_callback_query(call.id)
            
        elif action == 'confirmdel':
            database.delete_cloned_bot_by_id(bot_id)
            bot.edit_message_text("✅ Clone bot has been successfully deleted.", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "Bot Deleted")
            
        elif action == 'cancel':
            bot.edit_message_text("Customize Clone Settings:", call.message.chat.id, call.message.message_id, reply_markup=keyboards.clone_settings_keyboard(bot_id))
            bot.answer_callback_query(call.id, "Cancelled")
            
        elif action == 'restart':
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if selected_bot:
                import os
                import telebot
                token = selected_bot['token']
                base_url = (os.getenv('BASE_URL') or '').rstrip('/')
                if not base_url:
                    base_url = f"https://{os.getenv('VERCEL_PROJECT_PRODUCTION_URL', '')}"
                
                if base_url and '://' in base_url:
                    try:
                        new_bot = telebot.TeleBot(token)
                        webhook_url = f"{base_url}/api?token={token}"
                        secret_token = os.getenv('WEBHOOK_SECRET')
                        if secret_token:
                            new_bot.set_webhook(url=webhook_url, secret_token=secret_token)
                        else:
                            new_bot.set_webhook(url=webhook_url)
                        bot.answer_callback_query(call.id, "✅ Bot Restarted Successfully!", show_alert=True)
                    except Exception as e:
                        bot.answer_callback_query(call.id, f"❌ Failed to restart: {e}", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "❌ BASE_URL not configured.", show_alert=True)
                    
        elif action == 'shortener':
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if selected_bot:
                status = selected_bot.get("shortener_status", False)
                status_text = "Enabled ✅" if status else "Disabled ❌"
                url = selected_bot.get("shortener_api_url", "Not Set")
                key = selected_bot.get("shortener_api_key", "Not Set")
                val = selected_bot.get("shortener_validity", 24)
                
                text = (f"**Shortener Settings**\n\n"
                        f"Users need to pass a shortened link to gain special access to messages from all clone shareable links. "
                        f"This access will be valid for the next custom validity period.\n\n"
                        f"- Status: {status_text}\n"
                        f"- API URL: `{url}`\n"
                        f"- API Key: `{key}`\n"
                        f"- Validity: `{val} hours`")
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=keyboards.shortener_settings_keyboard(bot_id, selected_bot))
                bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('short_'))
    def handle_shortener_action(call):
        action = call.data.split('_')[1]
        bot_id = call.data.split('_', 2)[2]
        
        selected_bot = database.get_cloned_bot_by_id(bot_id)
        if not selected_bot:
            bot.answer_callback_query(call.id, "Bot not found.", show_alert=True)
            return
            
        token = selected_bot['token']
        
        if action == 'back':
            bot.edit_message_text("Customize Clone Settings:", call.message.chat.id, call.message.message_id, reply_markup=keyboards.clone_settings_keyboard(bot_id))
            bot.answer_callback_query(call.id)
            return
            
        elif action == 'toggle':
            current = selected_bot.get("shortener_status", False)
            database.update_cloned_bot_setting(token, "shortener_status", not current)
            bot.answer_callback_query(call.id, f"Shortener {'Enabled' if not current else 'Disabled'}")
            
            # Refresh menu
            selected_bot["shortener_status"] = not current
            status_text = "Enabled ✅" if not current else "Disabled ❌"
            url = selected_bot.get("shortener_api_url", "Not Set")
            key = selected_bot.get("shortener_api_key", "Not Set")
            val = selected_bot.get("shortener_validity", 24)
            text = (f"**Shortener Settings**\n\n"
                    f"Users need to pass a shortened link to gain special access to messages from all clone shareable links. "
                    f"This access will be valid for the next custom validity period.\n\n"
                    f"- Status: {status_text}\n"
                    f"- API URL: `{url}`\n"
                    f"- API Key: `{key}`\n"
                    f"- Validity: `{val} hours`")
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=keyboards.shortener_settings_keyboard(bot_id, selected_bot))
            return
            
        elif action == 'apiurl':
            database.set_user_state(call.message.chat.id, "awaiting_short_apiurl", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Send your shortener site API URL (e.g. `https://earn4link.in/api`).", parse_mode="Markdown", reply_markup=keyboards.cancel_keyboard())
            bot.answer_callback_query(call.id)
            
        elif action == 'apikey':
            database.set_user_state(call.message.chat.id, "awaiting_short_apikey", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Send your shortener site API Key.", reply_markup=keyboards.cancel_keyboard())
            bot.answer_callback_query(call.id)
            
        elif action == 'validity':
            database.set_user_state(call.message.chat.id, "awaiting_short_validity", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Send the validity period in hours (e.g. `24`).", parse_mode="Markdown", reply_markup=keyboards.cancel_keyboard())
            bot.answer_callback_query(call.id)
            
        elif action == 'tutorial':
            database.set_user_state(call.message.chat.id, "awaiting_short_tutorial", {"bot_id": bot_id})
            bot.send_message(call.message.chat.id, "Send the tutorial URL (e.g. a Telegram post or YouTube video link on how to bypass).", reply_markup=keyboards.cancel_keyboard())
            bot.answer_callback_query(call.id)

    # ─────────────────────────────────────────────
    # Send all files when user clicks the button
    # ─────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda call: call.data.startswith('send_all_'))
    def handle_send_all(call):
        # We simulate a message context to check permissions using call.message
        # But we need to make sure the chat ID is correct
        if not check_permissions(bot, call.message, "use"):
            bot.answer_callback_query(call.id, "Please join the required channel first.", show_alert=True)
            return
            
        token = call.data.split('_', 2)[2]
        upload_doc = storage.retrieve_upload_by_token(token)
        if upload_doc:
            bot.answer_callback_query(call.id, "Sending files...")
            
            # Check if NO FORWARD is enabled for this bot
            protect = False
            if not getattr(bot, 'is_main_bot', False):
                clone_info = database.get_cloned_bot_by_token(bot.token)
                if clone_info:
                    protect = clone_info.get("no_forward", False)
                    
            storage.send_upload_items(bot, call.message.chat.id, upload_doc, protect_content=protect)
        else:
            bot.answer_callback_query(call.id, "❌ Invalid or expired link.", show_alert=True)

    # ─────────────────────────────────────────────
    # /upload
    # ─────────────────────────────────────────────

    @bot.message_handler(commands=['upload'])
    @bot.message_handler(func=lambda m: m.text == "📤 Upload Files")
    def handle_upload(message):
        if not check_permissions(bot, message, "upload"):
            return
            
        upload_session.start_session(message.chat.id)
        user_settings = settings.get_user_settings(message.chat.id)
        grouping = user_settings.get("group_media", False)
        limit_note = "" if grouping else "\n\n⚠️ Group Media is OFF — max 20 items. Use /settings to increase."
        bot.send_message(
            message.chat.id,
            f"📤 Upload Mode\n\nSend me any files or messages you want to store.\nWhen finished, press ✅ Done.{limit_note}",
            reply_markup=keyboards.upload_keyboard()
        )

    @bot.callback_query_handler(func=lambda call: call.data == 'menu_upload')
    def handle_menu_upload(call):
        bot.answer_callback_query(call.id)
        handle_upload(call.message)

    @bot.message_handler(func=lambda m: m.text == "❌ Cancel")
    def handle_cancel(message):
        user_id = message.chat.id
        upload_session.delete_session(user_id)
        database.set_user_state(user_id, None)
        is_main = getattr(bot, 'is_main_bot', False)
        bot.send_message(user_id, "❌ Operation cancelled.", reply_markup=keyboards.remove_keyboard())
        bot.send_message(user_id, "Menu activated 👇", reply_markup=keyboards.main_menu_keyboard(is_main))

    @bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
    def handle_cancel_action(call):
        bot.answer_callback_query(call.id)
        handle_cancel(call.message)

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
            bot.send_message(user_id, "⚠️ You haven't sent anything yet.\n\nSend at least one file, then press ✅ Done.", reply_markup=keyboards.remove_keyboard())
            return

        is_main = getattr(bot, 'is_main_bot', False)
        bot.send_message(user_id, f"⏳ Storing {len(message_ids)} item(s)...", reply_markup=keyboards.remove_keyboard())

        result = storage.store_session(bot, user_id, message_ids)
        upload_session.delete_session(user_id)

        if result:
            token, count, failed = result
            
            if not is_main:
                database.increment_clone_upload(bot.token)
                
            
            # Use current bot's username instead of env var
            if not hasattr(bot, 'bot_username'):
                bot.bot_username = bot.get_me().username
            bot_username = bot.bot_username
            
            url = f"https://t.me/{bot_username}?start={token}"
            text = f"✅ Done!\n\n📦 Stored: {count} item(s)\n🔗 Link:\n{url}"
            if failed:
                text += f"\n\n⚠️ {failed} item(s) could not be copied."
            bot.send_message(user_id, text, reply_markup=keyboards.share_keyboard(token, bot_username))
            bot.send_message(user_id, "Menu activated 👇", reply_markup=keyboards.main_menu_keyboard(is_main))
        else:
            bot.send_message(user_id, "❌ Failed to store files. Please try again.")
            bot.send_message(user_id, "Menu activated 👇", reply_markup=keyboards.main_menu_keyboard(is_main))

    @bot.callback_query_handler(func=lambda call: call.data == 'upload_done')
    def handle_upload_done_action(call):
        bot.answer_callback_query(call.id)
        handle_done(call.message)

    # ─────────────────────────────────────────────
    # /settings
    # ─────────────────────────────────────────────

    @bot.message_handler(commands=['settings'])
    @bot.message_handler(func=lambda m: m.text == "⚙️ Settings")
    def handle_settings(message):
        user_settings = settings.get_user_settings(message.chat.id)
        grouping = user_settings.get("group_media", False)
        status = "ON 🟢" if grouping else "OFF 🔴"
        
        is_main = getattr(bot, 'is_main_bot', False)
        is_admin = False
        mode = "public"
        
        if is_main:
            admin_ids = [int(i.strip()) for i in os.getenv('ADMIN_IDS', '').split(',') if i.strip()]
            if message.chat.id in admin_ids:
                is_admin = True
                main_settings = settings.get_global_settings()
                mode = main_settings.get("mode", "public")
        else:
            clone_info = database.get_cloned_bot_by_token(bot.token)
            if clone_info and message.chat.id == clone_info.get('owner_id'):
                is_admin = True
                mode = clone_info.get("mode", "public")
                
        text = (f"⚙️ Settings\n\n"
                f"Group Media: {status}\n\n"
                f"If ON — files are grouped into albums when storing (no upload limit).\n"
                f"If OFF — files stored individually, max 20 items per upload.")
        if is_admin:
            text += f"\n\nBot Mode: {mode.upper()}"
            
        bot.send_message(message.chat.id, text, reply_markup=keyboards.settings_keyboard(grouping, is_admin, mode))

    @bot.callback_query_handler(func=lambda call: call.data == 'menu_settings')
    def handle_menu_settings(call):
        bot.answer_callback_query(call.id)
        handle_settings(call.message)

    @bot.callback_query_handler(func=lambda call: call.data == 'toggle_grouping')
    def handle_toggle_grouping(call):
        new_val = settings.toggle_group_media(call.message.chat.id)
        status = "ON 🟢" if new_val else "OFF 🔴"
        
        is_main = getattr(bot, 'is_main_bot', False)
        is_admin = False
        mode = "public"
        
        if is_main:
            admin_ids = [int(i.strip()) for i in os.getenv('ADMIN_IDS', '').split(',') if i.strip()]
            if call.message.chat.id in admin_ids:
                is_admin = True
                main_settings = settings.get_global_settings()
                mode = main_settings.get("mode", "public")
        else:
            clone_info = database.get_cloned_bot_by_token(bot.token)
            if clone_info and call.message.chat.id == clone_info.get('owner_id'):
                is_admin = True
                mode = clone_info.get("mode", "public")
                
        bot.answer_callback_query(call.id, f"Group Media {status}")
        text = (f"⚙️ Settings\n\n"
                f"Group Media: {status}\n\n"
                f"If ON — files are grouped into albums when storing (no upload limit).\n"
                f"If OFF — files stored individually, max 20 items per upload.")
        if is_admin:
            text += f"\n\nBot Mode: {mode.upper()}"
            
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=keyboards.settings_keyboard(new_val, is_admin, mode))

    @bot.callback_query_handler(func=lambda call: call.data == 'toggle_main_mode')
    def handle_toggle_main_mode(call):
        is_main = getattr(bot, 'is_main_bot', False)
        new_mode = "public"
        
        if is_main:
            new_mode = settings.toggle_main_bot_mode()
        else:
            clone_info = database.get_cloned_bot_by_token(bot.token)
            if clone_info:
                current_mode = clone_info.get("mode", "public")
                new_mode = "private" if current_mode == "public" else "public"
                database.update_cloned_bot_setting(bot.token, 'mode', new_mode)
        
        user_settings = settings.get_user_settings(call.message.chat.id)
        grouping = user_settings.get("group_media", False)
        status = "ON 🟢" if grouping else "OFF 🔴"
        
        bot.answer_callback_query(call.id, f"Mode changed to {new_mode.upper()}!")
        text = (f"⚙️ Settings\n\n"
                f"Group Media: {status}\n\n"
                f"If ON — files are grouped into albums when storing (no upload limit).\n"
                f"If OFF — files stored individually, max 20 items per upload.\n\n"
                f"Bot Mode: {new_mode.upper()}")
                
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=keyboards.settings_keyboard(grouping, True, new_mode))

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
        if not check_permissions(bot, message, "upload"):
            return
            
        user_id = message.chat.id
        database.set_user_state(user_id, "batch_first")
        bot.send_message(user_id,
            "Forward the first message from your batch channel (with forward tag), "
            "or send its link (e.g. https://t.me/c/123456/1).", reply_markup=keyboards.cancel_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data == 'menu_batch')
    def handle_menu_batch(call):
        bot.answer_callback_query(call.id)
        handle_batch(call.message)

    # ─────────────────────────────────────────────
    # Catch-all — handles file collection during upload + batch states + clone states
    # ─────────────────────────────────────────────

    @bot.message_handler(content_types=[
        'audio', 'document', 'photo', 'sticker', 'video',
        'video_note', 'voice', 'location', 'contact',
        'text', 'animation', 'poll', 'dice', 'chat_shared', 'user_shared'
    ])
    def handle_all_messages(message):
        user_id = message.chat.id

        # Skip keyboard button texts
        if message.text in ["✅ Done", "❌ Cancel"]:
            return

        # ── State machine ──
        state, state_data = database.get_user_state(user_id)
        
        if state in ["awaiting_short_apiurl", "awaiting_short_apikey", "awaiting_short_validity", "awaiting_short_tutorial"]:
            if not message.text:
                return
            val = message.text.strip()
            bot_id = state_data.get('bot_id')
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if not selected_bot:
                return
                
            token = selected_bot['token']
            if state == "awaiting_short_apiurl":
                if not val.startswith("http"):
                    val = "https://" + val
                database.update_cloned_bot_setting(token, "shortener_api_url", val)
                bot.send_message(user_id, "✅ API URL updated.")
            elif state == "awaiting_short_apikey":
                database.update_cloned_bot_setting(token, "shortener_api_key", val)
                bot.send_message(user_id, "✅ API Key updated.")
            elif state == "awaiting_short_validity":
                database.update_cloned_bot_setting(token, "shortener_validity", val)
                bot.send_message(user_id, "✅ Validity updated.")
            elif state == "awaiting_short_tutorial":
                database.update_cloned_bot_setting(token, "shortener_tutorial", val)
                bot.send_message(user_id, "✅ Tutorial URL updated.")
                
            database.set_user_state(user_id, None)
            
            # Send back to shortener settings
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            status = selected_bot.get("shortener_status", False)
            status_text = "Enabled ✅" if status else "Disabled ❌"
            url = selected_bot.get("shortener_api_url", "Not Set")
            key = selected_bot.get("shortener_api_key", "Not Set")
            val = selected_bot.get("shortener_validity", 24)
            text = (f"**Shortener Settings**\n\n"
                    f"Users need to pass a shortened link to gain special access to messages from all clone shareable links. "
                    f"This access will be valid for the next custom validity period.\n\n"
                    f"- Status: {status_text}\n"
                    f"- API URL: `{url}`\n"
                    f"- API Key: `{key}`\n"
                    f"- Validity: `{val} hours`")
            bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=keyboards.shortener_settings_keyboard(bot_id, selected_bot))
            return

        if state == "awaiting_force_sub":
            bot_id = state_data.get('bot_id')
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if not selected_bot:
                return
            token = selected_bot['token']
            
            if message.text and message.text.strip() == '/disable':
                database.update_cloned_bot_setting(token, 'force_sub', None)
                bot.send_message(user_id, "✅ Force Sub has been disabled.", reply_markup=keyboards.remove_keyboard())
            else:
                channel = None
                
                # Check for chat_shared / user_shared in message.json
                shared_chat = message.json.get('chat_shared', {}) or message.json.get('user_shared', {})
                if shared_chat:
                    channel = str(shared_chat.get('chat_id', shared_chat.get('user_id')))
                # Check for forward_from_chat
                elif getattr(message, 'forward_from_chat', None):
                    channel = str(message.forward_from_chat.id)
                elif message.text:
                    channel = message.text.strip()
                    # Sanitize text input
                    if "t.me/" in channel:
                        channel = "@" + channel.split("t.me/")[-1].strip().strip("/")
                    elif channel.startswith("@") or channel.startswith("-100"):
                        pass
                    elif channel.isdigit() or (channel.startswith("-") and channel[1:].isdigit()):
                        if not channel.startswith("-100"):
                            channel = "-100" + channel.lstrip("-")
                    else:
                        channel = "@" + channel
                
                if not channel:
                    return
                    
                database.update_cloned_bot_setting(token, 'force_sub', channel)
                bot.send_message(user_id, f"✅ Force Sub has been set to: {channel}\n\nMake sure your cloned bot is an admin in this channel!", reply_markup=keyboards.remove_keyboard())
            
            database.set_user_state(user_id, None)
            
            # Send them back to the settings menu
            bot.send_message(user_id, "Customize Clone Settings:", reply_markup=keyboards.clone_settings_keyboard(bot_id))
            return
            
        if state == "awaiting_mods":
            if not message.text:
                return
            bot_id = state_data.get('bot_id')
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if not selected_bot:
                return
            token = selected_bot['token']
            if message.text.strip() == '/clear':
                database.update_cloned_bot_setting(token, 'moderators', [])
                bot.send_message(user_id, "✅ All moderators have been removed.")
            else:
                try:
                    mods = [int(x.strip()) for x in message.text.split()]
                    database.update_cloned_bot_setting(token, 'moderators', mods)
                    bot.send_message(user_id, f"✅ Set {len(mods)} moderators.")
                except ValueError:
                    bot.send_message(user_id, "❌ Invalid format. Please send a list of User IDs (numbers only).")
                    return
            database.set_user_state(user_id, None)
            
            bot.send_message(user_id, "Customize Clone Settings:", reply_markup=keyboards.clone_settings_keyboard(bot_id))
            return
        
        if state == "awaiting_bot_token" and getattr(bot, 'is_main_bot', False):
            if not message.text:
                return
            token = message.text.strip()
            
            if database.is_bot_cloned(token):
                bot.send_message(user_id, "❌ This bot token is already cloned!")
                database.set_user_state(user_id, None)
                return
            
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
            
        if state == "awaiting_new_token":
            if not message.text:
                return
            new_token = message.text.strip()
            
            if database.is_bot_cloned(new_token):
                bot.send_message(user_id, "❌ This bot token is already cloned!")
                database.set_user_state(user_id, None)
                return
                
            bot_id = state_data.get('bot_id')
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if not selected_bot:
                return
                
            bot_msg = bot.send_message(user_id, "⏳ Verifying new bot token...")
            
            try:
                import telebot
                import os
                new_bot = telebot.TeleBot(new_token)
                bot_info = new_bot.get_me()
                
                base_url = (os.getenv('BASE_URL') or '').rstrip('/')
                if not base_url:
                    base_url = f"https://{os.getenv('VERCEL_PROJECT_PRODUCTION_URL', '')}"
                
                if not base_url or '://' not in base_url:
                    bot.edit_message_text("❌ Server missing BASE_URL. Cannot set webhook.", user_id, bot_msg.message_id)
                    return
                    
                webhook_url = f"{base_url}/api?token={new_token}"
                secret_token = os.getenv('WEBHOOK_SECRET')
                if secret_token:
                    new_bot.set_webhook(url=webhook_url, secret_token=secret_token)
                else:
                    new_bot.set_webhook(url=webhook_url)
                    
                # Update DB
                database.update_cloned_bot_token(bot_id, new_token, bot_info.username)
                database.set_user_state(user_id, None)
                
                bot.edit_message_text(f"✅ Token updated successfully!\n\nYour bot is now live at @{bot_info.username}.", user_id, bot_msg.message_id)
                bot.send_message(user_id, "Customize Clone Settings:", reply_markup=keyboards.clone_settings_keyboard(bot_id))
            except Exception as e:
                bot.edit_message_text(f"❌ Invalid token or error connecting to Telegram: {e}", user_id, bot_msg.message_id)
                database.set_user_state(user_id, None)
                bot.send_message(user_id, "Customize Clone Settings:", reply_markup=keyboards.clone_settings_keyboard(bot_id))
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
            
            if not getattr(bot, 'is_main_bot', False):
                database.increment_clone_upload(bot.token)
                
            
            if not hasattr(bot, 'bot_username'):
                bot.bot_username = bot.get_me().username
            bot_username = bot.bot_username
            
            url = f"https://t.me/{bot_username}?start={token}"
            bot.send_message(user_id, f"✅ Batch created!\n\n📦 Items: {count}\n🔗 Link:\n{url}",
                             reply_markup=keyboards.share_keyboard(token, bot_username))
            return
            
        if state == "awaiting_db_channel":
            if not message.text:
                return
            bot_id = state_data.get('bot_id')
            selected_bot = database.get_cloned_bot_by_id(bot_id)
            if not selected_bot:
                return
            token = selected_bot['token']
            
            channel = message.text.strip()
            database.update_cloned_bot_setting(token, 'db_channel', channel)
            bot.send_message(user_id, f"✅ Database Channel has been set to: {channel}\n\nMake sure your cloned bot is an admin in this channel!", reply_markup=keyboards.remove_keyboard())
            database.set_user_state(user_id, None)
            
            bot.send_message(user_id, "Customize Clone Settings:", reply_markup=keyboards.clone_settings_keyboard(bot_id))
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
