"""Report model."""
from sqlalchemy.dialects.postgresql import JSON
from app.extensions import db
from app.models.base import BaseModel


class Report(BaseModel):
    """Report model."""

    __tablename__ = "reports"

    conversion_job_id = db.Column(
        db.String(36), db.ForeignKey("conversion_jobs.id"), nullable=False, index=True
    )
    accuracy_percentage = db.Column(db.Float, nullable=True)
    files_converted = db.Column(db.Integer, nullable=True)
    files_failed = db.Column(db.Integer, nullable=True)
    issues_found = db.Column(JSON, nullable=True)
    suggestions = db.Column(JSON, nullable=True)
    gemini_verification = db.Column(JSON, nullable=True)
    file_diffs = db.Column(JSON, nullable=True)
    validation_result = db.Column(JSON, nullable=True)

    def __repr__(self):
        return f"<Report {self.id}>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "conversion_job_id": self.conversion_job_id,
            "accuracy_percentage": self.accuracy_percentage,
            "files_converted": self.files_converted,
            "files_failed": self.files_failed,
            "issues_found": self.issues_found or [],
            "suggestions": self.suggestions or [],
            "gemini_verification": self.gemini_verification,
            "file_diffs": self.file_diffs or {},
            "validation_result": self.validation_result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
