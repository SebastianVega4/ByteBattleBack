from flask import Flask
from flask_cors import CORS
from routes.auth_routes import auth_bp
from routes.challenge_routes import challenge_bp
from routes.participation_routes import participation_bp
import os
from dotenv import load_dotenv
from utils.firebase import initialize_firebase
from routes.notification_routes import notification_bp


load_dotenv()

app = Flask(__name__)
CORS(app, 
     supports_credentials=True,
     resources={
         r"/auth/*": {
             "origins": ["http://localhost:4200"],
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"]
         }
     })

# Initialize Firebase
initialize_firebase()

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(challenge_bp, url_prefix='/challenges')
app.register_blueprint(participation_bp, url_prefix='/participations')
app.register_blueprint(notification_bp, url_prefix='/notifications')

# Error handler
from utils.exceptions import handle_error, ByteBattleError

@app.errorhandler(ByteBattleError)
def handle_bytebattle_error(e):
    return handle_error(e)

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    return handle_error(e)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)