"""Admin routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User, Project, ConversionJob
from app.middleware import require_admin
from app.utils.decorators import success_response, error_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/users", methods=["GET"])
@jwt_required()
@require_admin
def list_users():
    """List all users (admin only)."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        users = User.query.paginate(page=page, per_page=per_page, error_out=False)

        return success_response(
            {
                "users": [u.to_dict() for u in users.items],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": users.total,
                    "pages": users.pages,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return error_response("Failed to list users", 500)


@admin_bp.route("/stats", methods=["GET"])
@jwt_required()
@require_admin
def get_stats():
    """Get system statistics (admin only)."""
    try:
        stats = {
            "total_users": User.query.count(),
            "total_projects": Project.query.count(),
            "total_conversions": ConversionJob.query.count(),
            "completed_conversions": ConversionJob.query.filter_by(status="completed").count(),
            "failed_conversions": ConversionJob.query.filter_by(status="failed").count(),
        }

        return success_response({"stats": stats})

    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return error_response("Failed to get statistics", 500)
