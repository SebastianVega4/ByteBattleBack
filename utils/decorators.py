from functools import wraps
from flask import request, jsonify
from firebase_admin import auth
from utils.firebase import db
from utils.exceptions import UnauthorizedError, ForbiddenError

# decorators.py
def firebase_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("Token de autenticación faltante en el encabezado")
            raise UnauthorizedError("Authentication token required")
        
        token = auth_header.split('Bearer ')[1]
        try:
            print(f"Verificando token: {token}")
            decoded_token = auth.verify_id_token(token)
            print(f"Token decodificado: {decoded_token}")

            request.user = {
                'uid': decoded_token['uid'],
                'email': decoded_token.get('email', '')
            }
            return f(*args, **kwargs)
        except auth.InvalidIdTokenError:
            print("Token inválido")
            raise UnauthorizedError("Invalid token")
        except auth.ExpiredIdTokenError:
            raise UnauthorizedError("Token expired")
        except Exception as e:
            raise UnauthorizedError(f"Authentication error: {str(e)}")
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar el header Authorization
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Token de autenticación requerido"}), 401

        token = auth_header.split(' ')[1]
        try:
            # Verificar el token con Firebase Admin
            decoded_token = auth.verify_id_token(token)
            request.user = decoded_token  # Almacenar el usuario en el request

            # Verificar si el usuario es admin (usando Firestore)
            user_ref = db.collection('users').document(decoded_token['uid']).get()
            if not user_ref.exists or user_ref.to_dict().get('role') != 'admin':
                return jsonify({"error": "Se requieren privilegios de administrador"}), 403

        except Exception as e:
            return jsonify({"error": f"Token inválido: {str(e)}"}), 401

        return f(*args, **kwargs)
    return decorated_function