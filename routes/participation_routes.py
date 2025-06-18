from flask import Blueprint, request, jsonify
from models.Participation import Participation
from utils.firebase import db, storage_bucket
from utils.decorators import firebase_token_required, admin_required
import uuid

participation_bp = Blueprint('participations', __name__)

@participation_bp.route('', methods=['POST'])
@firebase_token_required
def initiate_participation():
    try:
        data = request.get_json()
        challenge_id = data.get('challengeId')
        user_id = request.user['uid']
        
        # Verificar si el reto existe y está activo
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge = challenge_ref.get()
        if not challenge.exists:
            return jsonify({"error": "Reto no encontrado"}), 404
        if challenge.to_dict().get('status') != 'activo':
            return jsonify({"error": "El reto no está activo"}), 400
        
        # Crear participación
        participation = Participation(user_id, challenge_id)
        _, doc_ref = db.collection('participations').add(participation.to_dict())
        
        return jsonify({
            "message": "Participación iniciada. Realiza el pago según las instrucciones.",
            "participationId": doc_ref.id
        }), 201
    except Exception as e:
        return jsonify({"error": f"Error al iniciar participación: {str(e)}"}), 500

@participation_bp.route('/<participation_id>/confirm-payment', methods=['PUT'])
@admin_required
def confirm_payment(participation_id):
    try:
        participation_ref = db.collection('participations').document(participation_id)
        participation_ref.update({
            "isPaid": True,
            "paymentStatus": "confirmed",
            "paymentConfirmationDate": firestore.SERVER_TIMESTAMP
        })
        return jsonify({"message": "Pago confirmado exitosamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al confirmar pago: {str(e)}"}), 500

@participation_bp.route('/<participation_id>/submit', methods=['PUT'])
@firebase_token_required
def submit_score_and_code(participation_id):
    try:
        data = request.get_json()
        score = data.get('score')
        code = data.get('code')
        
        # Verificar que la participación existe y pertenece al usuario
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        if not participation.exists:
            return jsonify({"error": "Participación no encontrada"}), 404
        if participation.to_dict().get('userId') != request.user['uid']:
            return jsonify({"error": "No autorizado"}), 403
        
        # Guardar código en Cloud Storage
        code_path = f"code/{uuid.uuid4()}.txt"
        blob = storage_bucket.blob(code_path)
        blob.upload_from_string(code)
        
        # Actualizar participación
        participation_ref.update({
            "score": score,
            "codeStoragePath": code_path,
            "submissionDate": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"message": "Resultados enviados exitosamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al enviar resultados: {str(e)}"}), 500

@participation_bp.route('/challenge/<challenge_id>/leaderboard', methods=['GET'])
def get_leaderboard(challenge_id):
    try:
        participations = db.collection('participations') \
            .where('challengeId', '==', challenge_id) \
            .where('paymentStatus', '==', 'confirmed') \
            .order_by('score', direction=firestore.Query.DESCENDING) \
            .stream()
            
        leaderboard = []
        for part in participations:
            part_data = part.to_dict()
            user_data = db.collection('users').document(part_data['userId']).get().to_dict()
            leaderboard.append({
                "username": user_data.get('username'),
                "score": part_data.get('score'),
                "submissionDate": part_data.get('submissionDate')
            })
            
        return jsonify(leaderboard), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener clasificación: {str(e)}"}), 500

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
        
        # Obtener código de Cloud Storage
        blob = storage_bucket.blob(part_data['codeStoragePath'])
        code = blob.download_as_text()
        
        return jsonify({
            "code": code,
            "username": db.collection('users').document(part_data['userId']).get().to_dict().get('username')
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener código: {str(e)}"}), 500