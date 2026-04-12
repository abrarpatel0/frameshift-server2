"""Error handling utilities."""
from flask import jsonify


def handle_errors(app):
    """Register error handlers with Flask app."""

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify(
            {
                "success": False,
                "error": {
                    "message": str(error.description) if hasattr(error, "description") else "Bad request",
                    "status": 400,
                },
            }
        ), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify(
            {
                "success": False,
                "error": {
                    "message": str(error.description) if hasattr(error, "description") else "Unauthorized",
                    "status": 401,
                },
            }
        ), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify(
            {
                "success": False,
                "error": {
                    "message": str(error.description) if hasattr(error, "description") else "Forbidden",
                    "status": 403,
                },
            }
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(
            {
                "success": False,
                "error": {
                    "message": "Endpoint not found",
                    "status": 404,
                },
            }
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify(
            {
                "success": False,
                "error": {
                    "message": "Internal server error",
                    "status": 500,
                },
            }
        ), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle generic exceptions."""
        app.logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
        return jsonify(
            {
                "success": False,
                "error": {
                    "message": str(error) if app.debug else "Internal server error",
                    "status": 500,
                },
            }
        ), 500
