import secrets
import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class Session(Base):  # type: ignore[misc]
    """Session model for managing login sessions."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    @staticmethod
    def generate_token() -> str:
        """Generate a random session token."""
        return secrets.token_hex(32)
