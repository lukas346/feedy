from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database import Base

if TYPE_CHECKING:
    from domain.models.article import Article
    from domain.models.category import Category


class Website(Base):  # type: ignore[misc]
    __tablename__ = "websites"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    rss_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("categories.id"), nullable=False, index=True
    )
    fetch_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    category: Mapped["Category"] = relationship("Category", back_populates="websites")
    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="website", cascade="all, delete-orphan"
    )
