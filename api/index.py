from http.server import BaseHTTPRequestHandler
import os
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # Verify webhook secret if configured
        secret_token = self.headers.get('X-Telegram-Bot-Api-Secret-Token')
        expected_secret = os.getenv('WEBHOOK_SECRET')
        if expected_secret and secret_token != expected_secret:
            self.send_response(403)
            self.end_headers()
            return

        update_json = post_data.decode('utf-8')

        try:
            import telebot
            import bot.telegram as tg_module
            
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('token', [None])[0]

            tg_bot = tg_module.get_bot(token)

            update = telebot.types.Update.de_json(update_json)
            tg_bot.process_new_updates([update])
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(f"Error processing update: {error_msg}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Webhook Error: {error_msg}".encode('utf-8'))
            return

        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if 'cron=true' in self.path:
            import time
            import telebot
            import bot.database as database
            import bot.telegram as tg_module
            
            # ── Auto-delete processing ──
            pending = database.get_pending_auto_deletes(time.time())
            
            # Group by bot_token to reuse bot instances
            by_token = {}
            for doc in pending:
                t = doc['bot_token']
                if t not in by_token:
                    by_token[t] = []
                by_token[t].append(doc)
                
            for token, docs in by_token.items():
                try:
                    tg_bot = tg_module.get_bot(token)
                    for doc in docs:
                        try:
                            tg_bot.delete_message(doc['chat_id'], doc['message_id'])
                        except Exception as e:
                            print(f"Failed to delete {doc['message_id']} for {doc['chat_id']}: {e}")
                        finally:
                            database.remove_auto_delete(doc['_id'])
                except Exception as e:
                    print(f"Bot init error: {e}")

            # ── Auto-heal webhooks if env vars changed ──
            healed = []
            base_url = (os.getenv('BASE_URL') or '').rstrip('/')
            expected_secret = os.getenv('WEBHOOK_SECRET') or ''
            
            if base_url:
                import hashlib
                config_hash = hashlib.md5(f"{base_url}|{expected_secret}".encode()).hexdigest()
                db = database.get_db()
                stored = db.bot_config.find_one({"_id": "webhook_config"})
                stored_hash = stored.get("hash") if stored else None
                
                if stored_hash != config_hash:
                    # Env vars changed — re-register ALL webhooks
                    # Main bot
                    try:
                        main_bot = tg_module.get_bot()
                        main_url = f"{base_url}/api"
                        if expected_secret:
                            main_bot.set_webhook(url=main_url, secret_token=expected_secret)
                        else:
                            main_bot.set_webhook(url=main_url)
                        healed.append("main")
                    except Exception as e:
                        print(f"[CRON] Main bot heal error: {e}")
                    
                    # Clone bots
                    try:
                        clones = list(db.cloned_bots.find({"status": "active"}))
                        for clone in clones:
                            clone_token = clone.get('token')
                            if not clone_token:
                                continue
                            try:
                                clone_bot = telebot.TeleBot(clone_token, threaded=False)
                                clone_url = f"{base_url}/api?token={clone_token}"
                                if expected_secret:
                                    clone_bot.set_webhook(url=clone_url, secret_token=expected_secret)
                                else:
                                    clone_bot.set_webhook(url=clone_url)
                                healed.append(clone.get('username', clone_token[:10]))
                            except Exception as e:
                                print(f"[CRON] Clone heal error ({clone_token[:10]}): {e}")
                    except Exception as e:
                        print(f"[CRON] Clone heal scan error: {e}")
                    
                    # Save new hash so we don't re-register again next cron
                    db.bot_config.update_one(
                        {"_id": "webhook_config"},
                        {"$set": {"hash": config_hash}},
                        upsert=True
                    )

            heal_msg = f", healed={healed}" if healed else ""
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Processed {len(pending)} auto-deletes{heal_msg}.".encode('utf-8'))
            return
            
        if 'setup=true' in self.path:
            from telebot.types import BotCommand
            import bot.telegram as tg_module
            
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('token', [None])[0]

            tg_bot = tg_module.get_bot(token)

            # Prefer BASE_URL env var, fall back to Host header
            base_url = (os.getenv('BASE_URL') or '').rstrip('/')
            if not base_url:
                host = self.headers.get('Host', '')
                base_url = f"https://{host}"

            if token:
                webhook_url = f"{base_url}/api?token={token}"
            else:
                webhook_url = f"{base_url}/api"
                
            secret_token = os.getenv('WEBHOOK_SECRET')

            try:
                # 1. Set Webhook
                if secret_token:
                    tg_bot.set_webhook(url=webhook_url, secret_token=secret_token)
                else:
                    tg_bot.set_webhook(url=webhook_url)

                # 2. Set Bot Commands
                commands = [
                    BotCommand("start", "Start the bot"),
                    BotCommand("upload", "Start a new file upload session"),
                    BotCommand("batch", "Create a link from existing channel messages"),
                    BotCommand("search", "Search for files"),
                    BotCommand("clone", "Clone this bot"),
                    BotCommand("mybots", "Manage your cloned bots"),
                    BotCommand("settings", "Configure bot preferences"),
                    BotCommand("help", "Show detailed help and features")
                ]
                tg_bot.set_my_commands(commands)

                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(
                    f"Successfully set webhook to {webhook_url} and updated bot commands!".encode('utf-8')
                )
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Setup Error: {e}".encode('utf-8'))
            return
            
        if 'setup_clones=true' in self.path:
            import bot.database as database
            import bot.telegram as tg_module
            
            db = database.get_db()
            clones = list(db.cloned_bots.find({"status": "active"}))
            
            base_url = (os.getenv('BASE_URL') or '').rstrip('/')
            if not base_url:
                host = self.headers.get('Host', '')
                base_url = f"https://{host}"
                
            secret_token = os.getenv('WEBHOOK_SECRET')
            
            success_count = 0
            for clone in clones:
                token = clone.get('token')
                if not token: continue
                
                try:
                    tg_bot = tg_module.get_bot(token)
                    webhook_url = f"{base_url}/api?token={token}"
                    if secret_token:
                        tg_bot.set_webhook(url=webhook_url, secret_token=secret_token)
                    else:
                        tg_bot.set_webhook(url=webhook_url)
                    success_count += 1
                except Exception as e:
                    print(f"Failed to setup clone {token}: {e}")
                    
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Successfully re-registered webhooks for {success_count}/{len(clones)} clone bots.".encode('utf-8'))
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("Telegram File Store Bot is running.".encode('utf-8'))
