import os
from bot.database import get_db
from bot.tokens import generate_token, hash_token
from bot.telegram import bot
from bot.rate_limiter import RateLimiter, RateLimitExceeded
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
    
    upload_doc = {
        "upload_id": upload_id,
        "owner_id": user_id,
        "status": "processing",
        "total_items": len(items_data),
        "processed_items": 0,
        "failed_items": 0,
        "items": [],
        "created_at": datetime.now(timezone.utc)
    }
    db.uploads.insert_one(upload_doc)
    
    storage_items = []
    failed = 0
    aborted_by_rate_limit = False
    
    try:
        if not group_media:
            # Process using highly efficient copy_messages (100 items per request)
            message_ids = [item['message_id'] if isinstance(item, dict) else item for item in items_data]
            for chunk in chunk_list(message_ids, 100):
                if aborted_by_rate_limit:
                    break
                try:
                    copied_msgs = rate_limiter.execute(
                        bot.copy_messages,
                        chat_id=storage_chat_id,
                        from_chat_id=user_id,
                        message_ids=chunk
                    )
                    for msg_id_obj in copied_msgs:
                        storage_items.append(msg_id_obj.message_id)
                except RateLimitExceeded:
                    aborted_by_rate_limit = True
                    break
                except Exception as e:
                    print(f"Failed to copy batch of messages: {e}")
                    failed += len(chunk)
        else:
            # Process with grouping (order doesn't matter)
            groups = {}
            others = []
            
            for item in items_data:
                if isinstance(item, dict):
                    mt = item['media_type']
                    if mt in ['photo', 'video', 'document', 'audio']:
                        groups.setdefault(mt, []).append(item['file_id'])
                    else:
                        others.append(item['message_id'])
                else:
                    others.append(item)
                    
            # Send grouped media
            for mt, media_list in groups.items():
                if aborted_by_rate_limit:
                    break
                    
                for chunk in chunk_list(media_list, 10):
                    media_group = []
                    for f_id in chunk:
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
                        for sent_msg in sent_msgs:
                            storage_items.append(sent_msg.message_id)
                    except RateLimitExceeded:
                        aborted_by_rate_limit = True
                        break
                    except Exception as e:
                        print(f"Failed to send media group for {mt}: {e}")
                        failed += len(chunk)
                        
            # Send unsupported formats natively using chunked copy_messages
            if not aborted_by_rate_limit:
                for chunk in chunk_list(others, 100):
                    if aborted_by_rate_limit:
                        break
                    try:
                        copied_msgs = rate_limiter.execute(
                            bot.copy_messages,
                            chat_id=storage_chat_id,
                            from_chat_id=user_id,
                            message_ids=chunk
                        )
                        for msg_id_obj in copied_msgs:
                            storage_items.append(msg_id_obj.message_id)
                    except RateLimitExceeded:
                        aborted_by_rate_limit = True
                        break
                    except Exception as e:
                        print(f"Failed to copy batch of text/unsupported messages: {e}")
                        failed += len(chunk)
    finally:
        # Save what we managed to process before rate limit or timeout
        if aborted_by_rate_limit:
            # Calculate remaining as failed so the user knows they weren't stored
            processed = len(storage_items)
            failed = len(items_data) - processed
        
        if not storage_items:
            db.uploads.update_one({"upload_id": upload_id}, {"$set": {"status": "failed"}})
            return None
            
        raw_token = generate_token()
        token_hash = hash_token(raw_token)
        
        db.uploads.update_one({"upload_id": upload_id}, {
            "$set": {
                "status": "stored",
                "token_hash": token_hash,
                "items": storage_items,
                "processed_items": len(storage_items),
                "failed_items": failed
            }
        })
        
        final_doc = db.uploads.find_one({"upload_id": upload_id})
        return raw_token, final_doc['processed_items'], final_doc['failed_items']

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
