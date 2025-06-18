from flask import jsonify

class ByteBattleError(Exception):
    """Base exception class for ByteBattle"""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

class NotFoundError(ByteBattleError):
    """Raised when a resource is not found"""
    def __init__(self, message="Resource not found", payload=None):
        super().__init__(message, 404, payload)

class UnauthorizedError(ByteBattleError):
    """Raised when a user is not authorized"""
    def __init__(self, message="Unauthorized", payload=None):
        super().__init__(message, 401, payload)

class ForbiddenError(ByteBattleError):
    """Raised when a user doesn't have permission"""
    def __init__(self, message="Forbidden", payload=None):
        super().__init__(message, 403, payload)

class ValidationError(ByteBattleError):
    """Raised when input validation fails"""
    def __init__(self, message="Validation error", payload=None):
        super().__init__(message, 400, payload)

def handle_error(e):
    """Convert exceptions to JSON responses"""
    if isinstance(e, ByteBattleError):
        response = jsonify(e.to_dict())
        response.status_code = e.status_code
        return response
    response = jsonify({
        'message': 'An unexpected error occurred',
        'error': str(e)
    })
    response.status_code = 500
    return response