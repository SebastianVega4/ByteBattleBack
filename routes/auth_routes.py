from flask import Blueprint, request, jsonify
from functions.auth_functions import register_user, set_admin_role, ban_user
from utils.decorators import firebase_token_required, admin_required
from utils.exceptions import handle_error

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register_user_route():
    try:
        data = request.get_json()
        result = register_user(data)
        return jsonify(result), 201
    except Exception as e:
        return handle_error(e)

@auth_bp.route('/set-admin-role', methods=['POST'])
@admin_required
def set_admin_role_route():
    try:
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
        data = request.get_json()
        user_id = data.get('uid')
        is_banned = data.get('isBanned', True)
        current_user_id = request.user['uid']
        result = ban_user(user_id, is_banned, current_user_id)
        return jsonify(result), 200
    except Exception as e:
        return handle_error(e)