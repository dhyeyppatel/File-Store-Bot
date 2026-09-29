import os
from bot.database import get_db
from bot.tokens import generate_token, hash_token
from bot.telegram import bot
from datetime import datetime, timezone

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# ─────────────────────────────────────────────
# /upload flow
# ─────────────────────────────────────────────

def store_session(user_id, message_ids):
    """
    Copy messages from user's PM to the database channel, save their
    new IDs, generate a token and return (token, stored_count, failed_count).
    message_ids: list of ints (the user's original message IDs in bot PM).
    """
    storage_chat_id = os.getenv('STORAGE_CHAT_ID')
    db = get_db()

    message_ids = sorted(set(message_ids))   # dedup + sort (Telegram requires ascending order)

    storage_message_ids = []
    failed = 0

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

    if not storage_message_ids:
        return None

    raw_token = generate_token()
    token_hash = hash_token(raw_token)

    db.uploads.insert_one({
        "owner_id": user_id,
        "token_hash": token_hash,
        "status": "stored",
        "items": storage_message_ids,
        "source_chat_id": None,
        "item_count": len(storage_message_ids),
        "created_at": datetime.now(timezone.utc),
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


def send_upload_items(user_id, upload_doc):
    """Send stored files to the user using copy_messages."""
    source = upload_doc.get("source_chat_id") or os.getenv('STORAGE_CHAT_ID')
    items = upload_doc.get('items', [])

    for chunk in chunk_list(items, 100):
        try:
            bot.copy_messages(
                chat_id=user_id,
                from_chat_id=source,
                message_ids=chunk
            )
        except Exception as e:
            print(f"[send_upload_items] copy_messages failed: {e}")
