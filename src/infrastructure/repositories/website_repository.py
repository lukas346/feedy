"""Repository for Website data access."""

from datetime import datetime, timedelta
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.models import Article, Category, Website


class WebsiteRepository:
    """Repository for Website data access operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_all(self) -> Sequence[Website]:
        """Get all websites."""
        stmt = select(Website)
        return self.session.scalars(stmt).all()

    def get_all_with_unread_counts(
        self, category_id: str | None = None
    ) -> list[tuple[Website, int]]:
        """Get all websites with their unread article counts."""
        unread_count_subquery = (
            select(
                Article.website_id,
                func.count(Article.id).label("count"),
            )
            .where(Article.is_read == False)  # noqa: E712
            .group_by(Article.website_id)
            .subquery()
        )

        stmt = (
            select(
                Website,
                func.coalesce(unread_count_subquery.c.count, 0).label("unread_count"),
            )
            .outerjoin(
                unread_count_subquery,
                Website.id == unread_count_subquery.c.website_id,
            )
        )

        if category_id is not None:
            stmt = stmt.where(Website.category_id == category_id)

        stmt = stmt.order_by(Website.name)
        result = self.session.execute(stmt).all()
        return [(website, count) for website, count in result]

    def get_all_with_category_names(
        self,
    ) -> list[tuple[Website, str | None, str | None]]:
        """Get all websites with category names and icons, ordered by category."""
        stmt = (
            select(
                Website,
                Category.name.label("category_name"),
                Category.icon.label("category_icon"),
            )
            .outerjoin(Category, Website.category_id == Category.id)
            .order_by(Category.name, Website.name)
        )
        result = self.session.execute(stmt).all()
        return [
            (website, category_name, category_icon)
            for website, category_name, category_icon in result
        ]

    def get_by_id(self, website_id: str) -> Website | None:
        """Get a website by its ID."""
        stmt = select(Website).where(Website.id == website_id)
        return self.session.scalars(stmt).first()

    def get_by_rss_url(self, rss_url: str) -> Website | None:
        """Get a website by its RSS URL."""
        stmt = select(Website).where(Website.rss_url == rss_url)
        return self.session.scalars(stmt).first()

    def get_ids_by_category(self, category_id: str) -> list[str]:
        """Get all website IDs for a category."""
        stmt = select(Website.id).where(Website.category_id == category_id)
        return list(self.session.scalars(stmt).all())

    def get_due_for_update(self) -> list[Website]:
        """
        Get websites that need to be fetched based on their interval.

        A website is due for update if:
        - It has never been fetched (last_fetched_at is None)
        - The time since last fetch exceeds fetch_interval_minutes
        """
        now = datetime.utcnow()
        websites: list[Website] = []

        stmt = select(Website)
        result = self.session.execute(stmt)

        for website in result.scalars().all():
            if website.last_fetched_at is None:
                websites.append(website)
            else:
                next_fetch_time = website.last_fetched_at + timedelta(
                    minutes=website.fetch_interval_minutes
                )
                if now >= next_fetch_time:
                    websites.append(website)

        return websites

    def create(
        self,
        name: str,
        url: str,
        rss_url: str,
        category_id: str,
        fetch_interval_minutes: int = 60,
    ) -> Website:
        """Create a new website."""
        website = Website(
            name=name,
            url=url,
            rss_url=rss_url,
            category_id=category_id,
            fetch_interval_minutes=fetch_interval_minutes,
        )
        self.session.add(website)
        self.session.commit()
        self.session.refresh(website)
        return website

    def update(
        self,
        website: Website,
        name: str | None = None,
        url: str | None = None,
        rss_url: str | None = None,
        category_id: str | None = None,
        fetch_interval_minutes: int | None = None,
    ) -> Website:
        """Update a website's fields."""
        if name is not None:
            website.name = name
        if url is not None:
            website.url = url
        if rss_url is not None:
            website.rss_url = rss_url
        if category_id is not None:
            website.category_id = category_id
        if fetch_interval_minutes is not None:
            website.fetch_interval_minutes = fetch_interval_minutes
        self.session.commit()
        self.session.refresh(website)
        return website

    def update_last_fetched(self, website: Website) -> None:
        """Update the last_fetched_at timestamp to now."""
        website.last_fetched_at = datetime.utcnow()
        self.session.commit()

    def delete(self, website: Website) -> None:
        """Delete a website and cascade to articles."""
        self.session.delete(website)
        self.session.commit()
