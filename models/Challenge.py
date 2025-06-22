from datetime import datetime
from firebase_admin import firestore

class Challenge:
    def __init__(self, title, description, start_date, end_date, participation_cost, created_by, id=None):
        self.id = id
        self.title = title
        self.description = description
        self.start_date = start_date
        self.end_date = end_date
        self.participation_cost = participation_cost
        self.status = "próximo"  # próximo, activo, pasado
        self.is_paid_to_winner = False
        self.winner_user_id = None
        self.total_pot = participation_cost
        self.created_at = firestore.SERVER_TIMESTAMP
        self.created_by = created_by
        self.updated_at = firestore.SERVER_TIMESTAMP

    def to_dict(self):
        data = {
            "title": self.title,
            "description": self.description,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "participationCost": self.participation_cost,
            "status": self.status,
            "isPaidToWinner": self.is_paid_to_winner,
            "winnerUserId": self.winner_user_id,
            "totalPot": self.total_pot,
            "createdAt": self.created_at,
            "createdBy": self.created_by
        }
        if self.id:
            data['id'] = self.id
        return data