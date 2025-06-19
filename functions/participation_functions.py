from flask import jsonify, request
from firebase_admin import firestore
from utils.decorators import firebase_token_required, admin_required
from utils.exceptions import handle_error

db = firestore.client()

@firebase_token_required
def initiate_participation(request):
    try:
        data = request.get_json()
        user_id = request.user['uid']
        challenge_id = data['challengeId']
        
        # Verificar que el desafío existe y está activo
        challenge = db.collection('challenges').document(challenge_id).get()
        if not challenge.exists:
            return jsonify({'error': 'Challenge not found'}), 404
            
        challenge_data = challenge.to_dict()
        if challenge_data['status'] != 'active':
            return jsonify({'error': 'Challenge is not active'}), 400
            
        # Verificar que el usuario no está baneado
        user = db.collection('users').document(user_id).get()
        if not user.exists or user.to_dict().get('isBanned', False):
            return jsonify({'error': 'User is banned'}), 403
            
        # Verificar que el usuario no ha participado ya
        existing_participation = db.collection('participations') \
            .where('userId', '==', user_id) \
            .where('challengeId', '==', challenge_id) \
            .limit(1) \
            .stream()
            
        if len(list(existing_participation)) > 0:
            return jsonify({'error': 'User already participated in this challenge'}), 400
            
        # Crear participación
        participation_data = {
            'userId': user_id,
            'challengeId': challenge_id,
            'isPaid': False,
            'paymentStatus': 'pending',
            'participationCost': challenge_data['participationCost'],
            'createdAt': firestore.SERVER_TIMESTAMP
        }
        
        _, participation_ref = db.collection('participations').add(participation_data)
        
        return jsonify({
            'success': True,
            'message': 'Participation initiated. Please complete the payment.',
            'participationId': participation_ref.id,
            'paymentInstructions': {
                'amount': challenge_data['participationCost'],
                'nequiNumber': '3101234567',  # Número de Nequi del administrador
                'reference': f"{user_id}-{challenge_id}"
            }
        }), 201
        
    except Exception as e:
        return handle_error(e)

@admin_required
def confirm_payment(request, participation_id):
    try:
        # Verificar que la participación existe
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        
        if not participation.exists:
            return jsonify({'error': 'Participation not found'}), 404
            
        # Actualizar estado de pago
        participation_ref.update({
            'isPaid': True,
            'paymentStatus': 'confirmed',
            'paymentConfirmationDate': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({
            'success': True,
            'message': 'Payment confirmed successfully'
        }), 200
        
    except Exception as e:
        return handle_error(e)

@firebase_token_required
def submit_score_and_code(request, participation_id):
    try:
        data = request.get_json()
        user_id = request.user['uid']
        
        # Verificar que la participación existe y pertenece al usuario
        participation_ref = db.collection('participations').document(participation_id)
        participation = participation_ref.get()
        
        if not participation.exists:
            return jsonify({'error': 'Participation not found'}), 404
            
        participation_data = participation.to_dict()
        if participation_data['userId'] != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
            
        if not participation_data['isPaid']:
            return jsonify({'error': 'Payment not confirmed'}), 400
            
        # Verificar que el desafío sigue activo
        challenge = db.collection('challenges').document(participation_data['challengeId']).get()
        if not challenge.exists or challenge.to_dict()['status'] != 'active':
            return jsonify({'error': 'Challenge is not active'}), 400
            
        # Actualizar participación con puntaje y código
        updates = {
            'score': int(data['score']),
            'code': data['code'],
            'aceptaelretoUsername': data.get('aceptaelretoUsername'),
            'submissionDate': firestore.SERVER_TIMESTAMP
        }
        
        participation_ref.update(updates)
        
        return jsonify({
            'success': True,
            'message': 'Score and code submitted successfully'
        }), 200
        
    except Exception as e:
        return handle_error(e)

def get_leaderboard(request, challenge_id):
    try:
        # Obtener todas las participaciones confirmadas con puntaje
        participations = db.collection('participations') \
            .where('challengeId', '==', challenge_id) \
            .where('isPaid', '==', True) \
            .where('score', '>', 0) \
            .order_by('score', direction=firestore.Query.DESCENDING) \
            .stream()
            
        leaderboard = []
        
        for doc in participations:
            participation = doc.to_dict()
            participation['id'] = doc.id
            
            # Obtener información del usuario
            user = db.collection('users').document(participation['userId']).get()
            if user.exists:
                user_data = user.to_dict()
                participation['user'] = {
                    'name': user_data.get('name'),
                    'email': user_data.get('email'),
                    'aceptaelretoUsername': user_data.get('aceptaelretoUsername')
                }
                
            leaderboard.append(participation)
            
        return jsonify(leaderboard), 200
        
    except Exception as e:
        return handle_error(e)

def get_participant_code(request, participation_id):
    try:
        # Verificar que la participación existe
        participation = db.collection('participations').document(participation_id).get()
        
        if not participation.exists:
            return jsonify({'error': 'Participation not found'}), 404
            
        participation_data = participation.to_dict()
        
        # Verificar que el desafío es pasado
        challenge = db.collection('challenges').document(participation_data['challengeId']).get()
        if not challenge.exists or challenge.to_dict()['status'] != 'past':
            return jsonify({'error': 'Challenge is not past'}), 403
            
        return jsonify({
            'code': participation_data.get('code', '')
        }), 200
        
    except Exception as e:
        return handle_error(e)