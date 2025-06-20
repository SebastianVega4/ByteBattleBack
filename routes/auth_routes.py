from flask import Blueprint, request, jsonify
from utils.exceptions import handle_error
from utils.decorators import firebase_token_required, admin_required
from firebase_admin import auth, firestore
from functions.auth_functions import register_user  # Importar función de registro
import re
from datetime import datetime
from firebase_admin.exceptions import FirebaseError
import os
import requests

auth_bp = Blueprint('auth', __name__)

db = firestore.client()

@auth_bp.route('/register', methods=['POST'])
def register_user_route():
    try:
        data = request.get_json()
        
        # Validar datos de entrada
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password')
        username = data.get('username', '').strip()

        # Validaciones básicas
        if not username:
            return jsonify({"success": False, "message": "El username es obligatorio"}), 400
        if not email:
            return jsonify({"success": False, "message": "El email es obligatorio"}), 400
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"success": False, "message": "Formato de email inválido"}), 400
        if not password or len(password) < 6:
            return jsonify({"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}), 400
        if not username:
            return jsonify({"success": False, "message": "El nombre de usuario es obligatorio"}), 400

        # Verificar si el email ya existe
        try:
            auth.get_user_by_email(email)
            return jsonify({
                "success": False,
                "message": "El correo electrónico ya está registrado",
                "code": "email_already_exists"
            }), 409
        except auth.UserNotFoundError:
            pass  # El usuario no existe, podemos continuar

        # Crear usuario en Firebase Auth
        user_record = auth.create_user(
            email=email,
            password=password,
            display_name=username
        )

        # Crear documento en Firestore
        user_data = {
            "uid": user_record.uid,
            "email": email,
            "username": username,
            "role": "user",
            "isBanned": False,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        db.collection('users').document(user_record.uid).set(user_data)

        return jsonify({
            "success": True,
            "message": "Usuario registrado con éxito",
            "user": {
                "id": user_record.uid,
                "email": email,
                "username": username
            }
        }), 201

    except auth.EmailAlreadyExistsError:
        return jsonify({
            "success": False,
            "message": "El correo electrónico ya está registrado",
            "code": "email_already_exists"
        }), 409
    except auth.WeakPasswordError:
        return jsonify({
            "success": False,
            "message": "La contraseña es demasiado débil",
            "code": "weak_password"
        }), 400
    except Exception as e:
        # Manejo detallado de errores
        error_message = f"Error en el registro: {str(e)}"
        print(error_message)
        return jsonify({
            "success": False,
            "message": "Error interno en el servidor",
            "code": "server_error",
            "details": str(e)
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login_user_route():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Email y contraseña son requeridos"
            }), 400
        
        # Verificar si el usuario existe en Firestore
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1).get()
        
        if not query:
            return jsonify({
                "success": False,
                "message": "Usuario no encontrado"
            }), 404
        
        user_doc = query[0]
        user_data = user_doc.to_dict()
        uid = user_doc.id
        
        # Verificar si el usuario está baneado
        if user_data.get('isBanned', False):
            return jsonify({
                "success": False,
                "message": "Tu cuenta ha sido suspendida"
            }), 403
        
        # Autenticar con Firebase usando el SDK de Admin
        try:
            # Verificar credenciales
            user = auth.get_user_by_email(email)
            
            # Crear token de sesión personalizado
            custom_token = auth.create_custom_token(user.uid)
            
            # Convertir bytes a string
            token_str = custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token
            
            # Respuesta exitosa
            return jsonify({
                "success": True,
                "message": "Inicio de sesión exitoso",
                "token": token_str,
                "user": {
                    "uid": uid,
                    "email": email,
                    "username": user_data['username'],
                    "role": user_data.get('role', 'user'),
                    "isBanned": user_data.get('isBanned', False)
                }
            }), 200
            
        except auth.UserNotFoundError:
            return jsonify({
                "success": False,
                "message": "Usuario no encontrado"
            }), 404
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Contraseña incorrecta"
            }), 401
        except FirebaseError as e:
            return jsonify({
                "success": False,
                "message": f"Error de Firebase: {str(e)}"
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error interno: {str(e)}"
        }), 500
    
@auth_bp.route('/admin/users', methods=['GET'])
@admin_required
def get_all_users():
    try:
        users_ref = db.collection('users')
        users = [doc.to_dict() for doc in users_ref.stream()]
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@auth_bp.route('/set-admin-role', methods=['POST'])
@admin_required
def set_admin_role_route():
    try:
        from functions.auth_functions import set_admin_role
        data = request.get_json()
        user_id = data.get('uid')
        current_user_id = request.user['uid']
        result = set_admin_role(user_id, current_user_id)
        return jsonify(result), 200
    except Exception as e:
        return handle_error(e)

@auth_bp.route('/ban-user', methods=['POST'])
@admin_required
def ban_user_route():
    try:
        from functions.auth_functions import ban_user
        data = request.get_json()
        user_id = data.get('uid')
        is_banned = data.get('isBanned', True)
        current_user_id = request.user['uid']
        result = ban_user(user_id, is_banned, current_user_id)
        return jsonify(result), 200
    except Exception as e:
        return handle_error(e)