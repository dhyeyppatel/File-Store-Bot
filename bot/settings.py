from bot.database import get_db

def get_user_settings(user_id):
    db = get_db()
    settings = db.users.find_one({"user_id": user_id})
    if not settings:
        settings = {"user_id": user_id, "group_media": False}
        db.users.insert_one(settings)
    return settings

def toggle_group_media(user_id):
    db = get_db()
    settings = get_user_settings(user_id)
    new_val = not settings.get("group_media", False)
    db.users.update_one({"user_id": user_id}, {"$set": {"group_media": new_val}})
    return new_val
