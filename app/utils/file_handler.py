"""File handling utilities."""
import os
import shutil
import zipfile
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_directory(path):
    """Create directory if it doesn't exist."""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory created: {path}")
        return path
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {str(e)}")
        raise


def delete_directory(path):
    """Delete directory and all contents."""
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            logger.debug(f"Directory deleted: {path}")
    except Exception as e:
        logger.error(f"Failed to delete directory {path}: {str(e)}")
        raise


def get_file_size(file_path):
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Failed to get file size {file_path}: {str(e)}")
        return 0


def validate_zip_file(file_path):
    """Validate if file is a valid ZIP file."""
    try:
        with zipfile.ZipFile(file_path, "r") as zip_file:
            # Test the ZIP file integrity
            result = zip_file.testzip()
            return result is None
    except Exception as e:
        logger.error(f"Invalid ZIP file {file_path}: {str(e)}")
        return False


def extract_zip(zip_path, extract_path):
    """Extract ZIP file to directory."""
    try:
        create_directory(extract_path)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)
        logger.info(f"ZIP extracted: {zip_path} -> {extract_path}")
        return extract_path
    except Exception as e:
        logger.error(f"Failed to extract ZIP {zip_path}: {str(e)}")
        raise


def create_zip(directory_path, output_zip_path):
    """Create ZIP file from directory."""
    try:
        create_directory(os.path.dirname(output_zip_path))
        shutil.make_archive(output_zip_path.replace(".zip", ""), "zip", directory_path)
        logger.info(f"ZIP created: {directory_path} -> {output_zip_path}")
        return output_zip_path
    except Exception as e:
        logger.error(f"Failed to create ZIP {output_zip_path}: {str(e)}")
        raise
