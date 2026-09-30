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

            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Processed {len(pending)} auto-deletes.".encode('utf-8'))
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
                    BotCommand("settings", "Configure bot preferences")
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

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("Telegram File Store Bot is running.".encode('utf-8'))
