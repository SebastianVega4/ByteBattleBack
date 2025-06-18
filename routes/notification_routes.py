from flask import Blueprint, request, jsonify
from models.Notification import Notification
from utils.firebase import db
from utils.decorators import firebase_token_required
from firebase_admin import firestore

notification_bp = Blueprint('notifications', __name__)

@notification_bp.route('', methods=['GET'])
@firebase_token_required
def get_notifications():
    try:
        user_id = request.user['uid']
        limit = int(request.args.get('limit', 10))
        
        notifications = db.collection('notifications') \
            .where('userId', '==', user_id) \
            .order_by('createdAt', direction=firestore.Query.DESCENDING) \
            .limit(limit) \
            .stream()
        
        result = []
        for notif in notifications:
            notif_data = notif.to_dict()
            notif_data['id'] = notif.id
            result.append(notif_data)
            
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener notificaciones: {str(e)}"}), 500

@notification_bp.route('/<notification_id>/read', methods=['PUT'])
@firebase_token_required
def mark_notification_as_read(notification_id):
    try:
        notification_ref = db.collection('notifications').document(notification_id)
        notification = notification_ref.get()
        
        if not notification.exists:
            return jsonify({"error": "Notificación no encontrada"}), 404
        
        if notification.to_dict().get('userId') != request.user['uid']:
            return jsonify({"error": "No autorizado"}), 403
        
        notification_ref.update({
            "isRead": True,
            "readAt": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"message": "Notificación marcada como leída"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al marcar notificación: {str(e)}"}), 500