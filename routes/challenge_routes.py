from flask import Blueprint, request, jsonify
from models.Challenge import Challenge
from utils.firebase import db
from utils.decorators import firebase_token_required, admin_required
from datetime import datetime
from firebase_admin import firestore
from services.notification_service import send_notification

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
        db = firestore.client()
        data = request.get_json()
        winner_id = data.get('winnerId')
        score = data.get('score')
        
        if not winner_id or not score:
            return jsonify({"error": "Se requieren winnerId y score"}), 400

        challenge_ref = db.collection('challenges').document(challenge_id)
        user_ref = db.collection('users').document(winner_id)
        
        challenge = challenge_ref.get()
        if not challenge.exists:
            return jsonify({"error": "Reto no encontrado"}), 404
            
        challenge_data = challenge.to_dict()
        
        if challenge_data.get('winnerUserId'):
            return jsonify({"error": "Este reto ya tiene un ganador"}), 400
            
        participations = db.collection('participations') \
            .where('challengeId', '==', challenge_id) \
            .where('userId', '==', winner_id) \
            .limit(1) \
            .stream()
            
        participation = next(participations, None)
        if not participation:
            return jsonify({"error": "Participación no encontrada"}), 404
            
        batch = db.batch()
        
        # 1. Marcar ganador en el reto
        batch.update(challenge_ref, {
            'winnerUserId': winner_id,
            'status': 'pasado', 
            'isPaidToWinner': True,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        
        # 2. Actualizar participación
        batch.update(participation.reference, {
            'winner': True,
            'score': score,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        
        # 3. Actualizar estadísticas del usuario
        total_pot = challenge_data.get('totalPot', 0)
        batch.update(user_ref, {
            'challengeWins': firestore.Increment(1),
            'totalEarnings': firestore.Increment(total_pot),
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        
        batch.commit()
        
        # Obtener datos para notificación
        user = user_ref.get().to_dict()
        winner_username = user.get('username', 'un participante')
        challenge_title = challenge_data.get('title', 'un reto')
        
        # Notificar al ganador
        send_notification(
            user_id=winner_id,
            title="¡Has ganado un reto!",
            message=f"Felicidades, has ganado el reto '{challenge_title}' con un premio de ${total_pot}",
            notification_type="challenge_win"
        )
        
        # Notificar a todos los participantes que no ganaron
        if challenge_data.get('status') == 'activo':
            # Solo si el reto estaba activo (para evitar notificaciones duplicadas)
            participants = db.collection('participations') \
                .where('challengeId', '==', challenge_id) \
                .where('userId', '!=', winner_id) \
                .stream()
            
            for part in participants:
                send_notification(
                    user_id=part.to_dict().get('userId'),
                    title="Resultado del reto",
                    message=f"El reto '{challenge_title}' ha finalizado. El ganador fue {winner_username}",
                    notification_type="challenge_result"
                )
        
        return jsonify({
            "success": True,
            "message": "Ganador asignado correctamente",
            "challengeId": challenge_id,
            "winnerId": winner_id,
            "prizeAmount": total_pot,
            "isPaid": True
        }), 200
        
    except Exception as e:
        print(f"Error al establecer ganador: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error interno: {str(e)}"
        }), 500   

@challenge_bp.route('/<challenge_id>/mark-paid', methods=['PUT'])
@admin_required
def mark_challenge_as_paid(challenge_id):
    try:
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge_doc = challenge_ref.get()
        
        if not challenge_doc.exists:
            return jsonify({
                "success": False,
                "message": "Reto no encontrado"
            }), 404
            
        challenge_data = challenge_doc.to_dict()
        winner_id = challenge_data.get('winnerUserId')
        
        if not winner_id:
            return jsonify({
                "success": False,
                "message": "El reto no tiene un ganador declarado"
            }), 400
            
        # Marcar como pagado
        challenge_ref.update({
            "isPaidToWinner": True,
            "updatedAt": datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Reto marcado como pagado"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al marcar reto como pagado: {str(e)}"
        }), 500
    
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

@challenge_bp.route('/<challenge_id>/declare-winner', methods=['POST'])
@admin_required
def declare_challenge_winner(challenge_id):
    try:
        data = request.get_json()
        winner_id = data.get('winner_id')
        score = data.get('score')
        
        if not winner_id or not score:
            return jsonify({
                "success": False,
                "message": "ID de ganador y puntaje requeridos"
            }), 400
            
        # 1. Obtener el reto para saber el premio
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge_doc = challenge_ref.get()
        
        if not challenge_doc.exists:
            return jsonify({
                "success": False,
                "message": "Reto no encontrado"
            }), 404
            
        challenge_data = challenge_doc.to_dict()
        prize_amount = challenge_data.get('totalPot', 0)
        
        # 2. Actualizar el reto con el ganador
        challenge_ref.update({
            "winnerUserId": winner_id,
            "status": "pasado",
            "isPaidToWinner": True,
            "updatedAt": datetime.utcnow()
        })
        
        # 3. Actualizar las estadísticas del ganador
        user_ref = db.collection('users').document(winner_id)
        
        # Verificar que el usuario existe
        if not user_ref.get().exists:
            return jsonify({
                "success": False,
                "message": "Usuario ganador no encontrado"
            }), 404
            
        # Actualizar victorias y ganancias
        user_ref.update({
            "challengeWins": firestore.Increment(1),
            "totalEarnings": firestore.Increment(prize_amount),
            "updatedAt": datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Ganador declarado y estadísticas actualizadas",
            "prize_amount": prize_amount
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al declarar ganador: {str(e)}"
        }), 500