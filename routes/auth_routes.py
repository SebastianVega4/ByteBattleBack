from flask import Blueprint, redirect, request, jsonify
from utils.exceptions import handle_error
from utils.decorators import firebase_token_required, admin_required
from firebase_admin import auth, firestore
from utils.firebase import get_db
from functions.auth_functions import register_user  # Importar función de registro
import re
from datetime import datetime
from firebase_admin.exceptions import FirebaseError
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

auth_bp = Blueprint('auth', __name__)

# Configuración de correo
EMAIL_CONFIG = {
    'sender': os.getenv('EMAIL_SENDER', 'no-reply@bytebattle.com'),
    'reset_password_template': {
        'subject': 'Restablece tu contraseña en ByteBattle',
        'body': 'Hola,\n\nPara restablecer tu contraseña, haz clic en el siguiente enlace:\n{reset_link}\n\nSi no solicitaste este cambio, ignora este correo.\n\nEl equipo de ByteBattle'
    },
    'verify_email_template': {
        'subject': 'Verifica tu correo en ByteBattle',
        'body': 'Hola,\n\nPor favor verifica tu dirección de correo electrónico haciendo clic en el siguiente enlace:\n{verify_link}\n\nGracias,\nEl equipo de ByteBattle'
    }
}

def send_email_via_sendgrid(to_email, subject, body):
    """Función para enviar correos usando SendGrid"""
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    
    message = Mail(
        from_email=EMAIL_CONFIG['sender'],
        to_emails=to_email,
        subject=subject,
        plain_text_content=body
    )
    
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"Error enviando correo: {str(e)}")
        return False
    
