"""GitHub routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User
from app.services.github_service import GitHubService
from app.extensions import db
from app.utils.decorators import success_response, error_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

github_bp = Blueprint("github", __name__, url_prefix="/api/github")


@github_bp.route("/connect", methods=["POST"])
@jwt_required()
def connect_github():
    """Connect GitHub account."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}

        access_token = data.get("access_token")
        if not access_token:
            return error_response("GitHub access token is required", 400)

        user = User.query.get(user_id)
        if not user:
            return error_response("User not found", 404)

        # Get GitHub user info
        github_user = GitHubService.get_github_user(access_token)

        # Update user with GitHub info
        user.github_id = str(github_user.get("id"))
        user.github_username = github_user.get("login")
        user.github_access_token = access_token
        user.avatar_url = github_user.get("avatar_url")

        db.session.commit()

        logger.info(f"GitHub account connected for user: {user_id}")

        return success_response({"user": user.to_dict()}, "GitHub account connected")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error connecting GitHub: {str(e)}")
        return error_response("Failed to connect GitHub account", 500)


@github_bp.route("/disconnect", methods=["POST"])
@jwt_required()
def disconnect_github():
    """Disconnect GitHub account."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return error_response("User not found", 404)

        user.github_id = None
        user.github_username = None
        user.github_access_token = None

        db.session.commit()

        logger.info(f"GitHub account disconnected for user: {user_id}")

        return success_response(message="GitHub account disconnected")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error disconnecting GitHub: {str(e)}")
        return error_response("Failed to disconnect GitHub account", 500)


@github_bp.route("/repos", methods=["GET"])
@jwt_required()
def get_user_repos():
    """Get user's GitHub repositories."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user or not user.github_access_token:
            return error_response("GitHub not connected", 400)

        repos = GitHubService.list_user_repos(user.github_access_token)

        return success_response({"repos": repos})

    except Exception as e:
        logger.error(f"Error getting GitHub repos: {str(e)}")
        return error_response("Failed to get repositories", 500)
