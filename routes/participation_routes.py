import traceback
from flask import Blueprint, request, jsonify
from models.Participation import Participation
from utils.firebase import db
from utils.decorators import firebase_token_required, admin_required
from firebase_admin import firestore
from utils.exceptions import ValidationError
from services.notification_service import send_notification, send_admin_notification

participation_bp = Blueprint('participations', __name__)
MAX_CODE_LENGTH = 10000  # Límite de 10,000 caracteres para el código

@participation_bp.route('', methods=['GET'])
@firebase_token_required
def get_user_participations():
    try:
        # Obtener el ID del usuario desde el token o parámetro
        requesting_user_id = request.user['uid']
        target_user_id = request.args.get('userId')
        
        # Si no se especifica userId, usar el del usuario autenticado
        if not target_user_id:
            target_user_id = requesting_user_id
        
        # Verificar permisos
        if requesting_user_id != target_user_id:
            # Solo permitir a admins ver otras participaciones
            user_ref = db.collection('users').document(requesting_user_id).get()
            if not user_ref.exists or user_ref.to_dict().get('role') != 'admin':
                return jsonify({"error": "No autorizado"}), 403
        
        # Obtener participaciones
        participations_ref = db.collection('participations').where('userId', '==', target_user_id)
        participations = []
        
        for doc in participations_ref.stream():
            part_data = doc.to_dict()
            part_data['id'] = doc.id
            
            # Obtener datos del reto
            challenge_ref = db.collection('challenges').document(part_data['challengeId']).get()
            if challenge_ref.exists:
                part_data['challenge'] = challenge_ref.to_dict()
            
            participations.append(part_data)
        
        return jsonify(participations), 200
        
    except Exception as e:
        print(f"Error en get_user_participations: {str(e)}")
        return jsonify({"error": "Error al obtener participaciones"}), 500
    
@participation_bp.route('', methods=['POST'])
@firebase_token_required
def initiate_participation():
    try:
        print("\n--- Iniciando participación ---")
        data = request.get_json()
        print("Datos recibidos:", data)
        
        if not data:
            print("Error: No se recibieron datos JSON")
            return jsonify({"error": "Datos JSON requeridos"}), 400
            
        challenge_id = data.get('challengeId')
        user_id = request.user['uid']
        
        if not challenge_id:
            print("Error: Falta challengeId")
            return jsonify({"error": "Challenge ID is required"}), 400
        
        # Verificar si el reto existe
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge = challenge_ref.get()
        
        if not challenge.exists:
            print(f"Error: Reto {challenge_id} no encontrado")
            return jsonify({"error": "Reto no encontrado"}), 404
            
        challenge_data = challenge.to_dict()
        
        # Verificar que el reto está activo
        if challenge_data.get('status') != 'activo':
            print("Error: Reto no está activo")
            return jsonify({"error": "El reto no está activo"}), 400
            
        # Verificar que el usuario no haya participado ya
        existing_query = db.collection('participations') \
            .where('userId', '==', user_id) \
            .where('challengeId', '==', challenge_id)
            
        existing_participations = list(existing_query.stream())
        
        if len(existing_participations) > 0:
            print("Error: Usuario ya está participando")
            return jsonify({"error": "Ya estás participando en este reto"}), 400
            
        # Crear nueva participación
        new_participation = {
            "userId": user_id,
            "challengeId": challenge_id,
            "score": None,
            "code": None,
            "aceptaelretoUsername": None,
            "submissionDate": None,
            "isPaid": False,
            "paymentStatus": "pending",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "paymentConfirmationDate": None
        }
        
        print("Creando participación con datos:", new_participation)
        
        # Agregar la participación a Firestore
        doc_ref = db.collection('participations').document()
        doc_ref.set(new_participation)

        # Notificar al usuario
        challenge_title = challenge_data.get('title', 'el reto')
        send_notification(
            user_id=user_id,
            title="Participación iniciada",
            message=f"Has iniciado tu participación en {challenge_title}. Realiza el pago para continuar.",
            notification_type="participation"
        )
        
        # Notificar a los administradores
        send_admin_notification(
            title="Nueva participación pendiente",
            message=f"El usuario {request.user.get('email')} ha iniciado participación en {challenge_title}. Verifica el pago."
        )
        
        return jsonify({
            "message": "Participación iniciada. Realiza el pago según las instrucciones.",
            "participationId": doc_ref.id
        }), 201
        
    except Exception as e:
        print(f"Error completo en initiate_participation: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Error al iniciar participación: {str(e)}"}), 500
    
