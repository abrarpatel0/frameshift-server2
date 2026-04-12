"""Request decorators and utility functions."""
from functools import wraps
from flask import jsonify, request
from app.utils.logger import get_logger

logger = get_logger(__name__)


def async_handler(f):
    """Decorator to catch async function exceptions."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify(
                {
                    "success": False,
                    "error": {
                        "message": str(e),
                    },
                }
            ), 500

    return decorated_function


def validate_json(required_fields=None):
    """Decorator to validate JSON request."""
    if required_fields is None:
        required_fields = []

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify(
                    {
                        "success": False,
                        "error": {
                            "message": "Request must be JSON",
                        },
                    }
                ), 400

            data = request.get_json()
            if not data:
                return jsonify(
                    {
                        "success": False,
                        "error": {
                            "message": "Request body cannot be empty",
                        },
                    }
                ), 400

            # Check required fields
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify(
                        {
                            "success": False,
                            "error": {
                                "message": f"Missing required field: {field}",
                            },
                        }
                    ), 400

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def success_response(data=None, message="Success", status_code=200):
    """Create a standardized success response."""
    response = {
        "success": True,
        "data": data,
    }
    if message:
        response["message"] = message
    return jsonify(response), status_code


def error_response(message="Error", status_code=400, error_code=None):
    """Create a standardized error response."""
    response = {
        "success": False,
        "error": {
            "message": message,
        },
    }
    if error_code:
        response["error"]["code"] = error_code
    return jsonify(response), status_code
