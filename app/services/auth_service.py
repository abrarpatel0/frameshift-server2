"""Authentication service."""
import bcrypt
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token, create_refresh_token
from app.extensions import db
from app.models import User, VerificationToken
from app.utils.logger import get_logger
from app.services.email_service import EmailService

logger = get_logger(__name__)
BCRYPT_ROUNDS = 10


class AuthService:
    """Service for authentication operations."""

    @staticmethod
    def hash_password(password):
        """Hash password with bcrypt."""
        try:
            salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
            return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to hash password: {str(e)}")
            raise

    @staticmethod
    def verify_password(plain_password, hashed_password):
        """Verify password against hash."""
        try:
            if not hashed_password:
                return False
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to verify password: {str(e)}")
            return False

    @staticmethod
    def generate_tokens(user_id, email):
        """Generate JWT access and refresh tokens."""
        try:
            access_token = create_access_token(identity=user_id)
            refresh_token = create_refresh_token(identity=user_id)
            return {"access_token": access_token, "refresh_token": refresh_token}
        except Exception as e:
            logger.error(f"Failed to generate tokens: {str(e)}")
            raise

    @staticmethod
    def register_user(email, password, full_name):
        """Register new user with email verification."""
        try:
            # Check if user exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                raise ValueError("User with this email already exists")

            # Hash password
            password_hash = AuthService.hash_password(password)

            # Create user
            user = User(
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                auth_provider="email",
                email_verified=False,
            )
            db.session.add(user)
            db.session.commit()

            logger.info(f"User registered: {email}")

            # Create verification token
            verification_token = AuthService.create_verification_token(user.id, "email_verification", 24)

            # Send verification email
            try:
                EmailService.send_welcome_email(user, verification_token.token)
            except Exception as e:
                logger.error(f"Failed to send welcome email to {email}: {str(e)}")
                # Don't fail registration if email fails

            # Generate JWT tokens
            tokens = AuthService.generate_tokens(user.id, user.email)

            return {
                "user": user.to_dict(),
                "tokens": tokens,
                "message": "Registration successful. Please check your email to verify your account.",
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to register user: {str(e)}")
            raise

    @staticmethod
    def login_user(email, password):
        """Login user with email/password."""
        try:
            # Find user
            user = User.query.filter_by(email=email).first()
            if not user:
                raise ValueError("Invalid email or password")

            # Check password
            if not user.password_hash or not AuthService.verify_password(password, user.password_hash):
                raise ValueError("Invalid email or password")

            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Generate tokens
            tokens = AuthService.generate_tokens(user.id, user.email)

            logger.info(f"User logged in: {email}")

            return {
                "user": user.to_dict(),
                "tokens": tokens,
            }

        except Exception as e:
            logger.error(f"Login failed for {email}: {str(e)}")
            raise

    @staticmethod
    def verify_email(token_string):
        """Verify user email with token."""
        try:
            # Find token
            token = VerificationToken.query.filter_by(
                token=token_string, token_type="email_verification"
            ).first()

            if not token:
                raise ValueError("Invalid verification token")

            if token.is_expired():
                raise ValueError("Verification token has expired")

            if token.is_used:
                raise ValueError("Verification token has already been used")

            # Update user
            user = User.query.get(token.user_id)
            if not user:
                raise ValueError("User not found")

            user.email_verified = True
            token.is_used = True
            token.used_at = datetime.utcnow()
            db.session.commit()

            logger.info(f"Email verified for user: {user.email}")

            return {"user": user.to_dict(), "message": "Email verified successfully"}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to verify email: {str(e)}")
            raise

    @staticmethod
    def request_password_reset(email):
        """Request password reset token."""
        try:
            # Find user
            user = User.query.filter_by(email=email).first()
            if not user:
                raise ValueError("User not found")

            # Create reset token (15 minutes)
            reset_token = AuthService.create_verification_token(user.id, "password_reset", 15)

            # Send reset email
            try:
                EmailService.send_password_reset_email(user, reset_token.token)
            except Exception as e:
                logger.error(f"Failed to send password reset email to {email}: {str(e)}")
                raise

            logger.info(f"Password reset requested for: {email}")

            return {"message": "Password reset email sent"}

        except Exception as e:
            logger.error(f"Failed to request password reset: {str(e)}")
            raise

    @staticmethod
    def reset_password(token_string, new_password):
        """Reset password with token."""
        try:
            # Find token
            token = VerificationToken.query.filter_by(
                token=token_string, token_type="password_reset"
            ).first()

            if not token:
                raise ValueError("Invalid reset token")

            if token.is_expired():
                raise ValueError("Reset token has expired")

            if token.is_used:
                raise ValueError("Reset token has already been used")

            # Update user password
            user = User.query.get(token.user_id)
            if not user:
                raise ValueError("User not found")

            user.password_hash = AuthService.hash_password(new_password)
            token.is_used = True
            token.used_at = datetime.utcnow()
            db.session.commit()

            logger.info(f"Password reset for user: {user.email}")

            return {"message": "Password reset successfully"}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to reset password: {str(e)}")
            raise

    @staticmethod
    def change_password(user_id, current_password, new_password):
        """Change user password."""
        try:
            # Find user
            user = User.query.get(user_id)
            if not user:
                raise ValueError("User not found")

            # Verify current password
            if not AuthService.verify_password(current_password, user.password_hash):
                raise ValueError("Current password is incorrect")

            # Update password
            user.password_hash = AuthService.hash_password(new_password)
            db.session.commit()

            logger.info(f"Password changed for user: {user.email}")

            return {"message": "Password changed successfully"}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to change password: {str(e)}")
            raise

    @staticmethod
    def create_verification_token(user_id, token_type, expires_in_minutes):
        """Create verification token."""
        try:
            import uuid

            token_string = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

            token = VerificationToken(
                user_id=user_id,
                token_type=token_type,
                token=token_string,
                expires_at=expires_at,
                is_used=False,
            )
            db.session.add(token)
            db.session.commit()

            logger.debug(f"Verification token created: {token_type}")
            return token

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create verification token: {str(e)}")
            raise

    @staticmethod
    def sanitize_user(user):
        """Remove sensitive fields from user object."""
        if not user:
            return None
        return user.to_dict()
