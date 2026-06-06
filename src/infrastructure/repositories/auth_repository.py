"""Repository for authentication data access (AppSettings and Session)."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from domain.models import AppSettings, Session


class AuthRepository:
    """Repository for authentication data access operations."""

    def __init__(self, session: DbSession) -> None:
        self.session = session

    def get_settings(self) -> AppSettings | None:
        """Get the app settings."""
        stmt = select(AppSettings)
        return self.session.scalars(stmt).first()

    def update_settings(
        self,
        settings: AppSettings,
        must_change_password: bool | None = None,
    ) -> AppSettings:
        """Update app settings."""
        if must_change_password is not None:
            settings.must_change_password = must_change_password
        settings.updated_at = datetime.utcnow()
        self.session.flush()
        self.session.refresh(settings)
        return settings

    def get_valid_session(self, token: str) -> Session | None:
        """Get a valid (non-expired) session by token."""
        stmt = select(Session).where(
            Session.token == token, Session.expires_at > datetime.utcnow()
        )
        return self.session.scalars(stmt).first()

    def create_session(self, token: str, expires_at: datetime) -> Session:
        """Create a new session."""
        session = Session(token=token, expires_at=expires_at)
        self.session.add(session)
        self.session.flush()
        return session

    def delete_session_by_token(self, token: str) -> None:
        """Delete a session by token."""
        stmt = delete(Session).where(Session.token == token)
        self.session.execute(stmt)
        self.session.flush()

    def delete_expired_sessions(self) -> None:
        """Delete all expired sessions."""
        stmt = delete(Session).where(Session.expires_at <= datetime.utcnow())
        self.session.execute(stmt)
        self.session.flush()

    def get_language(self) -> str | None:
        """Get the user's language preference."""
        settings = self.get_settings()
        return settings.language if settings else None

    def set_language(self, language: str | None) -> None:
        """Set the user's language preference."""
        settings = self.get_settings()
        if settings:
            settings.language = language
            settings.updated_at = datetime.utcnow()
            self.session.flush()
