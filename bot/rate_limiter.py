import time
import os
import telebot
from telebot.apihelper import ApiTelegramException

class RateLimiter:
    def __init__(self):
        self.requests_per_minute = int(os.getenv("TELEGRAM_REQUESTS_PER_MINUTE", 20))
        self.requests_this_minute = 0
        self.minute_start = time.time()
        
    def wait_if_needed(self):
        now = time.time()
        if now - self.minute_start >= 60:
            self.minute_start = now
            self.requests_this_minute = 0
            
        if self.requests_this_minute >= self.requests_per_minute:
            sleep_time = 60 - (now - self.minute_start)
            if sleep_time > 0:
                print(f"RateLimiter: Sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
            self.minute_start = time.time()
            self.requests_this_minute = 0
            
    def execute(self, func, *args, **kwargs):
        self.wait_if_needed()
        try:
            result = func(*args, **kwargs)
            self.requests_this_minute += 1
            return result
        except ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = e.result_json.get('parameters', {}).get('retry_after', 3)
                print(f"RateLimiter: Hit 429 Too Many Requests. Sleeping for {retry_after}s")
                time.sleep(retry_after)
                
                # Retry once
                result = func(*args, **kwargs)
                self.requests_this_minute += 1
                return result
            raise e
