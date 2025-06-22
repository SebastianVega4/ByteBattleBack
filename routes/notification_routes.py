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
        
        # Consulta modificada temporalmente (sin ordenamiento)
        notifications = db.collection('notifications') \
            .where('userId', '==', user_id) \
            .limit(limit) \
            .stream()
        
        result = []
        for notif in notifications:
            notif_data = notif.to_dict()
            if 'createdAt' in notif_data:
                notif_data['createdAt'] = notif_data['createdAt'].isoformat()
            if 'readAt' in notif_data and notif_data['readAt']:
                notif_data['readAt'] = notif_data['readAt'].isoformat()
            notif_data['id'] = notif.id
            result.append(notif_data)
        
        # Ordenar manualmente en Python
        result.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
            
        return jsonify(result), 200
    except Exception as e:
        print(f"Error en get_notifications: {str(e)}")
        return jsonify({"error": f"Error al obtener notificaciones: {str(e)}"}), 500
    
@notification_bp.route('', methods=['POST'])
@firebase_token_required
def create_notification():
    try:
        data = request.get_json()
        user_id = data.get('userId')
        title = data.get('title')
        message = data.get('message')
        notification_type = data.get('type')
        
        if not all([user_id, title, message, notification_type]):
            return jsonify({"error": "Faltan campos requeridos"}), 400
            
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type
        )
        
        _, doc_ref = db.collection('notifications').add(notification.to_dict())
        
        return jsonify({
            "success": True,
            "message": "Notificación creada",
            "id": doc_ref.id
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al crear notificación: {str(e)}"}), 500
    
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
    
@notification_bp.route('/<notification_id>', methods=['DELETE'])
@firebase_token_required
def delete_notification(notification_id):
    try:
        notification_ref = db.collection('notifications').document(notification_id)
        notification = notification_ref.get()
        
        if not notification.exists:
            return jsonify({"error": "Notificación no encontrada"}), 404
        
        if notification.to_dict().get('userId') != request.user['uid']:
            return jsonify({"error": "No autorizado"}), 403
        
        notification_ref.delete()
        
        return jsonify({"message": "Notificación eliminada"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al eliminar notificación: {str(e)}"}), 500

    