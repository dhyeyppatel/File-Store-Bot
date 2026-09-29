from http.server import BaseHTTPRequestHandler
import os


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
            import bot.telegram as tg_module   # import the module, not the name 'bot'
            tg_bot = tg_module.bot

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
        if 'setup=true' in self.path:
            from telebot.types import BotCommand
            import bot.telegram as tg_module
            tg_bot = tg_module.bot

            # Prefer BASE_URL env var, fall back to Host header
            base_url = (os.getenv('BASE_URL') or '').rstrip('/')
            if not base_url:
                host = self.headers.get('Host', '')
                base_url = f"https://{host}"

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
