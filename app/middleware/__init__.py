"""Middleware initialization."""
from flask import request, jsonify
from functools import wraps
from app.extensions import limiter
from app.utils.logger import get_logger

logger = get_logger(__name__)


def init_middleware(app):
    """Initialize all middleware for Flask app."""

    @app.before_request
    def before_request():
        """Log incoming requests."""
        if not request.path.startswith("/health"):
            logger.debug(f"{request.method} {request.path}")

    @app.after_request
    def after_request(response):
        """Set security headers."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


def require_admin(f):
    """Decorator to require admin role."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_jwt_extended import get_jwt_identity
        from app.models import User

        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({"success": False, "error": {"message": "Unauthorized"}}), 401

        user = User.query.get(current_user_id)
        if not user or user.role != "admin":
            return (
                jsonify({"success": False, "error": {"message": "Admin access required"}}),
                403,
            )

        return f(*args, **kwargs)

    return decorated_function


def require_auth(f):
    """Decorator to require authentication."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

        verify_jwt_in_request()  # Verify JWT token is present and valid
        return f(*args, **kwargs)

    return decorated_function
