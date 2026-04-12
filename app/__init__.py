"""Flask application factory."""
import os
import logging
from flask import Flask, jsonify
from flask_migrate import Migrate
from config import get_config
from app.extensions import init_app_extensions, db

migrate = Migrate()


def create_app(config_name=None):
    """Application factory for Flask app."""

    # Load configuration
    config = get_config(config_name) if config_name else get_config()
    app = Flask(__name__)
    app.config.from_object(config)

    # Setup logging
    from app.utils.logger import setup_logger
    logger = setup_logger(app)
    logger.info(f"Creating Flask app with config: {config.__class__.__name__}")

    # Initialize extensions
    extensions = init_app_extensions(app)

    # Setup database migrations
    migrate.init_app(app, db)

    # Import models after extensions are initialized
    from app.models import (
        User, Project, ConversionJob, Report, 
        VerificationToken, GitHubRepo
    )

    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        logger.info("Database tables initialized")

    # Initialize middleware
    from app.middleware import init_middleware
    init_middleware(app)

    # Register error handlers
    from app.utils.errors import handle_errors
    handle_errors(app)

    # Import and register blueprints  
    from app.routes.auth import auth_bp
    from app.routes.user import user_bp
    from app.routes.project import project_bp
    from app.routes.conversion import conversion_bp
    from app.routes.github import github_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(conversion_bp)
    app.register_blueprint(github_bp)
    app.register_blueprint(admin_bp)

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "success": True,
                "message": "FrameShift API is running",
                "timestamp": str(__import__("datetime").datetime.utcnow().isoformat()),
            }
        ), 200

    # 404 handler
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

    logger.info("Flask app created successfully")
    return app
