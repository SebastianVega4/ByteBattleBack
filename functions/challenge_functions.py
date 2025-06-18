from firebase_admin import firestore
from utils.firebase import db
from utils.decorators import admin_required

@admin_required
def calculate_and_set_winner(challenge_id):
    try:
        # Obtener todas las participaciones confirmadas ordenadas por puntaje
        participations = db.collection('participations') \
            .where('challengeId', '==', challenge_id) \
            .where('paymentStatus', '==', 'confirmed') \
            .order_by('score', direction=firestore.Query.DESCENDING) \
            .limit(1) \
            .stream()
        
        winner = None
        for part in participations:
            winner = part.to_dict().get('userId')
            break
        
        if not winner:
            return {"error": "No hay participantes válidos"}, 400
        
        # Contar participaciones confirmadas para calcular el premio
        count = db.collection('participations') \
            .where('challengeId', '==', challenge_id) \
            .where('paymentStatus', '==', 'confirmed') \
            .count().get()[0][0].value
        
        challenge = db.collection('challenges').document(challenge_id).get()
        participation_cost = challenge.to_dict().get('participationCost', 0)
        total_pot = count * participation_cost
        
        # Actualizar reto con ganador y premio
        db.collection('challenges').document(challenge_id).update({
            "winnerUserId": winner,
            "totalPot": total_pot
        })
        
        return {"message": "Ganador calculado y asignado", "winner": winner, "totalPot": total_pot}
    except Exception as e:
        return {"error": str(e)}