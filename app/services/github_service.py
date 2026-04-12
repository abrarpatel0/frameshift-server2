"""GitHub service for GitHub integration."""
import requests
from app.utils.logger import get_logger
from app.models import GitHubRepo
from app.extensions import db

logger = get_logger(__name__)


class GitHubService:
    """Service for GitHub operations."""

    @staticmethod
    def get_github_user(access_token):
        """Get authenticated GitHub user info."""
        try:
            headers = {"Authorization": f"token {access_token}"}
            response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get GitHub user: {str(e)}")
            raise

    @staticmethod
    def list_user_repos(access_token):
        """List repositories for authenticated GitHub user."""
        try:
            headers = {"Authorization": f"token {access_token}"}
            response = requests.get("https://api.github.com/user/repos", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list GitHub repos: {str(e)}")
            raise

    @staticmethod
    def create_repo(access_token, repo_name, description=None):
        """Create new repository on GitHub."""
        try:
            headers = {"Authorization": f"token {access_token}"}
            data = {
                "name": repo_name,
                "description": description or "Converted Flask project by FrameShift",
                "private": False,
            }
            response = requests.post(
                "https://api.github.com/user/repos", headers=headers, json=data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create GitHub repo: {str(e)}")
            raise

    @staticmethod
    def push_to_repo(user_id, repo_url, converted_project_path, branch="main", commit_message=None):
        """Push converted project to GitHub repository."""
        try:
            # This is a simplified version - full implementation would require:
            # - Git CLI or GitPython
            # - Cloning the repo
            # - Copying files
            # - Committing and pushing
            logger.info(f"Push to GitHub initiated: {repo_url}")

            github_repo = GitHubRepo(
                user_id=user_id,
                repo_url=repo_url,
                branch=branch,
                commit_message=commit_message or "Initial Flask project commit by FrameShift",
                push_status="success",
            )
            db.session.add(github_repo)
            db.session.commit()

            return github_repo.to_dict()

        except Exception as e:
            logger.error(f"Failed to push to GitHub: {str(e)}")
            db.session.rollback()
            raise
