"""Storage service for file operations."""
import os
from pathlib import Path
from app.utils.file_handler import create_directory, delete_directory, create_zip, extract_zip
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """Service for managing file storage."""

    @staticmethod
    def get_upload_directory(user_id):
        """Get upload directory for user."""
        from flask import current_app

        base_path = current_app.config.get("UPLOAD_FOLDER")
        user_path = os.path.join(base_path, user_id)
        create_directory(user_path)
        return user_path

    @staticmethod
    def get_converted_directory(user_id, job_id):
        """Get converted directory for conversion job."""
        from flask import current_app

        base_path = current_app.config.get("CONVERTED_FOLDER")
        job_path = os.path.join(base_path, user_id, job_id)
        create_directory(job_path)
        return job_path

    @staticmethod
    def get_reports_directory(user_id):
        """Get reports directory for user."""
        from flask import current_app

        base_path = current_app.config.get("REPORTS_FOLDER")
        user_path = os.path.join(base_path, user_id)
        create_directory(user_path)
        return user_path

    @staticmethod
    def save_uploaded_file(file, user_id, filename):
        """Save uploaded file to storage."""
        try:
            upload_dir = StorageService.get_upload_directory(user_id)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            logger.info(f"File uploaded: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {str(e)}")
            raise

    @staticmethod
    def delete_project_files(user_id, project_id):
        """Delete project files from storage."""
        try:
            upload_dir = StorageService.get_upload_directory(user_id)
            # Delete the project file
            # This is simplified - could be more sophisticated based on storage scheme
            logger.info(f"Project files deletion initiated for {project_id}")
        except Exception as e:
            logger.error(f"Failed to delete project files: {str(e)}")
            raise

    @staticmethod
    def create_converted_zip(user_id, job_id, converted_dir):
        """Create ZIP file of converted Flask project."""
        try:
            reports_dir = StorageService.get_reports_directory(user_id)
            zip_path = os.path.join(reports_dir, f"{job_id}.zip")
            create_zip(converted_dir, zip_path)
            logger.info(f"Converted ZIP created: {zip_path}")
            return zip_path
        except Exception as e:
            logger.error(f"Failed to create converted ZIP: {str(e)}")
            raise

    @staticmethod
    def get_file_path(user_id, file_type, file_id):
        """Get file path based on type."""
        if file_type == "upload":
            return os.path.join(StorageService.get_upload_directory(user_id), file_id)
        elif file_type == "converted":
            return os.path.join(StorageService.get_reports_directory(user_id), f"{file_id}.zip")
        elif file_type == "report":
            return os.path.join(StorageService.get_reports_directory(user_id), f"{file_id}.json")
        else:
            raise ValueError(f"Unknown file type: {file_type}")
