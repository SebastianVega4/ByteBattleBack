import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from firebase_admin.exceptions import FirebaseError

def initialize_firebase():
    try:
        # Check if Firebase app is already initialized
        if firebase_admin._apps:
            return firebase_admin.get_app()
            
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
        
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"Firebase credentials file not found at {cred_path}")
        
        cred = credentials.Certificate(cred_path)
        firebase_app = firebase_admin.initialize_app(cred)
        
        return firebase_app
    except FirebaseError as e:
        print(f"Firebase initialization error: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error initializing Firebase: {str(e)}")
        raise

# Initialize Firebase and get Firestore client
firebase_app = initialize_firebase()
db = firestore.client()