"""User model."""
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
from app.extensions import db
from app.models.base import BaseModel


class User(BaseModel):
    """User model."""

    __tablename__ = "users"

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(50), default="user", nullable=False, index=True)
    github_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    github_username = db.Column(db.String(255), nullable=True)
    github_access_token = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.Text, nullable=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    auth_provider = db.Column(db.String(50), default="email", nullable=False)  # 'email' or 'github'
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    projects = db.relationship("Project", backref="user", lazy=True, cascade="all, delete-orphan")
    conversion_jobs = db.relationship("ConversionJob", backref="user", lazy=True, cascade="all, delete-orphan")
    verification_tokens = db.relationship("VerificationToken", backref="user", lazy=True, cascade="all, delete-orphan")
    github_repos = db.relationship("GitHubRepo", backref="user", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"

    def to_dict(self, include_password=False):
        """Convert model to dictionary."""
        data = {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "github_id": self.github_id,
            "github_username": self.github_username,
            "avatar_url": self.avatar_url,
            "email_verified": self.email_verified,
            "auth_provider": self.auth_provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if include_password:
            data["password_hash"] = self.password_hash
            data["github_access_token"] = self.github_access_token
        return data
