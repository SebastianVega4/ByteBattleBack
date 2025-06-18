from flask import Blueprint, request, jsonify
from models.Participation import Participation
from utils.firebase import db
from utils.decorators import firebase_token_required, admin_required
from firebase_admin import firestore
from utils.exceptions import ValidationError

participation_bp = Blueprint('participations', __name__)
MAX_CODE_LENGTH = 10000  # Límite de 10,000 caracteres para el código

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

@participation_bp.route('/<participation_id>/submit', methods=['PUT'])
@firebase_token_required
def submit_score_and_code(participation_id):
    try:
        data = request.get_json()
        score = data.get('score')
        code = data.get('code')
        
        # Validar longitud del código
        if code and len(code) > MAX_CODE_LENGTH:
            raise ValidationError(f"El código excede el límite de {MAX_CODE_LENGTH} caracteres")
        
        # Verificar que la participación existe y pertenece al usuario
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        if not participation.exists:
            return jsonify({"error": "Participación no encontrada"}), 404
        if participation.to_dict().get('userId') != request.user['uid']:
            return jsonify({"error": "No autorizado"}), 403
        
        # Actualizar participación (ahora guardamos el código directamente)
        participation_ref.update({
            "score": score,
            "code": code,  # Guardamos el código como texto plano
            "submissionDate": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"message": "Resultados enviados exitosamente"}), 200
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
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