"""ConversionJob model."""
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from app.extensions import db
from app.models.base import BaseModel


class ConversionJob(BaseModel):
    """ConversionJob model."""

    __tablename__ = "conversion_jobs"

    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(
        db.String(50),
        default="pending",
        nullable=False,
        index=True,
    )  # pending, analyzing, converting, verifying, completed, failed
    progress_percentage = db.Column(db.Integer, default=0, nullable=False)
    current_step = db.Column(db.String(255), nullable=True)
    converted_file_path = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    use_ai = db.Column(db.Boolean, default=True, nullable=False)
    ai_enhancements = db.Column(JSON, default=list, nullable=True)
    conversion_mode = db.Column(db.String(50), default="default", nullable=False)  # default, custom
    custom_api_config = db.Column(JSON, nullable=True)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    last_retry_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    reports = db.relationship("Report", backref="conversion_job", lazy=True, cascade="all, delete-orphan")
    github_repos = db.relationship("GitHubRepo", backref="conversion_job", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (db.Index("idx_conversion_user_status", "user_id", "status"),)

    def __repr__(self):
        return f"<ConversionJob {self.id} - {self.status}>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "status": self.status,
            "progress_percentage": self.progress_percentage,
            "current_step": self.current_step,
            "converted_file_path": self.converted_file_path,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "use_ai": self.use_ai,
            "ai_enhancements": self.ai_enhancements or [],
            "conversion_mode": self.conversion_mode,
            "custom_api_config": self.custom_api_config,
            "retry_count": self.retry_count,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
