import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class AppSettings(Base):  # type: ignore[misc]
    """Single-user app settings including authentication."""

    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(5), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """Hash a password with the given salt using SHA-256."""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    @staticmethod
    def generate_salt() -> str:
        """Generate a random salt."""
        return secrets.token_hex(32)

    def set_password(self, password: str) -> None:
        """Set the password."""
        self.password_salt = self.generate_salt()
        self.password_hash = self.hash_password(password, self.password_salt)

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return self.password_hash == self.hash_password(password, self.password_salt)
