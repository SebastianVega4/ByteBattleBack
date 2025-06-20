from flask import Blueprint, request, jsonify
from models.Challenge import Challenge
from utils.firebase import db
from utils.decorators import firebase_token_required, admin_required
from datetime import datetime

challenge_bp = Blueprint('challenges', __name__)

@challenge_bp.route('', methods=['POST'])
@admin_required
def create_challenge():
    try:
        data = request.get_json()
        challenge = Challenge(
            title=data['title'],
            description=data['description'],
            start_date=datetime.fromisoformat(data['startDate']),
            end_date=datetime.fromisoformat(data['endDate']),
            participation_cost=data['participationCost'],
            created_by=request.user['uid']
        )
        
        _, doc_ref = db.collection('challenges').add(challenge.to_dict())
        
        return jsonify({
            "message": "Reto creado exitosamente",
            "challengeId": doc_ref.id
        }), 201
    except Exception as e:
        return jsonify({"error": f"Error al crear reto: {str(e)}"}), 500

@challenge_bp.route('', methods=['GET'])
def get_challenges():
    try:
        status = request.args.get('status')
        query = db.collection('challenges')
        
        if status:
            query = query.where('status', '==', status)
            
        challenges = [doc.to_dict() | {"id": doc.id} for doc in query.stream()]
        return jsonify(challenges), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener retos: {str(e)}"}), 500

@challenge_bp.route('/<challenge_id>', methods=['GET'])
def get_challenge(challenge_id):
    try:
        doc = db.collection('challenges').document(challenge_id).get()
        if not doc.exists:
            return jsonify({"error": "Reto no encontrado"}), 404
        return jsonify(doc.to_dict()), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener reto: {str(e)}"}), 500

@challenge_bp.route('/<challenge_id>/status', methods=['PUT'])
@admin_required
def update_challenge_status(challenge_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['próximo', 'activo', 'pasado']:
            return jsonify({"error": "Estado inválido"}), 400
            
        db.collection('challenges').document(challenge_id).update({
            "status": new_status
        })
        
        return jsonify({"message": "Estado actualizado exitosamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al actualizar estado: {str(e)}"}), 500

@challenge_bp.route('/<challenge_id>/mark-paid', methods=['PUT'])
@admin_required
def mark_challenge_as_paid(challenge_id):
    try:
        db.collection('challenges').document(challenge_id).update({
            "isPaidToWinner": True
        })
        return jsonify({"message": "Reto marcado como pagado"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al marcar como pagado: {str(e)}"}), 500
    
@challenge_bp.route('/<challenge_id>/winner', methods=['PUT'])
@admin_required
def set_winner(challenge_id):
    try:
        data = request.get_json()
        winner_id = data.get('winnerId')
        score = data.get('score')
        
        if not winner_id or not score:
            return jsonify({"error": "winnerId and score are required"}), 400
            
        # Actualizar reto con ganador
        db.collection('challenges').document(challenge_id).update({
            "winnerUserId": winner_id
        })
        
        # Actualizar participación del ganador
        participations = db.collection('participations') \
            .where('challengeId', '==', challenge_id) \
            .where('userId', '==', winner_id) \
            .limit(1) \
            .stream()
            
        for part in participations:
            part.reference.update({
                "winner": True,
                "score": score
            })
        
        return jsonify({"message": "Winner set successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Error setting winner: {str(e)}"}), 500
    
    