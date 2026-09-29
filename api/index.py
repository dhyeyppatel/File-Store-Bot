from http.server import BaseHTTPRequestHandler
import json
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
        
        # Import bot inside the handler to ensure env vars are loaded by Vercel
        import telebot
        from bot.telegram import bot
        
        try:
            update = telebot.types.Update.de_json(update_json)
            bot.process_new_updates([update])
        except Exception as e:
            print(f"Error processing update: {e}")
            self.send_response(500)
            self.end_headers()
            return
        
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if 'setup=true' in self.path:
            import telebot
            from bot.telegram import bot
            from telebot.types import BotCommand
            
            # Auto-detect domain from host header if BASE_URL is not provided
            host = self.headers.get('Host')
            base_url = os.getenv('BASE_URL')
            if not base_url and host:
                base_url = f"https://{host}"
                
            if not base_url:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"BASE_URL environment variable is required or Host header missing.")
                return
                
            webhook_url = f"{base_url}/api"
            secret_token = os.getenv('WEBHOOK_SECRET')
            
            try:
                # 1. Set Webhook
                if secret_token:
                    bot.set_webhook(url=webhook_url, secret_token=secret_token)
                else:
                    bot.set_webhook(url=webhook_url)
                    
                # 2. Set Bot Commands
                commands = [
                    BotCommand("start", "Start the bot"),
                    BotCommand("upload", "Start a new file upload session")
                ]
                bot.set_my_commands(commands)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Successfully set webhook to {webhook_url} and updated bot commands!".encode('utf-8'))
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
