from firebase_admin import firestore

# En Participation.py
class Participation:
    def __init__(self, user_id, challenge_id):
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.status = "pending"  # Agregar status
        self.score = None
        self.code = None
        self.submission_date = None
        self.is_paid = False
        self.payment_status = "pending"  # pending, confirmed, rejected
        self.created_at = firestore.SERVER_TIMESTAMP
        self.payment_confirmation_date = None
        self.winner_user_id = None  # Agregar para ganador
        self.total_pot = 0  # Agregar para premio total
        

    def to_dict(self):
        return {
            "userId": self.user_id,
            "challengeId": self.challenge_id,
            "score": self.score,
            "code": self.code,  # Campo de texto para el código
            "submissionDate": self.submission_date,
            "isPaid": self.is_paid,
            "paymentStatus": self.payment_status,
            "createdAt": self.created_at,
            "paymentConfirmationDate": self.payment_confirmation_date
        }