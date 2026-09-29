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
        {
            "$set": {
                "status": "uploading",
                "items": [],
                "started_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

def add_item_to_session(user_id, item_data):
    db = get_db()
    result = db.sessions.find_one_and_update(
        {"user_id": user_id, "status": "uploading"},
        {
            "$push": {"items": item_data},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        },
        return_document=pymongo.ReturnDocument.AFTER
    )
    return result

def lock_session(user_id):
    db = get_db()
    # Find and lock the session so it can't be modified simultaneously
    result = db.sessions.find_one_and_update(
        {"user_id": user_id, "status": "uploading"},
        {"$set": {"status": "processing", "updated_at": datetime.now(timezone.utc)}},
        return_document=pymongo.ReturnDocument.BEFORE
    )
    return result

def delete_session(user_id):
    db = get_db()
    db.sessions.delete_one({"user_id": user_id})
