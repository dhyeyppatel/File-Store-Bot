from bot.database import get_db
from datetime import datetime, timezone
import pymongo

def get_session(user_id):
    db = get_db()
    return db.sessions.find_one({"user_id": user_id})

def start_session(user_id):
    db = get_db()
    db.sessions.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "status": "uploading",
            "message_ids": [],
            "started_at": datetime.now(timezone.utc),
        }},
        upsert=True
    )

def add_message(user_id, message_id):
    db = get_db()
    db.sessions.update_one(
        {"user_id": user_id, "status": "uploading"},
        {"$push": {"message_ids": message_id}}
    )

def pop_session(user_id):
    """Atomically lock + return the session, or None if already locked/missing."""
    db = get_db()
    return db.sessions.find_one_and_update(
        {"user_id": user_id, "status": "uploading"},
        {"$set": {"status": "processing"}},
        return_document=pymongo.ReturnDocument.BEFORE
    )

def delete_session(user_id):
    db = get_db()
    db.sessions.delete_one({"user_id": user_id})