@participation_bp.route('/pending-results', methods=['GET'])
@admin_required
def get_pending_results():
    try:
        # Obtener todas las participaciones con pago confirmado y puntaje asignado
        participations_ref = db.collection('participations')
        query = participations_ref.where('paymentStatus', '==', 'confirmed') \
                                 .where('score', '>', 0) \
                                 .order_by('score', direction=firestore.Query.DESCENDING)
        
        pending_results = []
        
        for doc in query.stream():
            part_data = doc.to_dict()
            part_data['id'] = doc.id
            
            # Obtener datos del reto asociado
            challenge_ref = db.collection('challenges').document(part_data['challengeId'])
            challenge = challenge_ref.get()
            
            if not challenge.exists:
                continue
                
            challenge_data = challenge.to_dict()
            
            # Solo incluir si el reto no tiene ganador asignado aún
            if not challenge_data.get('winnerUserId'):
                # Obtener datos del usuario
                user_ref = db.collection('users').document(part_data['userId'])
                user = user_ref.get()
                
                if user.exists:
                    part_data['user'] = user.to_dict()
                
                part_data['challenge'] = challenge_data
                pending_results.append(part_data)
        
        return jsonify({
            "success": True,
            "count": len(pending_results),
            "results": pending_results
        }), 200
        
    except Exception as e:
        print(f"Error en get_pending_results: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Error al obtener resultados pendientes",
            "details": str(e)
        }), 500

# participation_routes.py
@participation_bp.route('/<participation_id>/submit', methods=['PUT'])
@firebase_token_required
def submit_score_and_code(participation_id):
    try:
        data = request.get_json()
        score = data.get('score')
        code = data.get('code')
        aceptaelreto_username = data.get('aceptaelretoUsername')
        
        # Validaciones básicas
        if not all([score, code, aceptaelreto_username]):
            return jsonify({"error": "Faltan datos requeridos"}), 400

        # Obtener participación
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        
        if not participation.exists:
            return jsonify({"error": "Participación no encontrada"}), 404
            
        participation_data = participation.to_dict()
        
        # Verificar que el usuario es el dueño de la participación
        if participation_data['userId'] != request.user['uid']:
            print(f"UID no coincide: {participation_data['userId']} != {request.user['uid']}")
            return jsonify({"error": "No autorizado"}), 403
            
        # Verificar que el pago está confirmado
        if not participation_data.get('isPaid', False):
            return jsonify({"error": "El pago no ha sido confirmado"}), 400
            
        # Actualizar el usuario con el aceptaelretoUsername si no existe
        user_ref = db.collection('users').document(request.user['uid'])
        user = user_ref.get()
        
        if user.exists and not user.to_dict().get('aceptaelretoUsername'):
            user_ref.update({
                "aceptaelretoUsername": aceptaelreto_username,
                "updatedAt": firestore.SERVER_TIMESTAMP
            })
        
        # Actualizar participación
        participation_ref.update({
            "score": int(score),
            "code": code,
            "aceptaelretoUsername": aceptaelreto_username,
            "submissionDate": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"message": "Resultados enviados exitosamente"}), 200
        
    except Exception as e:
        print(f"Error en submit_score_and_code: {str(e)}")
        return jsonify({"error": f"Error al enviar resultados: {str(e)}"}), 500

