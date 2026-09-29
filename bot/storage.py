import os
from bot.database import get_db
from bot.tokens import generate_token, hash_token
from bot.telegram import bot
from bot.rate_limiter import RateLimiter
from datetime import datetime, timezone
import telebot

rate_limiter = RateLimiter()

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def store_session(user_id, items_data, group_media=False):
    storage_chat_id = os.getenv('STORAGE_CHAT_ID')
    db = get_db()
    
    upload_id = "up_" + os.urandom(8).hex()
    
    # Store initial processing state
    upload_doc = {
        "upload_id": upload_id,
        "owner_id": user_id,
        "status": "processing",
        "total_items": len(items_data),
        "processed_items": 0,
        "failed_items": 0,
        "items": [], # Will hold { "position": 1, "storage_message_id": 123 }
        "created_at": datetime.now(timezone.utc)
    }
    db.uploads.insert_one(upload_doc)
    
    storage_items = []
    
    if not group_media:
        # Process without grouping
        for idx, item in enumerate(items_data, start=1):
            try:
                copied_msg = rate_limiter.execute(
                    bot.copy_message,
                    chat_id=storage_chat_id,
                    from_chat_id=user_id,
                    message_id=item['message_id']
                )
                storage_items.append({"position": idx, "storage_message_id": copied_msg.message_id})
                db.uploads.update_one({"upload_id": upload_id}, {"$inc": {"processed_items": 1}})
            except Exception as e:
                print(f"Failed to copy message {item['message_id']}: {e}")
                db.uploads.update_one({"upload_id": upload_id}, {"$inc": {"failed_items": 1}})
    else:
        # Process with sendMediaGroup grouping
        groups = {} # media_type -> list of (position, file_id)
        others = [] # (position, message_id)
        
        for idx, item in enumerate(items_data, start=1):
            mt = item['media_type']
            if mt in ['photo', 'video', 'document', 'audio']:
                groups.setdefault(mt, []).append((idx, item['file_id']))
            else:
                others.append((idx, item['message_id']))
                
        # Send grouped media
        for mt, media_list in groups.items():
            for chunk in chunk_list(media_list, 10):
                media_group = []
                positions = []
                for pos, f_id in chunk:
                    positions.append(pos)
                    if mt == 'photo':
                        media_group.append(telebot.types.InputMediaPhoto(f_id))
                    elif mt == 'video':
                        media_group.append(telebot.types.InputMediaVideo(f_id))
                    elif mt == 'document':
                        media_group.append(telebot.types.InputMediaDocument(f_id))
                    elif mt == 'audio':
                        media_group.append(telebot.types.InputMediaAudio(f_id))
                        
                try:
                    sent_msgs = rate_limiter.execute(
                        bot.send_media_group,
                        chat_id=storage_chat_id,
                        media=media_group
                    )
                    for pos, sent_msg in zip(positions, sent_msgs):
                        storage_items.append({"position": pos, "storage_message_id": sent_msg.message_id})
                    db.uploads.update_one({"upload_id": upload_id}, {"$inc": {"processed_items": len(chunk)}})
                except Exception as e:
                    print(f"Failed to send media group for {mt}: {e}")
                    db.uploads.update_one({"upload_id": upload_id}, {"$inc": {"failed_items": len(chunk)}})
                    
        # Send others
        for pos, msg_id in others:
            try:
                copied_msg = rate_limiter.execute(
                    bot.copy_message,
                    chat_id=storage_chat_id,
                    from_chat_id=user_id,
                    message_id=msg_id
                )
                storage_items.append({"position": pos, "storage_message_id": copied_msg.message_id})
                db.uploads.update_one({"upload_id": upload_id}, {"$inc": {"processed_items": 1}})
            except Exception as e:
                print(f"Failed to copy message {msg_id}: {e}")
                db.uploads.update_one({"upload_id": upload_id}, {"$inc": {"failed_items": 1}})
                
    # Sort storage items by original position
    storage_items.sort(key=lambda x: x['position'])
    final_message_ids = [item['storage_message_id'] for item in storage_items]
    
    if not final_message_ids:
        db.uploads.update_one({"upload_id": upload_id}, {"$set": {"status": "failed"}})
        return None
        
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    
    db.uploads.update_one({"upload_id": upload_id}, {
        "$set": {
            "status": "stored",
            "token_hash": token_hash,
            "items": final_message_ids
        }
    })
    
    # Return upload_doc summary
    final_doc = db.uploads.find_one({"upload_id": upload_id})
    return raw_token, final_doc['processed_items'], final_doc['failed_items']

def retrieve_upload_by_token(token):
    token_hash = hash_token(token)
    db = get_db()
    return db.uploads.find_one({"token_hash": token_hash, "status": "stored"})

def send_upload_items(user_id, upload_doc):
    storage_chat_id = os.getenv('STORAGE_CHAT_ID')
    
    # Retrieve in chunks of 100 using copy_messages to avoid limits on reading
    for chunk in chunk_list(upload_doc['items'], 100):
        try:
            bot.copy_messages(
                chat_id=user_id,
                from_chat_id=storage_chat_id,
                message_ids=chunk
            )
        except Exception as e:
            print(f"Failed to retrieve batch for user {user_id}: {e}")
