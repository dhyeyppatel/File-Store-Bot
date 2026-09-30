import os
from pymongo import MongoClient

class Database:
    def __init__(self):
        self._client = None
        self._db = None

    def get_db(self):
        if self._db is None:
            mongo_uri = os.getenv('MONGO_URI')
            if not mongo_uri:
                raise ValueError("MONGO_URI not set in environment variables")
            db_name = os.getenv('DB_NAME', 'file_store')
            self._client = MongoClient(mongo_uri)
            self._db = self._client[db_name]
            
            # Setup indexes
            self._db.uploads.create_index("token_hash", unique=True)
            self._db.uploads.create_index("owner_id")
            self._db.uploads.create_index("created_at")
            self._db.sessions.create_index("user_id", unique=True)
        return self._db

db_instance = Database()

def get_db():
    return db_instance.get_db()

def set_user_state(user_id, state, data=None):
    db = get_db()
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"state": state, "state_data": data or {}}},
        upsert=True
    )

def get_user_state(user_id):
    db = get_db()
    user = db.users.find_one({"user_id": user_id})
    if user:
        return user.get("state"), user.get("state_data", {})
    return None, {}

def add_cloned_bot(user_id, token, username):
    db = get_db()
    db.cloned_bots.update_one(
        {"token": token},
        {"$set": {"owner_id": user_id, "username": username, "status": "active"}},
        upsert=True
    )

def get_cloned_bots(user_id):
    db = get_db()
    return list(db.cloned_bots.find({"owner_id": user_id, "status": "active"}))

def delete_cloned_bot_by_id(bot_id):
    db = get_db()
    from bson.objectid import ObjectId
    db.cloned_bots.delete_one({"_id": ObjectId(bot_id)})
    
# ─────────────────────────────────────────────
# Auto Delete Queue
# ─────────────────────────────────────────────

def enqueue_auto_delete(bot_token, chat_id, message_id, delete_at):
    db = get_db()
    db.auto_delete_queue.insert_one({
        "bot_token": bot_token,
        "chat_id": chat_id,
        "message_id": message_id,
        "delete_at": delete_at
    })

def get_pending_auto_deletes(current_time):
    db = get_db()
    return list(db.auto_delete_queue.find({"delete_at": {"$lte": current_time}}))

def remove_auto_delete(doc_id):
    db = get_db()
    db.auto_delete_queue.delete_one({"_id": doc_id})

def update_cloned_bot_token(bot_id, new_token, new_username):
    db = get_db()
    from bson.objectid import ObjectId
    db.cloned_bots.update_one({"_id": ObjectId(bot_id)}, {"$set": {"token": new_token, "username": new_username}})

def is_bot_cloned(token):
    db = get_db()
    return db.cloned_bots.find_one({"token": token}) is not None

def get_cloned_bot_by_token(token):
    db = get_db()
    return db.cloned_bots.find_one({"token": token, "status": "active"})

def get_cloned_bot_by_id(bot_id):
    from bson.objectid import ObjectId
    db = get_db()
    return db.cloned_bots.find_one({"_id": ObjectId(bot_id), "status": "active"})

def update_cloned_bot_setting(token, key, value):
    db = get_db()
    db.cloned_bots.update_one(
        {"token": token},
        {"$set": {key: value}}
    )

def is_user_verified(user_id, bot_token):
    db = get_db()
    session = db.shortener_sessions.find_one({"user_id": user_id, "bot_token": bot_token})
    if session:
        from datetime import datetime
        if session.get('expires_at') and session['expires_at'] > datetime.utcnow():
            return True
    return False

def set_user_verified(user_id, bot_token, validity_hours):
    db = get_db()
    from datetime import datetime, timedelta
    try:
        validity_hours = float(validity_hours)
    except:
        validity_hours = 24.0
    expires_at = datetime.utcnow() + timedelta(hours=validity_hours)
    db.shortener_sessions.update_one(
        {"user_id": user_id, "bot_token": bot_token},
        {"$set": {"expires_at": expires_at}},
        upsert=True
    )

def track_clone_user(bot_token, user_id):
    db = get_db()
    db.clone_users.update_one(
        {"bot_token": bot_token, "user_id": user_id},
        {"$set": {"bot_token": bot_token}},
        upsert=True
    )

def get_clone_user_count(bot_token):
    db = get_db()
    return db.clone_users.count_documents({"bot_token": bot_token})

def increment_clone_upload(bot_token):
    db = get_db()
    db.cloned_bots.update_one(
        {"token": bot_token},
        {"$inc": {"total_uploads": 1}}
    )
