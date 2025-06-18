from firebase_admin import firestore
from datetime import datetime

class Notification:
    def __init__(self, user_id, title, message, notification_type, is_read=False):
        self.user_id = user_id
        self.title = title
        self.message = message
        self.notification_type = notification_type  # 'payment', 'participation', 'winner', etc.
        self.is_read = is_read
        self.created_at = firestore.SERVER_TIMESTAMP
        self.read_at = None

    def to_dict(self):
        return {
            "userId": self.user_id,
            "title": self.title,
            "message": self.message,
            "type": self.notification_type,
            "isRead": self.is_read,
            "createdAt": self.created_at,
            "readAt": self.read_at
        }

    def mark_as_read(self):
        self.is_read = True
        self.read_at = firestore.SERVER_TIMESTAMP
        return self.to_dict()