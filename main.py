from flask import Flask
from flask_cors import CORS
from routes.auth_routes import auth_bp
from routes.challenge_routes import challenge_bp
from routes.participation_routes import participation_bp
import os
from utils.firebase import initialize_firebase  # Añadir esta línea

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Inicializar Firebase
initialize_firebase()

# Registro de blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(challenge_bp, url_prefix='/challenges')
app.register_blueprint(participation_bp, url_prefix='/participations')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)