from datetime import datetime
from firebase_admin import firestore

class User:
    def __init__(self, uid, email, username, role="user", is_banned=False, aceptaelreto_username=None):
        self.uid = uid
        self.email = email
        self.username = username
        self.role = role
        self.is_banned = is_banned
        self.aceptaelreto_username = aceptaelreto_username
        self.created_at = firestore.SERVER_TIMESTAMP
        self.updated_at = firestore.SERVER_TIMESTAMP

    def to_dict(self):
        return {
            "uid": self.uid,
            "email": self.email,
            "username": self.username,
            "role": self.role,
            "isBanned": self.is_banned,
            "aceptaelretoUsername": self.aceptaelreto_username,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }