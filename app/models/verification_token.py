"""VerificationToken model."""
from datetime import datetime, timedelta
from app.extensions import db
from app.models.base import BaseModel


class VerificationToken(BaseModel):
    """VerificationToken model."""

    __tablename__ = "verification_tokens"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    token_type = db.Column(db.String(50), nullable=False)  # email_verification, password_reset
    token = db.Column(db.Text, nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    is_used = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<VerificationToken {self.token_type}>"

    def is_expired(self):
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token_type": self.token_type,
            "token": self.token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "is_used": self.is_used,
            "is_expired": self.is_expired(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
