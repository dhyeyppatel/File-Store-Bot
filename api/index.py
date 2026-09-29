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
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("Telegram File Store Bot is running.".encode('utf-8'))
