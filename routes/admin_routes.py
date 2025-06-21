# admin_routes.py
from flask import Blueprint, request, jsonify
from firebase_admin import firestore
from utils.firebase import db  # Importar db desde utils.firebase
from utils.decorators import admin_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    try:
        page_index = int(request.args.get('pageIndex', 0))
        page_size = int(request.args.get('pageSize', 10))
        
        # Usar nombres de parámetros consistentes
        users_ref = db.collection('users')
        total_docs = users_ref.count().get()[0][0].value
        
        # Usar cursor para paginación eficiente
        query = users_ref.order_by('createdAt').limit(page_size)
        
        if page_index > 0:
            last_doc = users_ref.order_by('createdAt').offset((page_index) * page_size - 1).limit(1).get()[0]
            query = query.start_after(last_doc)
        
        users = []
        for doc in query.stream():
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            users.append(user_data)
            
        return jsonify({
            "users": users,
            "total": total_docs
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500