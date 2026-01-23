"""Authentication service for single-user app."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from domain.models import Session
from infrastructure.repositories import AuthRepository


class AuthService:
    """Service for handling authentication."""

    SESSION_DURATION_DAYS = 30

    def verify_password(self, db: DbSession, password: str) -> bool:
        """Verify the provided password against stored hash."""
        repo = AuthRepository(db)
        settings = repo.get_settings()
        if not settings:
            return False
        return bool(settings.verify_password(password))

    def create_session(self, db: DbSession) -> str:
        """Create a new session and return the token."""
        repo = AuthRepository(db)

        # Clean up expired sessions
        repo.delete_expired_sessions()

        token: str = Session.generate_token()
        expires_at = datetime.utcnow() + timedelta(days=self.SESSION_DURATION_DAYS)
        repo.create_session(token=token, expires_at=expires_at)
        return token

    def validate_session(self, db: DbSession, token: str) -> bool:
        """Validate a session token."""
        if not token:
            return False
        repo = AuthRepository(db)
        session = repo.get_valid_session(token)
        return session is not None

    def delete_session(self, db: DbSession, token: str) -> None:
        """Delete a session (logout)."""
        repo = AuthRepository(db)
        repo.delete_session_by_token(token)

    def must_change_password(self, db: DbSession) -> bool:
        """Check if password must be changed."""
        repo = AuthRepository(db)
        settings = repo.get_settings()
        return settings.must_change_password if settings else True

    def change_password(
        self, db: DbSession, current_password: str, new_password: str
    ) -> bool:
        """Change the password. Returns True if successful."""
        repo = AuthRepository(db)
        settings = repo.get_settings()
        if not settings:
            return False

        if not settings.verify_password(current_password):
            return False

        settings.set_password(new_password)
        repo.update_settings(settings, must_change_password=False)
        return True


auth_service = AuthService()