@participation_bp.route('/<participation_id>/code', methods=['GET'])
def get_participant_code(participation_id):
    try:
        participation = db.collection('participations').document(participation_id).get()
        if not participation.exists:
            return jsonify({"error": "Participación no encontrada"}), 404
            
        part_data = participation.to_dict()
        challenge = db.collection('challenges').document(part_data['challengeId']).get()
        
        # Solo permitir ver código si el reto ha finalizado
        if challenge.to_dict().get('status') != 'pasado':
            return jsonify({"error": "El código solo es visible después de finalizado el reto"}), 403
        
        # Obtener código directamente del documento
        code = part_data.get('code', '')
        
        return jsonify({
            "code": code,
            "username": db.collection('users').document(part_data['userId']).get().to_dict().get('username')
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener código: {str(e)}"}), 500

@participation_bp.route('/<participation_id>/notify-payment', methods=['POST'])
@firebase_token_required
def notify_payment(participation_id):
    try:
        # Verificar que la participación existe y pertenece al usuario
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        
        if not participation.exists:
            return jsonify({"error": "Participación no encontrada"}), 404
            
        if participation.to_dict()['userId'] != request.user['uid']:
            return jsonify({"error": "No autorizado"}), 403
            
        # Actualizar estado a "pending" (aunque ya debería estarlo)
        participation_ref.update({
            "paymentStatus": "pending",
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        
        # Notificar a los administradores
        send_admin_notification(
            title="Nuevo pago pendiente de verificación",
            message=f"El usuario {request.user.get('email')} ha notificado un pago para la participación {participation_id}."
        )
        
        return jsonify({"message": "Notificación de pago enviada a los administradores"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al notificar pago: {str(e)}"}), 500
    
@participation_bp.route('/status/<status>', methods=['GET'])
@admin_required
def get_participations_by_status(status):
    try:
        participations_ref = db.collection('participations').where('paymentStatus', '==', status)
        participations = []
        
        for doc in participations_ref.stream():
            part_data = doc.to_dict()
            part_data['id'] = doc.id
            
            # Obtener datos del usuario
            user_ref = db.collection('users').document(part_data['userId']).get()
            if user_ref.exists:
                part_data['user'] = user_ref.to_dict()
            
            # Obtener datos del reto
            challenge = db.collection('challenges').document(part_data['challengeId']).get()
            if challenge.exists:
                part_data['challenge'] = challenge.to_dict()
            
            participations.append(part_data)
            
        return jsonify(participations), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@participation_bp.route('/<participation_id>/confirm-payment', methods=['PUT'])
@admin_required
def confirm_payment(participation_id):
    try:
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        
        if not participation.exists:
            return jsonify({"error": "Participación no encontrada"}), 404
            
        participation_data = participation.to_dict()
        user_id = participation_data.get('userId')
        challenge_id = participation_data.get('challengeId')
        
        # Obtener el reto para actualizar el premio total
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge = challenge_ref.get()
        
        if not challenge.exists:
            return jsonify({"error": "Reto no encontrado"}), 404
            
        challenge_data = challenge.to_dict()
        participation_cost = challenge_data.get('participationCost', 0)
        
        # Actualizar participación
        participation_ref.update({
            "isPaid": True,
            "paymentStatus": "confirmed",
            "paymentConfirmationDate": firestore.SERVER_TIMESTAMP
        })
        
        # Actualizar el premio total del reto (incrementar)
        challenge_ref.update({
            "totalPot": firestore.Increment(participation_cost),
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        
        # Incrementar contador de participaciones del usuario
        db.collection('users').document(user_id).update({
            "totalParticipations": firestore.Increment(1),
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        
        # Notificar al usuario
        challenge_title = challenge_data.get('title', 'el reto')
        
        send_notification(
            user_id=user_id,
            title="Pago confirmado",
            message=f"Tu pago para {challenge_title} ha sido confirmado. ¡Ya puedes enviar tus resultados!",
            notification_type="payment"
        )
        
        return jsonify({
            "message": "Pago confirmado exitosamente. Premio total actualizado.",
            "newTotalPot": challenge_data.get('totalPot', 0) + participation_cost
        }), 200
    except Exception as e:
        print(f"Error al confirmar pago: {str(e)}")
        return jsonify({"error": f"Error al confirmar pago: {str(e)}"}), 500

@participation_bp.route('/<participation_id>', methods=['GET'])
@firebase_token_required
def get_participation_details(participation_id):
    try:
        # Obtener la participación
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        
        if not participation.exists:
            return jsonify({"error": "Participación no encontrada"}), 404
            
        part_data = participation.to_dict()
        
        # Verificar que el usuario es el dueño o admin
        if part_data['userId'] != request.user['uid']:
            # Solo permitir a admins ver otras participaciones
            user_ref = db.collection('users').document(request.user['uid']).get()
            if not user_ref.exists or user_ref.to_dict().get('role') != 'admin':
                return jsonify({"error": "No autorizado"}), 403
        
        # Obtener datos del reto
        challenge_ref = db.collection('challenges').document(part_data['challengeId']).get()
        if challenge_ref.exists:
            part_data['challenge'] = challenge_ref.to_dict()
        
        part_data['id'] = participation_id
        return jsonify(part_data), 200
        
    except Exception as e:
        print(f"Error en get_participation_details: {str(e)}")
        return jsonify({"error": "Error al obtener participación"}), 500
    
@participation_bp.route('/by-challenges', methods=['GET'])
def get_participations_by_challenge_ids():
    try:
        challenge_ids = request.args.get('challengeIds')
        if not challenge_ids:
            return jsonify({"error": "Se requieren IDs de retos"}), 400
        
        # Convertir a lista
        challenge_ids_list = challenge_ids.split(',')
        
        # Consulta para obtener solo participaciones confirmadas
        participations_ref = db.collection('participations')
        
        # Firestore no permite consultas con "IN" en más de 10 elementos, así que hacemos consultas separadas
        participations = []
        for chunk in [challenge_ids_list[i:i + 10] for i in range(0, len(challenge_ids_list), 10)]:
            query = participations_ref.where('challengeId', 'in', chunk) \
                                    .where('paymentStatus', '==', 'confirmed')
            
            for doc in query.stream():
                part_data = {
                    'id': doc.id,
                    'challengeId': doc.get('challengeId'),
                    'paymentStatus': doc.get('paymentStatus')
                }
                participations.append(part_data)
        
        return jsonify(participations), 200
        
    except Exception as e:
        print(f"Error en get_participations_by_challenge_ids: {str(e)}")
        return jsonify({"error": "Error al obtener participaciones"}), 500