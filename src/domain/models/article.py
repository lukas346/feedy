from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database import Base

if TYPE_CHECKING:
    from domain.models.website import Website


class Article(Base):  # type: ignore[misc]
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    domain: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    content_html: Mapped[Optional[str]] = mapped_column(nullable=True)
    website_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("websites.id"), nullable=False, index=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    favorited_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    reading_time_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    website: Mapped["Website"] = relationship("Website", back_populates="articles")
