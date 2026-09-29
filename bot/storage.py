import os
from bot.database import get_db
from bot.tokens import generate_token, hash_token
from bot.telegram import bot
from bot.rate_limiter import RateLimiter, RateLimitExceeded
from datetime import datetime, timezone
import time
import telebot

rate_limiter = RateLimiter()

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def store_session(user_id, message_ids):
    storage_chat_id = os.getenv('STORAGE_CHAT_ID')
    db = get_db()
    
    upload_id = "up_" + os.urandom(8).hex()
    
    message_ids.sort() # Ensure they are in strictly increasing order
    
    storage_message_ids = []
    failed = 0
    
    # Send in chunks of 100 to avoid Telegram limits
    for chunk in chunk_list(message_ids, 100):
        try:
            copied_msgs = rate_limiter.execute(
                bot.copy_messages,
                chat_id=storage_chat_id,
                from_chat_id=user_id,
                message_ids=chunk
            )
            for msg_id_obj in copied_msgs:
                storage_message_ids.append(msg_id_obj.message_id)
        except RateLimitExceeded:
            break
        except Exception as e:
            print(f"Failed to copy batch of messages: {e}")
            failed += len(chunk)

    if not storage_message_ids:
        return None
        
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    
    upload_doc = {
        "upload_id": upload_id,
        "owner_id": user_id,
        "status": "stored",
        "token_hash": token_hash,
        "items": storage_message_ids,
        "total_items": len(message_ids),
        "processed_items": len(storage_message_ids),
        "failed_items": failed,
        "created_at": datetime.now(timezone.utc),
        "source_chat_id": None
    }
    
    db.uploads.insert_one(upload_doc)
    return raw_token, len(storage_message_ids), failed

def retrieve_upload_by_token(token):
    token_hash = hash_token(token)
    db = get_db()
    return db.uploads.find_one({"token_hash": token_hash, "status": "stored"})

def send_upload_items(user_id, upload_doc):
    storage_chat_id = upload_doc.get("source_chat_id") or os.getenv('STORAGE_CHAT_ID')
    
    # Retrieve using copy_messages to efficiently send them grouped natively
    for chunk in chunk_list(upload_doc['items'], 100):
        try:
            bot.copy_messages(
                chat_id=user_id,
                from_chat_id=storage_chat_id,
                message_ids=chunk
            )
        except Exception as e:
            print(f"Failed to retrieve batch for user {user_id}: {e}")

def store_batch_session(user_id, message_ids, source_chat_id=None):
    db = get_db()
    upload_id = "up_" + os.urandom(8).hex()
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    
    upload_doc = {
        "upload_id": upload_id,
        "owner_id": user_id,
        "token_hash": token_hash,
        "source_chat_id": source_chat_id,
        "status": "stored",
        "total_items": len(message_ids),
        "processed_items": len(message_ids),
        "failed_items": 0,
        "items": message_ids,
        "created_at": datetime.now(timezone.utc)
    }
    db.uploads.insert_one(upload_doc)
    return raw_token, len(message_ids)
