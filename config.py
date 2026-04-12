"""Flask application configuration."""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""

    # Flask
    ENV = os.getenv("NODE_ENV", "development")
    DEBUG = ENV == "development"
    TESTING = False
    
    # Single JWT secret for both Flask session and JWT tokens
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
    SECRET_KEY = JWT_SECRET  # Flask session signing key
    JWT_SECRET_KEY = JWT_SECRET  # Flask-JWT-Extended key

    # Database
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', 5432)}"
        f"/{os.getenv('DB_NAME', 'frameshift')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 20,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }

    # JWT
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    JWT_ALGORITHM = "HS256"

    # CORS
    CORS_ORIGINS = os.getenv("FRONTEND_URL", "http://localhost:3001").split(",")
    CORS_ALLOW_HEADERS = ["Content-Type", "Authorization"]
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

    # File Upload
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 104857600))  # 100MB default
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "storage", "uploads")
    CONVERTED_FOLDER = os.path.join(os.path.dirname(__file__), "storage", "converted")
    REPORTS_FOLDER = os.path.join(os.path.dirname(__file__), "storage", "reports")

    # GitHub OAuth
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_CALLBACK_URL = os.getenv("GITHUB_CALLBACK_URL")

    # Email
    MAIL_SERVER = os.getenv("SMTP_HOST", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("SMTP_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("SMTP_USER")
    MAIL_PASSWORD = os.getenv("SMTP_PASS")
    MAIL_DEFAULT_SENDER = os.getenv("SMTP_FROM", "FrameShift <noreply@frameshift.com>")

    # Google Gemini API
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Server
    PORT = int(os.getenv("PORT", 5000))
    PREFERRED_HOST = "0.0.0.0"

    # WebSocket
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.getenv("FRONTEND_URL", "http://localhost:3001")
    SOCKETIO_ASYNC_MODE = "threading"

    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.getenv("REDIS_URL", "memory://")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "app.log")

    # Python Engine
    PYTHON_PATH = os.getenv("PYTHON_PATH", "python3")
    CLEANUP_INTERVAL_DAYS = int(os.getenv("CLEANUP_INTERVAL_DAYS", 7))


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False
    # Use SQLite for development when PostgreSQL is not available
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///frameshift_dev.db")


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)


def get_config():
    """Get configuration based on environment."""
    env = os.getenv("NODE_ENV", "development").lower()
    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }
    return config_map.get(env, DevelopmentConfig)