#db = firestore.client()
db = get_db()

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

        # Crear documento en Firestore con todos los campos
        user_data = {
            "uid": user_record.uid,
            "email": email,
            "username": username,
            "role": "user",
            "isBanned": False,
            "description": "",
            "institution": "",
            "professionalTitle": "",
            "universityCareer": "",
            "age": None,
            "challengeWins": 0,
            "totalParticipations": 0,
            "totalEarnings": 0,
            "profilePictureUrl": "",  # URL de imagen genérica por defecto
            "emailVerified": False,
            "verified": False,
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
            return jsonify({"success": False, "message": "Email y contraseña son requeridos"}), 400
        
        firebase_key = os.getenv('FIREBASE_API_KEY')
        
        
        if not firebase_key:
            return jsonify({
                "success": False,
                "message": "Configuración del servidor incompleta: FIREBASE_API_KEY no está configurada"
            }), 500
            
        auth_url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_key}'
        auth_response = requests.post(auth_url, json={
            'email': email,
            'password': password,
            'returnSecureToken': True
        })
     
        if auth_response.status_code != 200:
            error_data = auth_response.json()
            error_message = error_data.get('error', {}).get('message', 'Credenciales inválidas')
            return jsonify({"success": False, "message": error_message}), 401
        
        # Obtener datos del usuario
        auth_data = auth_response.json()
        id_token = auth_data['idToken']
        uid = auth_data['localId']
        
        # Obtener datos adicionales de Firestore
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        user_data = user_doc.to_dict()
        
        if user_data.get('isBanned', False):
            return jsonify({"success": False, "message": "Tu cuenta ha sido suspendida"}), 403
        
        return jsonify({
            "success": True,
            "message": "Inicio de sesión exitoso",
            "token": id_token,
            "user": {
                "uid": uid,
                "email": email,
                "username": user_data['username'],
                "role": user_data.get('role', 'user'),
                "isBanned": user_data.get('isBanned', False),
                "aceptaelretoUsername": user_data.get('aceptaelretoUsername'),
                "createdAt": user_data.get('createdAt'),
                "updatedAt": user_data.get('updatedAt'),
                "profilePictureUrl": user_data.get('profilePictureUrl', ''),

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
    
@auth_bp.route('/<user_id>', methods=['GET'])
@firebase_token_required
def get_user_profile(user_id):
    try:
        # Verificar permisos
        if request.user['uid'] != user_id and request.user.get('role') != 'admin':
            return jsonify({"error": "No autorizado"}), 403
            
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Obtener datos de Firebase Auth para el estado de verificación
        auth_user = auth.get_user(user_id)
            
        user_data = user_doc.to_dict()
        
        profile_data = {
            "uid": user_data.get("uid"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "emailVerified": auth_user.email_verified,
            "description": user_data.get("description", ""),
            "institution": user_data.get("institution", ""),
            "professionalTitle": user_data.get("professionalTitle", ""),
            "universityCareer": user_data.get("universityCareer", ""),
            "age": user_data.get("age"),
            "challengeWins": user_data.get("challengeWins", 0),
            "totalParticipations": user_data.get("totalParticipations", 0),
            "totalEarnings": user_data.get("totalEarnings", 0),
            "profilePictureUrl": user_data.get("profilePictureUrl", ""),
            "verified": user_data.get("verified", False),
            "aceptaelretoUsername": user_data.get("aceptaelretoUsername", ""),
            "createdAt": user_data.get("createdAt").isoformat() if user_data.get("createdAt") else None
        }
        
        return jsonify(profile_data), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener perfil: {str(e)}"}), 500

@auth_bp.route('/<user_id>', methods=['PUT'])
@firebase_token_required
def update_user_profile(user_id):
    try:
        # Verificar permisos
        if request.user['uid'] != user_id:
            return jsonify({"error": "No autorizado"}), 403
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "Datos JSON requeridos"}), 400
            
        # Campos permitidos para actualización
        allowed_fields = [
            "username", "description", "institution", 
            "professionalTitle", "universityCareer", "age",
            "profilePictureUrl", "aceptaelretoUsername"
        ]
        
        update_data = {
            "updatedAt": firestore.SERVER_TIMESTAMP
        }
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Actualizar el documento
        db.collection('users').document(user_id).update(update_data)
        
        return jsonify({"message": "Perfil actualizado exitosamente"}), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al actualizar perfil: {str(e)}"}), 500

@auth_bp.route('/<user_id>/change-password', methods=['POST'])
@firebase_token_required
def change_password(user_id):
    try:
        # Verificar permisos
        if request.user['uid'] != user_id:
            return jsonify({"error": "No autorizado"}), 403
            
        data = request.get_json()
        if not data or not data.get('currentPassword') or not data.get('newPassword'):
            return jsonify({"error": "Contraseña actual y nueva contraseña requeridas"}), 400
            
        # Verificar contraseña actual
        firebase_key = os.getenv('FIREBASE_API_KEY')
        auth_url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_key}'
        
        # Obtener email del usuario
        user = auth.get_user(user_id)
        email = user.email
        
        # Verificar credenciales actuales
        auth_response = requests.post(auth_url, json={
            'email': email,
            'password': data['currentPassword'],
            'returnSecureToken': True
        })
        
        if auth_response.status_code != 200:
            return jsonify({"error": "La contraseña actual es incorrecta"}), 401
        



        # Cambiar contraseña en Firebase Auth
        auth.update_user(user_id, password=data['newPassword'])
        
        return jsonify({"message": "Contraseña actualizada exitosamente"}), 200
        
    except auth.AuthError as e:
        return jsonify({"error": f"Error de autenticación: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Error al cambiar contraseña: {str(e)}"}), 500
    
@auth_bp.route('/send-email-verification', methods=['POST'])
@firebase_token_required
def send_email_verification():
    try:
        user_id = request.user['uid']
        user = auth.get_user(user_id)
        
        if user.email_verified:
            return jsonify({
                "success": True,
                "message": "El email ya está verificado"
            }), 200
        
        # Generar enlace de verificación
        verify_link = auth.generate_email_verification_link(
            user.email,
            action_code_settings=auth.ActionCodeSettings(
                url=f"{os.getenv('FRONTEND_URL')}/verify-email",
                handle_code_in_app=True
            )
        )
        
        # Enviar correo
        email_sent = send_email_via_sendgrid(
            user.email,
            EMAIL_CONFIG['verify_email_template']['subject'],
            EMAIL_CONFIG['verify_email_template']['body'].format(verify_link=verify_link)
        )
        
        if not email_sent:
            raise Exception("Error al enviar correo mediante SendGrid")
        
        return jsonify({
            "success": True,
            "message": "Correo de verificación enviado"
        }), 200
        
    except Exception as e:
        print(f"Error en send_email_verification: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error al enviar correo de verificación",
            "details": str(e)
        }), 500
    
