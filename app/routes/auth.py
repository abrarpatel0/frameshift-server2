"""Authentication routes."""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.models import User
from app.extensions import db, limiter
from app.utils.decorators import validate_json, error_response, success_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per 15 minutes")
@validate_json(required_fields=["email", "password"])
def register():
    """Register new user."""
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        full_name = data.get("full_name", "").strip()

        # Validate input
        if not email or not password:
            return error_response("Email and password are required", 400)

        if len(password) < 8:
            return error_response("Password must be at least 8 characters", 400)

        # Register user
        result = AuthService.register_user(email, password, full_name)

        return success_response(
            {
                "user": result["user"],
                "access_token": result["tokens"]["access_token"],
                "refresh_token": result["tokens"]["refresh_token"],
            },
            result["message"],
            201,
        )

    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return error_response("Registration failed", 500)


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per 15 minutes")
@validate_json(required_fields=["email", "password"])
def login():
    """Login user."""
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return error_response("Email and password are required", 400)

        # Login user
        result = AuthService.login_user(email, password)

        return success_response(
            {
                "user": result["user"],
                "access_token": result["tokens"]["access_token"],
                "refresh_token": result["tokens"]["refresh_token"],
            },
            "Login successful",
        )

    except ValueError as e:
        return error_response(str(e), 401)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return error_response("Login failed", 500)


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Logout user."""
    try:
        # With JWT, logout is handled on client-side by removing token
        return success_response(message="Logged out successfully")
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return error_response("Logout failed", 500)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """Get current authenticated user."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return error_response("User not found", 404)

        return success_response({"user": user.to_dict()})

    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        return error_response("Failed to get user", 500)


@auth_bp.route("/verify-email", methods=["POST"])
@validate_json(required_fields=["token"])
def verify_email():
    """Verify email with token."""
    try:
        data = request.get_json()
        token = data.get("token")

        if not token:
            return error_response("Verification token is required", 400)

        result = AuthService.verify_email(token)

        return success_response(
            {"user": result["user"]}, result["message"]
        )

    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        return error_response("Email verification failed", 500)


@auth_bp.route("/resend-verification", methods=["POST"])
@jwt_required()
def resend_verification():
    """Resend email verification."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return error_response("User not found", 404)

        if user.email_verified:
            return error_response("Email already verified", 400)

        # Create new verification token
        token = AuthService.create_verification_token(user_id, "email_verification", 24)

        # Send email
        EmailService.send_welcome_email(user, token.token)

        return success_response(message="Verification email sent")

    except Exception as e:
        logger.error(f"Resend verification error: {str(e)}")
        return error_response("Failed to resend verification", 500)


@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("3 per 30 minutes")
@validate_json(required_fields=["email"])
def forgot_password():
    """Request password reset."""
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()

        if not email:
            return error_response("Email is required", 400)

        result = AuthService.request_password_reset(email)
        return success_response(message=result["message"])

    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        return error_response("Failed to process password reset request", 500)


@auth_bp.route("/reset-password", methods=["POST"])
@validate_json(required_fields=["token", "password"])
def reset_password():
    """Reset password with token."""
    try:
        data = request.get_json()
        token = data.get("token")
        password = data.get("password")

        if not token or not password:
            return error_response("Token and password are required", 400)

        if len(password) < 8:
            return error_response("Password must be at least 8 characters", 400)

        result = AuthService.reset_password(token, password)
        return success_response(message=result["message"])

    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        return error_response("Failed to reset password", 500)


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
@validate_json(required_fields=["currentPassword", "newPassword"])
def change_password():
    """Change user password."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        current_password = data.get("currentPassword")
        new_password = data.get("newPassword")

        if not current_password or not new_password:
            return error_response("Current and new passwords are required", 400)

        if len(new_password) < 8:
            return error_response("New password must be at least 8 characters", 400)

        result = AuthService.change_password(user_id, current_password, new_password)
        return success_response(message=result["message"])

    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return error_response("Failed to change password", 500)


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required()
def refresh_token():
    """Refresh access token."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return error_response("User not found", 404)

        tokens = AuthService.generate_tokens(user_id, user.email)

        return success_response(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
            },
            "Token refreshed",
        )

    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return error_response("Failed to refresh token", 500)
