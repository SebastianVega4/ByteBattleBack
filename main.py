from flask_cors import CORS
from routes.auth_routes import auth_bp
from routes.challenge_routes import challenge_bp
from routes.participation_routes import participation_bp
import os
from dotenv import load_dotenv
from utils.firebase import initialize_firebase
from routes.notification_routes import notification_bp
from routes.admin_routes import admin_bp
from flask import Flask, request, jsonify, make_response

load_dotenv()

app = Flask(__name__)

# Configuración mejorada de CORS
allowed_origins = [
    "http://localhost:4200",
    "https://sebastianvega4.github.io",
    "https://bytebattlefront.vercel.app"
]

app.config.update({
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_SAMESITE': 'None',
    'CORS_SUPPORTS_CREDENTIALS': True
})

CORS(
    app,
    resources={
        r"/*": {
            "origins": allowed_origins,
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "supports_credentials": True,
            "expose_headers": ["Content-Disposition"]  # Necesario para algunas respuestas
        }
    }
)

# Middleware para manejar OPTIONS (preflight)
@app.after_request
def after_request(response):
    # Asegúrate de que estos headers se apliquen a todas las respuestas
    origin = request.headers.get('Origin', '')
    if origin in allowed_origins:
        response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

from utils.firebase import initialize_firebase
firebase_app, db = initialize_firebase()
#from utils.firebase import get_firebase
#firebase_app, db = get_firebase()
    
# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(challenge_bp, url_prefix='/challenges')
app.register_blueprint(participation_bp, url_prefix='/participations')
app.register_blueprint(notification_bp, url_prefix='/notifications')

# Error handler
from utils.exceptions import handle_error, ByteBattleError

@app.errorhandler(ByteBattleError)
def handle_bytebattle_error(e):
    response = handle_error(e)
    response = make_response(response)
    response.headers.add("Access-Control-Allow-Origin", ", ".join(allowed_origins))
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    response = handle_error(e)
    response = make_response(response)
    response.headers.add("Access-Control-Allow-Origin", ", ".join(allowed_origins))
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)