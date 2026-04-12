"""Email service."""
from flask import current_app
from flask_mail import Message
from app.extensions import mail
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Service for email operations."""

    @staticmethod
    def send_email(to_email, subject, html_body):
        """Send email."""
        try:
            msg = Message(
                subject=subject,
                recipients=[to_email],
                html=html_body,
            )
            mail.send(msg)
            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            raise

    @staticmethod
    def send_welcome_email(user, verification_token):
        """Send welcome email with verification link."""
        try:
            from flask import current_app

            frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3001')
            verify_url = f"{frontend_url}/verify-email?token={verification_token}"

            html_body = f"""
            <html>
                <body>
                    <h2>Welcome to FrameShift, {user.full_name}!</h2>
                    <p>Please verify your email by clicking the link below:</p>
                    <a href="{verify_url}">Verify Email</a>
                    <p>Or copy this link: {verify_url}</p>
                    <p>This link will expire in 24 hours.</p>
                </body>
            </html>
            """

            return EmailService.send_email(user.email, "Verify your FrameShift account", html_body)

        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            raise

    @staticmethod
    def send_password_reset_email(user, reset_token):
        """Send password reset email."""
        try:
            from flask import current_app

            frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3001')
            reset_url = f"{frontend_url}/reset-password?token={reset_token}"

            html_body = f"""
            <html>
                <body>
                    <h2>Password Reset for FrameShift</h2>
                    <p>Hi {user.full_name},</p>
                    <p>Click the link below to reset your password:</p>
                    <a href="{reset_url}">Reset Password</a>
                    <p>Or copy this link: {reset_url}</p>
                    <p>This link will expire in 15 minutes.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                </body>
            </html>
            """

            return EmailService.send_email(user.email, "Reset your FrameShift password", html_body)

        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            raise

    @staticmethod
    def send_conversion_complete_email(user, conversion_job, report):
        """Send conversion completion email."""
        try:
            html_body = f"""
            <html>
                <body>
                    <h2>Conversion Complete!</h2>
                    <p>Hi {user.full_name},</p>
                    <p>Your Django to Flask conversion has been completed successfully.</p>
                    <p><strong>Conversion Status:</strong> {conversion_job.status}</p>
                    <p><strong>Accuracy: </strong>{report.get('accuracy_percentage', 'N/A')}%</p>
                    <p>You can now download your Flask project or review the detailed report.</p>
                    <a href="{current_app.config.get('FRONTEND_URL', 'http://localhost:3001')}/conversion/{conversion_job.id}">View Conversion Report</a>
                </body>
            </html>
            """

            return EmailService.send_email(user.email, "Your FrameShift conversion is ready", html_body)

        except Exception as e:
            logger.error(f"Failed to send conversion email: {str(e)}")
            raise
