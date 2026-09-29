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
