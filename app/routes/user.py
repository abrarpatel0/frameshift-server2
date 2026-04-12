"""User routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User, Project, ConversionJob
from app.utils.decorators import success_response, error_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

user_bp = Blueprint("user", __name__, url_prefix="/api/users")


@user_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    """Get user profile."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return error_response("User not found", 404)

        profile = user.to_dict()

        # Add stats
        profile["stats"] = {
            "projects_count": Project.query.filter_by(user_id=user_id).count(),
            "conversions_count": ConversionJob.query.filter_by(user_id=user_id).count(),
            "conversions_completed": ConversionJob.query.filter_by(
                user_id=user_id, status="completed"
            ).count(),
        }

        return success_response({"user": profile})

    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        return error_response("Failed to get profile", 500)


@user_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    """Update user profile."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return error_response("User not found", 404)

        data = request.get_json() or {}
        
        # Update allowed fields
        if "full_name" in data:
            user.full_name = data["full_name"]

        from app.extensions import db
        db.session.commit()

        return success_response({"user": user.to_dict()}, "Profile updated")

    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        return error_response("Failed to update profile", 500)


@user_bp.route("/projects", methods=["GET"])
@jwt_required()
def get_user_projects():
    """Get user's projects."""
    try:
        user_id = get_jwt_identity()
        projects = Project.query.filter_by(user_id=user_id).all()

        return success_response(
            {"projects": [p.to_dict() for p in projects]}
        )

    except Exception as e:
        logger.error(f"Error getting user projects: {str(e)}")
        return error_response("Failed to get projects", 500)


@user_bp.route("/conversions", methods=["GET"])
@jwt_required()
def get_user_conversions():
    """Get user's conversions."""
    try:
        user_id = get_jwt_identity()
        conversions = ConversionJob.query.filter_by(user_id=user_id).all()

        return success_response(
            {"conversions": [c.to_dict() for c in conversions]}
        )

    except Exception as e:
        logger.error(f"Error getting user conversions: {str(e)}")
        return error_response("Failed to get conversions", 500)
