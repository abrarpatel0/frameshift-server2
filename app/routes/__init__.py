"""Routes package initialization."""
from app.routes.auth import auth_bp
from app.routes.user import user_bp
from app.routes.project import project_bp
from app.routes.conversion import conversion_bp
from app.routes.github import github_bp
from app.routes.admin import admin_bp

__all__ = [
    "auth_bp",
    "user_bp",
    "project_bp",
    "conversion_bp",
    "github_bp",
    "admin_bp",
]
