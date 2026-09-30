import os
import telebot
from bot.database import get_db
from bot.tokens import generate_token, hash_token
from datetime import datetime, timezone

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# ─────────────────────────────────────────────
# /upload flow
# ─────────────────────────────────────────────

def store_session(bot, user_id, items_data):
    """
    Copy/group messages into the storage channel and return a shareable token.

    items_data can be a mix of:
      - int  → bare message_id (Group Media OFF)
      - dict → {message_id, media_type, file_id} (Group Media ON)

    When dicts are present, media of the same type are grouped into albums
    (send_media_group, up to 10 per group). Non-groupable items (text, sticker,
    etc.) are forwarded individually via copy_messages.
    """
    storage_chat_id = os.getenv('STORAGE_CHAT_ID')
    db = get_db()

    if not getattr(bot, 'is_main_bot', False):
        clone_info = db.cloned_bots.find_one({"token": bot.token})
        if clone_info and clone_info.get('db_channel'):
            storage_chat_id = clone_info.get('db_channel')
            
    if not storage_chat_id:
        print("[store_session] No storage_chat_id available.")
        return None

    storage_message_ids = []
    failed = 0

    # ── Detect mode ──────────────────────────────────────────────────────────
    has_metadata = any(isinstance(i, dict) for i in items_data)

    if not has_metadata:
        # ── Simple mode (Group Media OFF): bulk copy_messages ────────────────
        message_ids = sorted(set(int(i) for i in items_data))
        for chunk in chunk_list(message_ids, 100):
            try:
                result = bot.copy_messages(
                    chat_id=storage_chat_id,
                    from_chat_id=user_id,
                    message_ids=chunk
                )
                for msg_obj in result:
                    storage_message_ids.append(msg_obj.message_id)
            except Exception as e:
                print(f"[store_session] copy_messages failed: {e}")
                failed += len(chunk)
    else:
        # ── Grouped mode (Group Media ON) ────────────────────────────────────
        GROUPABLE = {'photo', 'video', 'document', 'audio'}
        groups = {}    # media_type → [file_id, ...]
        singles = []   # message_ids for non-groupable (text, sticker, etc.)

        for item in items_data:
            if isinstance(item, dict):
                mt = item.get('media_type', 'other')
                fid = item.get('file_id')
                if mt in GROUPABLE and fid:
                    groups.setdefault(mt, []).append(fid)
                else:
                    singles.append(item['message_id'])
            else:
                singles.append(int(item))

        # Send each media type as albums (≤10 per group)
        MEDIA_CLS = {
            'photo':    telebot.types.InputMediaPhoto,
            'video':    telebot.types.InputMediaVideo,
            'document': telebot.types.InputMediaDocument,
            'audio':    telebot.types.InputMediaAudio,
        }
        for mt, fids in groups.items():
            for chunk in chunk_list(fids, 10):
                media_group = [MEDIA_CLS[mt](fid) for fid in chunk]
                try:
                    sent = bot.send_media_group(chat_id=storage_chat_id, media=media_group)
                    for m in sent:
                        storage_message_ids.append(m.message_id)
                except Exception as e:
                    print(f"[store_session] send_media_group({mt}) failed: {e}")
                    failed += len(chunk)

        # Send singles via copy_messages
        if singles:
            singles.sort()
            for chunk in chunk_list(singles, 100):
                try:
                    result = bot.copy_messages(
                        chat_id=storage_chat_id,
                        from_chat_id=user_id,
                        message_ids=chunk
                    )
                    for msg_obj in result:
                        storage_message_ids.append(msg_obj.message_id)
                except Exception as e:
                    print(f"[store_session] copy_messages(singles) failed: {e}")
                    failed += len(chunk)

    if not storage_message_ids:
        return None

    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    
    search_text = ""
    for item in items_data:
        if isinstance(item, dict) and item.get('text'):
            search_text += item['text'] + " "
    search_text = search_text.strip().lower()
    
    if not hasattr(bot, 'bot_username'):
        bot.bot_username = bot.get_me().username
        
    db.uploads.insert_one({
        "owner_id": user_id,
        "token_hash": token_hash,
        "status": "stored",
        "items": storage_message_ids,
        "source_chat_id": storage_chat_id,
        "item_count": len(storage_message_ids),
        "created_at": datetime.now(timezone.utc),
        "search_text": search_text,
        "bot_username": bot.bot_username,
        "raw_token": raw_token
    })

    return raw_token, len(storage_message_ids), failed


# ─────────────────────────────────────────────
# /batch flow  (no actual copying — stores range directly)
# ─────────────────────────────────────────────

def store_batch_session(user_id, message_ids, source_chat_id=None):
    """Store a range of message IDs from a channel directly (no copying needed)."""
    db = get_db()
    raw_token = generate_token()
    token_hash = hash_token(raw_token)

    db.uploads.insert_one({
        "owner_id": user_id,
        "token_hash": token_hash,
        "status": "stored",
        "items": message_ids,
        "source_chat_id": source_chat_id,
        "item_count": len(message_ids),
        "created_at": datetime.now(timezone.utc),
    })

    return raw_token, len(message_ids)


# ─────────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────────

def retrieve_upload_by_token(token):
    token_hash = hash_token(token)
    db = get_db()
    return db.uploads.find_one({"token_hash": token_hash, "status": "stored"})


def send_upload_items(bot, user_id, upload_doc, protect_content=False):
    """Send stored files to the user using copy_messages."""
    source = upload_doc.get("source_chat_id") or os.getenv('STORAGE_CHAT_ID')
    items = upload_doc.get('items', [])

    sent_ids = []
    for chunk in chunk_list(items, 100):
        try:
            res = bot.copy_messages(
                chat_id=user_id,
                from_chat_id=source,
                message_ids=chunk,
                protect_content=protect_content
            )
            sent_ids.extend([m.message_id for m in res])
        except Exception as e:
            print(f"[send_upload_items] copy_messages failed: {e}")
            
    return sent_ids
