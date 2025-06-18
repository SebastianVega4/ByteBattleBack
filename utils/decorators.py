from functools import wraps
from flask import request, jsonify
from firebase_admin import auth
from utils.firebase import db
from utils.exceptions import UnauthorizedError, ForbiddenError

def firebase_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise UnauthorizedError("Authentication token required")
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            request.user = decoded_token
            return f(*args, **kwargs)
        except auth.InvalidIdTokenError:
            raise UnauthorizedError("Invalid token")
        except auth.ExpiredIdTokenError:
            raise UnauthorizedError("Token expired")
        except Exception as e:
            raise UnauthorizedError(f"Authentication error: {str(e)}")
    return decorated_function

def admin_required(f):
    @wraps(f)
    @firebase_token_required
    def decorated_function(*args, **kwargs):
        user_doc = db.collection('users').document(request.user['uid']).get()
        if not user_doc.exists or user_doc.to_dict().get('role') != 'admin':
            raise ForbiddenError("Admin access required")
        return f(*args, **kwargs)
    return decorated_function