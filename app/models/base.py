"""Base model with common fields."""
import uuid
from datetime import datetime
from app.extensions import db


class BaseModel(db.Model):
    """Base model for all database models."""

    __abstract__ = True

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            col.name: getattr(self, col.name) for col in self.__table__.columns
        }
