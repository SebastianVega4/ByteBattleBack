import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import os
from firebase_admin.exceptions import FirebaseError

def initialize_firebase():
    try:
        # Check if Firebase app is already initialized
        if firebase_admin._apps:
            return firebase_admin.get_app()
            
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
        cred = credentials.Certificate(cred_path)
        
        firebase_app = firebase_admin.initialize_app(cred, {
            'storageBucket': os.environ.get("FIREBASE_STORAGE_BUCKET")
        })
        
        return firebase_app
    except FirebaseError as e:
        print(f"Firebase initialization error: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error initializing Firebase: {str(e)}")
        raise

# Initialize Firebase and get components
firebase_app = initialize_firebase()
db = firestore.client()
storage_bucket = storage.bucket()