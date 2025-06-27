from flask import Blueprint, request, jsonify
from models.Challenge import Challenge
from utils.firebase import db
from utils.decorators import firebase_token_required, admin_required
from datetime import datetime

challenge_bp = Blueprint('challenges', __name__)

@challenge_bp.route('', methods=['POST'])
@firebase_token_required
def create_challenge():
    try:
        data = request.get_json()
        
        # Convertir fechas ISO a datetime
        start_date = datetime.fromisoformat(data['startDate'])
        end_date = datetime.fromisoformat(data['endDate'])
        participation_cost = float(data['participationCost'])
        
        challenge = Challenge(
            title=data['title'],
            description=data['description'],
            start_date=start_date,
            end_date=end_date,
            participation_cost=participation_cost,
            created_by=request.user['uid'],
            link_challenge=data.get('linkChallenge')
        )
        
        challenge.total_pot = 0
        
        _, doc_ref = db.collection('challenges').add(challenge.to_dict())
        
        return jsonify({
            "message": "Reto creado exitosamente",
            "challengeId": doc_ref.id,
            "totalPot": participation_cost
        }), 201
    except Exception as e:
        return jsonify({"error": f"Error al crear reto: {str(e)}"}), 500
    

@challenge_bp.route('/<challenge_id>', methods=['PUT'])
@firebase_token_required
def update_challenge(challenge_id):
    try:
        data = request.get_json()
        challenge_ref = db.collection('challenges').document(challenge_id)
        
        if not challenge_ref.get().exists:
            return jsonify({"error": "Reto no encontrado"}), 404
        
        updates = {
            "title": data.get('title'),
            "description": data.get('description'),
            "participationCost": data.get('participationCost'),
            "status": data.get('status')
        }
        
        # Actualizar solo campos proporcionados
        challenge_ref.update({k: v for k, v in updates.items() if v is not None})
        
        return jsonify({"message": "Reto actualizado exitosamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al actualizar reto: {str(e)}"}), 500
    
@challenge_bp.route('', methods=['GET'])
def get_challenges():
    try:
        status = request.args.get('status')
        query = db.collection('challenges')
        
        if status:
            query = query.where('status', '==', status)
            
        challenges = []
        for doc in query.stream():
            challenge_data = doc.to_dict()
            challenge_data['id'] = doc.id  # Incluir el ID del documento
            challenges.append(challenge_data)
            
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
@firebase_token_required
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

@challenge_bp.route('/<challenge_id>/winner', methods=['PUT'])
@firebase_token_required
def set_winner(challenge_id):
    try:
        data = request.get_json()
        winner_id = data.get('winnerId')
        score = data.get('score')
        
        if not winner_id or not score:
            return jsonify({"error": "winnerId and score are required"}), 400
            
        # Obtener el reto
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge = challenge_ref.get().to_dict()
        
        if not challenge:
            return jsonify({"error": "Reto no encontrado"}), 404
            
        # Verificar que el reto no tenga ya un ganador
        if challenge.get('winnerUserId'):
            return jsonify({"error": "Este reto ya tiene un ganador asignado"}), 400
            
        # Actualizar reto con ganador
        challenge_ref.update({
            "winnerUserId": winner_id,
            "updatedAt": firestore.SERVER_TIMESTAMP
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
                "score": score,
                "updatedAt": firestore.SERVER_TIMESTAMP
            })
        
        # Actualizar estadísticas del usuario ganador
        user_ref = db.collection('users').document(winner_id)
        user_ref.update({
            "challengeWins": firestore.Increment(1),
            "totalEarnings": firestore.Increment(challenge['totalPot']),
            "updatedAt": firestore.SERVER_TIMESTAMP
        })

        # 1. Notificar al ganador
        send_notification(
            user_id=winner_id,
            title="¡Has ganado un reto!",
            message=f"Felicidades, has ganado el reto '{challenge['title']}' con un premio de ${challenge['totalPot']}",
            notification_type="challenge_win"
        )

        # 2. Notificar a todos los demás participantes
        participants = db.collection('participations') \
            .where('challengeId', '==', challenge_id) \
            .stream()

        winner_username = db.collection('users').document(winner_id).get().to_dict().get('username', 'un participante')
        
        for part in participants:
            participant_id = part.to_dict()['userId']
            if participant_id != winner_id:  # No notificar al ganador otra vez
                send_notification(
                    user_id=participant_id,
                    title="Reto finalizado",
                    message=f"El reto '{challenge['title']}' ha finalizado. El ganador fue {winner_username}. ¡Gracias por participar!",
                    notification_type="challenge_end"
                )
        
        return jsonify({
            "message": "Ganador establecido correctamente",
            "challengeId": challenge_id,
            "winnerId": winner_id,
            "prizeAmount": challenge['totalPot']
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error al establecer ganador: {str(e)}"}), 500
    
@challenge_bp.route('/<challenge_id>/mark-paid', methods=['PUT'])
@firebase_token_required
def mark_challenge_as_paid(challenge_id):
    try:
        # Verificar que el reto existe y tiene un ganador
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge = challenge_ref.get().to_dict()
        
        if not challenge:
            return jsonify({"error": "Reto no encontrado"}), 404
            
        if not challenge.get('winnerUserId'):
            return jsonify({"error": "El reto no tiene un ganador asignado"}), 400
            
        # Marcar como pagado
        challenge_ref.update({
            "isPaidToWinner": True,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"message": "Reto marcado como pagado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al marcar como pagado: {str(e)}"}), 500
    
@challenge_bp.route('/<challenge_id>/participations', methods=['GET'])
def get_challenge_participations(challenge_id):
    try:
        # Verificar que el reto existe
        challenge_ref = db.collection('challenges').document(challenge_id)
        if not challenge_ref.get().exists:
            return jsonify({"error": "Reto no encontrado"}), 404

        # Obtener TODAS las participaciones del reto
        participations_ref = db.collection('participations').where('challengeId', '==', challenge_id)
        participations = []
        
        for doc in participations_ref.stream():
            part_data = doc.to_dict()
            part_data['id'] = doc.id
            
            # Obtener datos del usuario
            user_ref = db.collection('users').document(part_data['userId']).get()
            if user_ref.exists:
                part_data['user'] = user_ref.to_dict()
            
            participations.append(part_data)
            
        # Ordenar por puntaje descendente (los nulls van al final)
        participations.sort(key=lambda x: (-x.get('score', float('-inf')) if x.get('score') is not None else float('inf')))
        
        return jsonify(participations), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500