# admin_routes.py
from flask import Blueprint, request, jsonify
from firebase_admin import firestore
from datetime import datetime
from utils.firebase import db
from utils.decorators import admin_required
from utils.exceptions import handle_error

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    try:
        page_index = int(request.args.get('pageIndex', 0))
        page_size = int(request.args.get('pageSize', 10))
        
        users_ref = db.collection('users')
        total_docs = users_ref.count().get()[0][0].value
        
        query = users_ref.order_by('createdAt').limit(page_size)
        
        if page_index > 0:
            last_doc = users_ref.order_by('createdAt').offset((page_index) * page_size - 1).limit(1).get()[0]
            query = query.start_after(last_doc)
        
        users = []
        for doc in query.stream():
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            users.append(user_data)
            
        return jsonify({
            "users": users,
            "total": total_docs
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/set-admin-role', methods=['POST'])
@admin_required
def set_admin_role_route():
    try:
        data = request.get_json()
        user_id = data.get('uid')
        role = data.get('role', 'user')  # 'admin' o 'user'
        
        # Validar que el rol sea válido
        if role not in ['admin', 'user']:
            return jsonify({"success": False, "message": "Rol inválido"}), 400
        
        # Actualizar en Firestore
        db.collection('users').document(user_id).update({
            'role': role,
            'updatedAt': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": f"Rol actualizado a {role} correctamente"
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/ban-user', methods=['POST'])
@admin_required
def ban_user_route():
    try:
        data = request.get_json()
        user_id = data.get('uid')
        is_banned = data.get('isBanned', True)
        
        # Actualizar en Firestore
        db.collection('users').document(user_id).update({
            'isBanned': is_banned,
            'updatedAt': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": f"Usuario {'baneado' if is_banned else 'desbaneado'} correctamente"
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/challenges', methods=['GET', 'POST'])
@admin_required
def challenges_route():
    if request.method == 'GET':
        try:
            status = request.args.get('status')
            
            challenges_ref = db.collection('challenges')
            if status:
                challenges_ref = challenges_ref.where('status', '==', status)
                
            challenges = []
            for doc in challenges_ref.stream():
                challenge_data = doc.to_dict()
                challenge_data['id'] = doc.id
                challenges.append(challenge_data)
                
            return jsonify(challenges), 200
        except Exception as e:
            return handle_error(e)
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Validación básica
            required_fields = ['title', 'description', 'startDate', 'endDate', 'participationCost']
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Campo requerido faltante: {field}"}), 400
            
            # Crear nuevo reto
            challenge_data = {
                'title': data['title'],
                'description': data['description'],
                'startDate': datetime.fromisoformat(data['startDate']),
                'endDate': datetime.fromisoformat(data['endDate']),
                'participationCost': float(data['participationCost']),
                'status': data.get('status', 'próximo'),
                'isPaidToWinner': False,
                'winnerUserId': None,
                'totalPot': 0,
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow(),
                'createdByUserId': request.user['uid']
            }
            
            _, doc_ref = db.collection('challenges').add(challenge_data)
            
            return jsonify({
                "success": True,
                "message": "Reto creado correctamente",
                "id": doc_ref.id
            }), 201
        except Exception as e:
            return handle_error(e)

@admin_bp.route('/challenges/<challenge_id>', methods=['PUT'])
@admin_required
def update_challenge_route(challenge_id):
    try:
        data = request.get_json()
        
        # Validación básica
        required_fields = ['title', 'description', 'startDate', 'endDate', 'participationCost']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Campo requerido faltante: {field}"}), 400
        
        # Actualizar reto
        db.collection('challenges').document(challenge_id).update({
            'title': data['title'],
            'description': data['description'],
            'startDate': datetime.fromisoformat(data['startDate']),
            'endDate': datetime.fromisoformat(data['endDate']),
            'participationCost': float(data['participationCost']),
            'status': data.get('status', 'próximo'),
            'updatedAt': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Reto actualizado correctamente"
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/challenges/<challenge_id>/status', methods=['PUT'])
@admin_required
def update_challenge_status_route(challenge_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['próximo', 'activo', 'pasado']:
            return jsonify({"error": "Estado inválido"}), 400
        
        db.collection('challenges').document(challenge_id).update({
            'status': new_status,
            'updatedAt': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": f"Estado del reto actualizado a {new_status}"
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/challenges/<challenge_id>/mark-as-paid', methods=['PUT'])
@admin_required
def mark_challenge_as_paid_route(challenge_id):
    try:
        # Verificar que el reto tenga un ganador
        challenge_ref = db.collection('challenges').document(challenge_id)
        challenge = challenge_ref.get().to_dict()
        
        if not challenge.get('winnerUserId'):
            return jsonify({"error": "El reto no tiene un ganador asignado"}), 400
        
        # Marcar como pagado
        challenge_ref.update({
            'isPaidToWinner': True,
            'updatedAt': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Reto marcado como pagado correctamente"
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/participations', methods=['GET'])
@admin_required
def get_participations():
    try:
        status = request.args.get('status')
        challenge_id = request.args.get('challengeId')
        
        participations_ref = db.collection('participations')
        
        if status:
            participations_ref = participations_ref.where('paymentStatus', '==', status)
        if challenge_id:
            participations_ref = participations_ref.where('challengeId', '==', challenge_id)
            
        participations = []
        for doc in participations_ref.stream():
            participation_data = doc.to_dict()
            participation_data['id'] = doc.id
            participations.append(participation_data)
            
        return jsonify({
            "participations": participations,
            "total": len(participations)
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/confirm-payment', methods=['POST'])
@admin_required
def confirm_payment_route():
    try:
        data = request.get_json()
        participation_id = data.get('participationId')
        
        # Actualizar en Firestore
        db.collection('participations').document(participation_id).update({
            'isPaid': True,
            'paymentStatus': 'confirmed',
            'paymentConfirmationDate': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Pago confirmado correctamente"
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/set-winner', methods=['POST'])
@admin_required
def set_winner_route():
    try:
        data = request.get_json()
        challenge_id = data.get('challengeId')
        winner_id = data.get('winnerId')
        
        # Actualizar el reto con el ganador
        db.collection('challenges').document(challenge_id).update({
            'winnerUserId': winner_id,
            'updatedAt': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Ganador establecido correctamente"
        }), 200
    except Exception as e:
        return handle_error(e)

@admin_bp.route('/mark-as-paid', methods=['POST'])
@admin_required
def mark_as_paid_route():
    try:
        data = request.get_json()
        challenge_id = data.get('challengeId')
        
        # Actualizar el reto como pagado
        db.collection('challenges').document(challenge_id).update({
            'isPaidToWinner': True,
            'updatedAt': datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Reto marcado como pagado correctamente"
        }), 200
    except Exception as e:
        return handle_error(e)