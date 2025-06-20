from firebase_admin import auth
from utils.firebase import db
from utils.exceptions import ValidationError, NotFoundError, ForbiddenError
from firebase_admin.exceptions import FirebaseError
from models.User import User

def register_user(data):
    """Register a new user"""
    try:
        email = data.get('email')
        password = data.get('password')
        username = data.get('username')
        
        if not all([email, password, username]):
            raise ValidationError("Email, password and username are required")
        
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters")
        
        # Create user in Firebase Auth
        user_record = auth.create_user(
            email=email,
            password=password,
            display_name=username
        )
        
        # Create document in Firestore
        user_data = {
            "uid": user_record.uid,
            "email": email,
            "username": username,
            "role": "user",
            "isBanned": False,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP
        }
        
        db.collection('users').document(user_record.uid).set(user_data)
        
        return {
            "message": "User registered successfully",
            "user": {
                "uid": user_record.uid,
                "email": email,
                "username": username
            }
        }
    except auth.EmailAlreadyExistsError:
        raise ValidationError("Email already registered")
    except FirebaseError as e:  # Usar FirebaseError en lugar de WeakPasswordError
        if "WEAK_PASSWORD" in str(e):
            raise ValidationError("Password is too weak")
        raise ValidationError(f"Firebase error: {str(e)}")
    except ValueError as e:
        raise ValidationError(str(e))
    except Exception as e:
        print(f"Error during registration: {str(e)}")
        raise Exception(f"Error registering user: {str(e)}")
    
def set_admin_role(user_id, current_user_id):
    """Set admin role for a user"""
    if not user_id:
        raise ValidationError("User ID is required")
    
    # Verify the current user is admin
    current_user = db.collection('users').document(current_user_id).get()
    if not current_user.exists or current_user.to_dict().get('role') != 'admin':
        raise ForbiddenError("Only admins can set admin roles")
    
    try:
        db.collection('users').document(user_id).update({"role": "admin"})
        return {"message": "Admin role assigned successfully"}
    except Exception as e:
        raise Exception(f"Error assigning admin role: {str(e)}")

def ban_user(user_id, is_banned, current_user_id):
    """Ban or unban a user"""
    if not user_id:
        raise ValidationError("User ID is required")
    
    # Verify the current user is admin
    current_user = db.collection('users').document(current_user_id).get()
    if not current_user.exists or current_user.to_dict().get('role') != 'admin':
        raise ForbiddenError("Only admins can ban users")
    
    try:
        # Update in Firestore
        db.collection('users').document(user_id).update({"isBanned": is_banned})
        
        # Update in Firebase Auth
        auth.update_user(user_id, disabled=is_banned)
        
        return {"message": f"User {'banned' if is_banned else 'unbanned'} successfully"}
    except Exception as e:
        raise Exception(f"Error updating ban status: {str(e)}")