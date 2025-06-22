from datetime import datetime
from firebase_admin import firestore

class User:
    def __init__(self, uid, email, username, role="user", is_banned=False, aceptaelreto_username=None,
                 description=None, institution=None, professional_title=None, university_career=None,
                 age=None, challenge_wins=0, total_participations=0, total_earnings=0,
                 profile_picture_url=None, email_verified=False, verified=False):
        self.uid = uid
        self.email = email
        self.username = username
        self.role = role
        self.is_banned = is_banned
        self.aceptaelreto_username = aceptaelreto_username
        self.description = description
        self.institution = institution
        self.professional_title = professional_title
        self.university_career = university_career
        self.age = age
        self.challenge_wins = challenge_wins
        self.total_participations = total_participations
        self.total_earnings = total_earnings
        self.profile_picture_url = profile_picture_url
        self.email_verified = email_verified
        self.verified = verified
        self.created_at = firestore.SERVER_TIMESTAMP
        self.updated_at = firestore.SERVER_TIMESTAMP

    def to_dict(self):
        return {
            "uid": self.uid,
            "email": self.email,
            "username": self.username,
            "role": self.role,
            "isBanned": self.is_banned,
            "aceptaelretoUsername": self.aceptaelreto_username,
            "description": self.description,
            "institution": self.institution,
            "professionalTitle": self.professional_title,
            "universityCareer": self.university_career,
            "age": self.age,
            "challengeWins": self.challenge_wins,
            "totalParticipations": self.total_participations,
            "totalEarnings": self.total_earnings,
            "profilePictureUrl": self.profile_picture_url,
            "emailVerified": self.email_verified,
            "verified": self.verified,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }