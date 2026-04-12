"""Project routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Project, User
from app.extensions import db
from app.utils.decorators import success_response, error_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

project_bp = Blueprint("project", __name__, url_prefix="/api/projects")


@project_bp.route("", methods=["GET"])
@jwt_required()
def list_projects():
    """List all projects for user."""
    try:
        user_id = get_jwt_identity()
        projects = Project.query.filter_by(user_id=user_id).all()

        return success_response(
            {"projects": [p.to_dict() for p in projects]}
        )

    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}")
        return error_response("Failed to list projects", 500)


@project_bp.route("/<project_id>", methods=["GET"])
@jwt_required()
def get_project(project_id):
    """Get project details."""
    try:
        user_id = get_jwt_identity()
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()

        if not project:
            return error_response("Project not found", 404)

        return success_response({"project": project.to_dict()})

    except Exception as e:
        logger.error(f"Error getting project: {str(e)}")
        return error_response("Failed to get project", 500)


@project_bp.route("", methods=["POST"])
@jwt_required()
def create_project():
    """Create new project."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}

        project = Project(
            user_id=user_id,
            name=data.get("name", "Untitled Project"),
            description=data.get("description", ""),
            source_type=data.get("source_type", "upload"),
        )

        db.session.add(project)
        db.session.commit()

        logger.info(f"Project created: {project.id}")

        return success_response(
            {"project": project.to_dict()}, "Project created", 201
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating project: {str(e)}")
        return error_response("Failed to create project", 500)


@project_bp.route("/<project_id>", methods=["DELETE"])
@jwt_required()
def delete_project(project_id):
    """Delete project."""
    try:
        user_id = get_jwt_identity()
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()

        if not project:
            return error_response("Project not found", 404)

        db.session.delete(project)
        db.session.commit()

        logger.info(f"Project deleted: {project_id}")

        return success_response(message="Project deleted")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting project: {str(e)}")
        return error_response("Failed to delete project", 500)