@auth_bp.route('/current-user', methods=['GET'])
@firebase_token_required
def get_current_user():
    try:
        user_id = request.user['uid']
        user = auth.get_user(user_id)
        user_ref = db.collection('users').document(user_id)
        user_data = user_ref.get().to_dict()
        
        return jsonify({
            "uid": user.uid,
            "email": user.email,
            "emailVerified": user.email_verified,
            "username": user_data.get('username'),
            "aceptaelretoUsername": user_data.get('aceptaelretoUsername'),
            "role": user_data.get('role', 'user'),
            "isBanned": user_data.get('isBanned', False),
            "createdAt": user_data.get('createdAt'),
            "profileViews": user_data.get('profileViews', 0),
            "description": user_data.get('description'),
            "institution": user_data.get('institution'),
            "professionalTitle": user_data.get('professionalTitle'),
            "universityCareer": user_data.get('universityCareer'),
            "age": user_data.get('age'),
            "challengeWins": user_data.get('challengeWins', 0),
            "totalParticipations": user_data.get('totalParticipations', 0),
            "totalEarnings": user_data.get('totalEarnings', 0),
            "profilePictureUrl": user_data.get('profilePictureUrl'),
            "verified": user_data.get('verified', False)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/<user_id>/public', methods=['GET'])
@firebase_token_required
def get_public_profile(user_id):
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Obtener datos de Firebase Auth para el estado de verificación
        auth_user = auth.get_user(user_id)
        
        user_data = user_doc.to_dict()
        
        profile_data = {
            "uid": user_data.get("uid"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "isBanned": user_data.get('isBanned', False),
            "aceptaelretoUsername": user_data.get('aceptaelretoUsername'),
            "age": user_data.get('age'),
            "emailVerified": auth_user.email_verified,
            "description": user_data.get("description", ""),
            "institution": user_data.get("institution", ""),
            "professionalTitle": user_data.get("professionalTitle", ""),
            "universityCareer": user_data.get("universityCareer", ""),
            "challengeWins": user_data.get("challengeWins", 0),
            "totalParticipations": user_data.get("totalParticipations", 0),
            "totalEarnings": user_data.get("totalEarnings", 0),  # Asegurar que se incluya
            "profilePictureUrl": user_data.get("profilePictureUrl", ""),
            "profileViews": user_data.get("profileViews", 0),
            "createdAt": user_data.get("createdAt").isoformat() if user_data.get("createdAt") else None
        }
        
        return jsonify(profile_data), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener perfil público: {str(e)}"}), 500

# En auth_routes.py
@auth_bp.route('/<user_id>/increment-views', methods=['PUT'])
@firebase_token_required
def increment_profile_views(user_id):
    try:
        # Verificar que el usuario que incrementa no es el mismo
        if request.user['uid'] == user_id:
            return jsonify({"message": "No se incrementan vistas propias"}), 200
            
        user_ref = db.collection('users').document(user_id)
        
        # Verificar que el usuario existe
        if not user_ref.get().exists:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Obtener la última vez que se incrementó
        last_increment = user_ref.get().to_dict().get('lastViewIncrement')
        current_time = datetime.utcnow().timestamp() * 1000  # milisegundos
        
        # Cooldown de 1 hora (3600000 ms)
        if last_increment and (current_time - last_increment) < 3600000:
            return jsonify({"message": "Visitas ya incrementadas recientemente"}), 200
            
        # Incrementar el contador de visitas y registrar el tiempo
        user_ref.update({
            "profileViews": firestore.Increment(1),
            "lastViewIncrement": current_time,
            "updatedAt": datetime.utcnow()
        })
        
        return jsonify({"message": "Visitas incrementadas"}), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al incrementar visitas: {str(e)}"}), 500
    
@auth_bp.route('/<user_id>/aceptaelreto-username', methods=['PUT'])
@firebase_token_required
def update_aceptaelreto_username(user_id):
    try:
        # Verificar permisos
        if request.user['uid'] != user_id and request.user.get('role') != 'admin':
            return jsonify({"error": "No autorizado"}), 403
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "Datos JSON requeridos"}), 400
            
        username = data.get('username')
        if not username:
            return jsonify({"error": "Username es requerido"}), 400
            
        # Verificar que el usuario existe
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Preparar datos de actualización
        update_data = {
            "aceptaelretoUsername": username,
            "updatedAt": firestore.SERVER_TIMESTAMP
        }
        
        # Actualizar el documento
        user_ref.update(update_data)
        
        return jsonify({"message": "Username actualizado exitosamente"}), 200
    except KeyError as e:
        print(f"Error de clave: {str(e)}")
        return jsonify({"error": "Datos de autenticación incompletos"}), 401
    except Exception as e:
        print(f"Error al actualizar username: {str(e)}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

@auth_bp.route('/<user_id>/increment-participations', methods=['PUT'])
@admin_required
def increment_user_participations(user_id):
    try:
        user_ref = db.collection('users').document(user_id)
        
        # Verificar que el usuario existe
        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
            
        # Incrementar el contador de participaciones
        user_ref.update({
            "totalParticipations": firestore.Increment(1),
            "updatedAt": datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Participaciones incrementadas correctamente"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al incrementar participaciones: {str(e)}"
        }), 500

@auth_bp.route('/verify-email', methods=['GET'])
def handle_email_verification():
    try:
        # Firebase maneja automáticamente la verificación cuando el usuario hace clic en el enlace
        # Esta ruta es para redireccionar al frontend después de la verificación
        return redirect(f"{os.getenv('FRONTEND_URL')}/profile/verify-email?verified=true")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/send-password-reset-email', methods=['POST'])
def send_password_reset_email():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({"success": False, "message": "Email es requerido"}), 400
        
        try:
            user = auth.get_user_by_email(email)
        except auth.UserNotFoundError:
            # Por seguridad, no revelamos si el email existe
            return jsonify({
                "success": True,
                "message": "Si el email existe, se ha enviado un correo con instrucciones"
            }), 200
        
        # Generar enlace de restablecimiento
        reset_link = auth.generate_password_reset_link(
            email,
            action_code_settings=auth.ActionCodeSettings(
                url=f"{os.getenv('FRONTEND_URL')}/reset-password",
                handle_code_in_app=True
            )
        )
        
        # Enviar correo usando SendGrid
        email_sent = send_email_via_sendgrid(
            email,
            EMAIL_CONFIG['reset_password_template']['subject'],
            EMAIL_CONFIG['reset_password_template']['body'].format(reset_link=reset_link)
        )
        
        if not email_sent:
            raise Exception("Error al enviar correo mediante SendGrid")
        
        return jsonify({
            "success": True,
            "message": "Correo de recuperación enviado"
        }), 200
        
    except Exception as e:
        print(f"Error en send_password_reset_email: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Error al enviar correo de recuperación",
            "details": str(e)
        }), 500
    
@auth_bp.route('/verify-password-reset-code', methods=['POST'])
def verify_password_reset_code():
    try:
        data = request.get_json()
        oob_code = data.get('oobCode')
        
        if not oob_code:
            return jsonify({"success": False, "message": "Código de restablecimiento requerido"}), 400
        
        # Verificar el código
        email = auth.verify_password_reset_code(oob_code)
        
        return jsonify({
            "success": True,
            "message": "Código válido",
            "email": email
        }), 200
        
    except auth.InvalidActionCodeError:
        return jsonify({
            "success": False,
            "message": "El código de restablecimiento no es válido o ha expirado"
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al verificar el código",
            "details": str(e)
        }), 500

@auth_bp.route('/<user_id>/increment-earnings', methods=['PUT'])
@admin_required
def increment_user_earnings(user_id):
    try:
        data = request.get_json()
        amount = data.get('amount')
        
        if not amount or not isinstance(amount, (int, float)) or amount <= 0:
            return jsonify({
                "success": False,
                "message": "Monto válido requerido"
            }), 400
            
        user_ref = db.collection('users').document(user_id)
        
        # Verificar que el usuario existe
        if not user_ref.get().exists:
            return jsonify({
                "success": False,
                "message": "Usuario no encontrado"
            }), 404
            
        # Incrementar las ganancias totales
        user_ref.update({
            "totalEarnings": firestore.Increment(amount),
            "updatedAt": datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Ganancias incrementadas correctamente"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al incrementar ganancias: {str(e)}"
        }), 500

@auth_bp.route('/<user_id>/increment-wins', methods=['PUT'])
@admin_required
def increment_user_wins(user_id):
    try:
        user_ref = db.collection('users').document(user_id)
        
        # Verificar que el usuario existe
        if not user_ref.get().exists:
            return jsonify({
                "success": False,
                "message": "Usuario no encontrado"
            }), 404
            
        # Incrementar el contador de victorias
        user_ref.update({
            "challengeWins": firestore.Increment(1),
            "updatedAt": datetime.utcnow()
        })
        
        return jsonify({
            "success": True,
            "message": "Victorias incrementadas correctamente"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al incrementar victorias: {str(e)}"
        }), 500
        
@auth_bp.route('/confirm-password-reset', methods=['POST'])
def confirm_password_reset():
    try:
        data = request.get_json()
        oob_code = data.get('oobCode')
        new_password = data.get('newPassword')
        
        if not oob_code or not new_password:
            return jsonify({"success": False, "message": "Código y nueva contraseña requeridos"}), 400
        
        if len(new_password) < 6:
            return jsonify({"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}), 400
        
        # Verificar el código y obtener el email
        email = auth.verify_password_reset_code(oob_code)
        
        # Actualizar la contraseña
        user = auth.get_user_by_email(email)
        auth.update_user(user.uid, password=new_password)
        
        return jsonify({
            "success": True,
            "message": "Contraseña actualizada exitosamente"
        }), 200
        
    except auth.InvalidActionCodeError:
        return jsonify({
            "success": False,
            "message": "El código de restablecimiento no es válido o ha expirado"
        }), 400
    except auth.WeakPasswordError:
        return jsonify({
            "success": False,
            "message": "La contraseña es demasiado débil"
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al restablecer la contraseña",
            "details": str(e)
        }), 500

    