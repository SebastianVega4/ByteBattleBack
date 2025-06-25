import firebase_admin
from firebase_admin import credentials, firestore
import os
from pathlib import Path

# Variables globales
_firebase_app = None
_db = None

def initialize_firebase():
    global _firebase_app, _db
    try:
        if _firebase_app is None:
            # Opción 1: Usar archivo JSON
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
            
            if Path(cred_path).exists():
                cred = credentials.Certificate(cred_path)
            else:
                # Opción 2: Variables de entorno
                private_key = os.environ.get("FIREBASE_PRIVATE_KEY")
                if not private_key:
                    raise ValueError("FIREBASE_PRIVATE_KEY no encontrada")
                
                firebase_config = {
                    "type": os.environ.get("FIREBASE_TYPE"),
                    "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
                    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
                    "private_key": private_key.replace('\\n', '\n'),
                    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
                    "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
                    "auth_uri": os.environ.get("FIREBASE_AUTH_URI"),
                    "token_uri": os.environ.get("FIREBASE_TOKEN_URI"),
                    "auth_provider_x509_cert_url": os.environ.get("FIREBASE_AUTH_PROVIDER_CERT_URL"),
                    "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_CERT_URL")
                }
                cred = credentials.Certificate(firebase_config)
            
            _firebase_app = firebase_admin.initialize_app(cred)
            _db = firestore.client()
        
        return _firebase_app, _db
    except Exception as e:
        print(f"🔥 Error inicializando Firebase: {str(e)}")
        raise

def get_db():
    if _db is None:
        initialize_firebase()
    return _db

# Inicialización inmediata al importar el módulo
firebase_app, db = initialize_firebase()