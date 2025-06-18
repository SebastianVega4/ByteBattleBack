from models.Notification import Notification
from utils.firebase import db

def send_notification(user_id, title, message, notification_type):
    try:
        notification = Notification(user_id, title, message, notification_type)
        _, doc_ref = db.collection('notifications').add(notification.to_dict())
        return doc_ref.id
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return None

def send_admin_notification(title, message):
    try:
        # Obtener todos los administradores
        admins = db.collection('users').where('role', '==', 'admin').stream()
        
        for admin in admins:
            send_notification(admin.id, title, message, 'admin')
            
        return True
    except Exception as e:
        print(f"Error sending admin notifications: {str(e)}")
        return False