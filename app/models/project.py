"""Project model."""
from sqlalchemy.dialects.postgresql import JSON
from app.extensions import db
from app.models.base import BaseModel


class Project(BaseModel):
    """Project model."""

    __tablename__ = "projects"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    source_type = db.Column(db.String(50), nullable=False)  # 'upload' or 'github'
    source_url = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.Text, nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)
    django_version = db.Column(db.String(50), nullable=True)
    structure_detected = db.Column(JSON, nullable=True)

    # Relationships
    conversion_jobs = db.relationship("ConversionJob", backref="project", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="unique_project_name_per_user"),
        db.Index("idx_project_user_source", "user_id", "source_type"),
    )

    def __repr__(self):
        return f"<Project {self.name}>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "django_version": self.django_version,
            "structure_detected": self.structure_detected,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
