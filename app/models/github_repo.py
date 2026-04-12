"""GitHubRepo model."""
from sqlalchemy.dialects.postgresql import JSON
from app.extensions import db
from app.models.base import BaseModel


class GitHubRepo(BaseModel):
    """GitHubRepo model."""

    __tablename__ = "github_repos"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    conversion_job_id = db.Column(
        db.String(36), db.ForeignKey("conversion_jobs.id"), nullable=True, index=True
    )
    repo_name = db.Column(db.String(255), nullable=False)
    repo_url = db.Column(db.Text, nullable=False)
    branch = db.Column(db.String(255), default="main", nullable=False)
    commit_message = db.Column(db.Text, nullable=True)
    push_status = db.Column(db.String(50), default="pending", nullable=False)  # pending, success, failed
    error_details = db.Column(JSON, nullable=True)

    def __repr__(self):
        return f"<GitHubRepo {self.repo_name}>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "conversion_job_id": self.conversion_job_id,
            "repo_name": self.repo_name,
            "repo_url": self.repo_url,
            "branch": self.branch,
            "commit_message": self.commit_message,
            "push_status": self.push_status,
            "error_details": self.error_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
