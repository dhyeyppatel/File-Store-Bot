import time
import os
import telebot
from telebot.apihelper import ApiTelegramException

class RateLimitExceeded(Exception):
    pass

class RateLimiter:
    def __init__(self):
        self.requests_per_minute = int(os.getenv("TELEGRAM_REQUESTS_PER_MINUTE", 20))
        self.requests_this_minute = 0
        self.minute_start = time.time()
        
    def check_limit(self):
        now = time.time()
        if now - self.minute_start >= 60:
            self.minute_start = now
            self.requests_this_minute = 0
            
        if self.requests_this_minute >= self.requests_per_minute:
            raise RateLimitExceeded("Configured requests-per-minute limit reached. Aborting to prevent Vercel timeout.")
            
    def execute(self, func, *args, **kwargs):
        self.check_limit()
        try:
            result = func(*args, **kwargs)
            self.requests_this_minute += 1
            return result
        except ApiTelegramException as e:
            if e.error_code == 429:
                raise RateLimitExceeded(f"Telegram 429 Too Many Requests hit. Aborting to prevent Vercel timeout.")
            raise e
