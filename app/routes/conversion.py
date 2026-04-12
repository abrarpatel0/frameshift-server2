"""Conversion routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import ConversionJob, Project
from app.services.conversion_service import ConversionService
from app.utils.decorators import success_response, error_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

conversion_bp = Blueprint("conversion", __name__, url_prefix="/api/conversions")


@conversion_bp.route("", methods=["POST"])
@jwt_required()
def create_conversion():
    """Create new conversion job."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}

        project_id = data.get("project_id")
        if not project_id:
            return error_response("Project ID is required", 400)

        # Verify project exists and belongs to user
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()
        if not project:
            return error_response("Project not found", 404)

        # Create conversion job
        job = ConversionService.create_conversion_job(
            project_id=project_id,
            user_id=user_id,
            use_ai=data.get("use_ai", True),
            conversion_mode=data.get("conversion_mode", "default"),
            custom_api_config=data.get("custom_api_config"),
        )

        return success_response(
            {"conversion": job.to_dict()}, "Conversion job created", 201
        )

    except Exception as e:
        logger.error(f"Error creating conversion: {str(e)}")
        return error_response("Failed to create conversion", 500)


@conversion_bp.route("/<job_id>", methods=["GET"])
@jwt_required()
def get_conversion(job_id):
    """Get conversion job status."""
    try:
        user_id = get_jwt_identity()
        job = ConversionJob.query.filter_by(id=job_id, user_id=user_id).first()

        if not job:
            return error_response("Conversion job not found", 404)

        return success_response({"conversion": job.to_dict()})

    except Exception as e:
        logger.error(f"Error getting conversion: {str(e)}")
        return error_response("Failed to get conversion", 500)


@conversion_bp.route("/<job_id>/start", methods=["POST"])
@jwt_required()
def start_conversion(job_id):
    """Start conversion."""
    try:
        user_id = get_jwt_identity()
        job = ConversionJob.query.filter_by(id=job_id, user_id=user_id).first()

        if not job:
            return error_response("Conversion job not found", 404)

        if job.status != "pending":
            return error_response("Conversion has already been started", 400)

        result = ConversionService.start_conversion(job_id, job.project.file_path, user_id)

        return success_response({"message": result["message"]})

    except Exception as e:
        logger.error(f"Error starting conversion: {str(e)}")
        return error_response("Failed to start conversion", 500)


@conversion_bp.route("/<job_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_conversion(job_id):
    """Cancel conversion."""
    try:
        user_id = get_jwt_identity()
        job = ConversionJob.query.filter_by(id=job_id, user_id=user_id).first()

        if not job:
            return error_response("Conversion job not found", 404)

        result = ConversionService.cancel_conversion(job_id)

        return success_response({"message": result["message"]})

    except Exception as e:
        logger.error(f"Error cancelling conversion: {str(e)}")
        return error_response("Failed to cancel conversion", 500)
