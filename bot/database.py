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

def remove_cloned_bot(token):
    db = get_db()
    db.cloned_bots.delete_one({"token": token})
