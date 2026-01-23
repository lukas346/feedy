from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database import Base

if TYPE_CHECKING:
    from domain.models.website import Website


class Category(Base):  # type: ignore[misc]
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default="tag"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    websites: Mapped[list["Website"]] = relationship(
        "Website", back_populates="category", cascade="all, delete-orphan"
    )
