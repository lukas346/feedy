"""Repository for Category data access."""

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.models import Category, Website


class CategoryRepository:
    """Repository for Category data access operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_all(self) -> Sequence[Category]:
        """Get all categories ordered by name."""
        stmt = select(Category).order_by(Category.name)
        return self.session.scalars(stmt).all()

    def get_all_with_website_counts(self) -> list[tuple[Category, int]]:
        """Get all categories with their website counts, ordered by name."""
        website_count_subquery = (
            select(Website.category_id, func.count(Website.id).label("count"))
            .group_by(Website.category_id)
            .subquery()
        )

        stmt = (
            select(
                Category,
                func.coalesce(website_count_subquery.c.count, 0).label("website_count"),
            )
            .outerjoin(
                website_count_subquery,
                Category.id == website_count_subquery.c.category_id,
            )
            .order_by(Category.name)
        )
        result = self.session.execute(stmt).all()
        return [(cat, count) for cat, count in result]

    def get_by_id(self, category_id: str) -> Category | None:
        """Get a category by its ID."""
        stmt = select(Category).where(Category.id == category_id)
        return self.session.scalars(stmt).first()

    def create(self, name: str, slug: str, icon: str | None = "tag") -> Category:
        """Create a new category."""
        category = Category(name=name, slug=slug, icon=icon)
        self.session.add(category)
        self.session.flush()
        self.session.refresh(category)
        return category

    def update(
        self,
        category: Category,
        name: str | None = None,
        slug: str | None = None,
        icon: str | None = None,
    ) -> Category:
        """Update a category's fields."""
        if name is not None:
            category.name = name
        if slug is not None:
            category.slug = slug
        if icon is not None:
            category.icon = icon
        self.session.flush()
        self.session.refresh(category)
        return category

    def delete(self, category: Category) -> None:
        """Delete a category."""
        self.session.delete(category)
        self.session.flush()
