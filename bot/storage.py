import os
from bot.database import get_db
from bot.tokens import generate_token, hash_token
from bot.telegram import bot
from datetime import datetime, timezone

def store_session(user_id, message_ids):
    storage_chat_id = os.getenv('STORAGE_CHAT_ID')
    
    storage_message_ids = []
    failed_count = 0
    for msg_id in message_ids:
        try:
            copied_msg = bot.copy_message(
                chat_id=storage_chat_id,
                from_chat_id=user_id,
                message_id=msg_id
            )
            storage_message_ids.append(copied_msg.message_id)
        except Exception as e:
            print(f"Failed to copy message {msg_id}: {e}")
            failed_count += 1
            continue

    if not storage_message_ids:
        return None
        
    db = get_db()
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    
    upload_doc = {
        "owner_id": user_id,
        "item_count": len(storage_message_ids),
        "status": "stored",
        "token_hash": token_hash,
        "items": storage_message_ids,
        "created_at": datetime.now(timezone.utc),
        "expires_at": None
    }
    
    db.uploads.insert_one(upload_doc)
    return raw_token, len(storage_message_ids), failed_count

def retrieve_upload_by_token(token):
    token_hash = hash_token(token)
    db = get_db()
    return db.uploads.find_one({"token_hash": token_hash, "status": "stored"})

def send_upload_items(user_id, upload_doc):
    storage_chat_id = os.getenv('STORAGE_CHAT_ID')
    for msg_id in upload_doc['items']:
        try:
            bot.copy_message(
                chat_id=user_id,
                from_chat_id=storage_chat_id,
                message_id=msg_id
            )
        except Exception as e:
            print(f"Failed to retrieve message {msg_id} for user {user_id}: {e}")
