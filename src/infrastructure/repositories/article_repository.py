"""Repository for Article data access."""

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.selectable import ScalarSelect

from domain.models import Article, BlockedDomain, Category, Website


class ArticleRepository:
    """Repository for Article data access operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _blocked_domains_subquery(self) -> ScalarSelect[Any]:
        """Get subquery for blocked domains."""
        return select(BlockedDomain.domain).scalar_subquery()

    def get_list(
        self,
        website_id: str | None = None,
        is_read: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[Article]:
        """Get articles with pagination and filters, excluding blocked domains."""
        blocked_domains = self._blocked_domains_subquery()

        stmt = select(Article).where(~Article.domain.in_(blocked_domains))

        if website_id is not None:
            stmt = stmt.where(Article.website_id == website_id)
        if is_read is not None:
            stmt = stmt.where(Article.is_read == is_read)

        stmt = stmt.order_by(Article.published_at.desc().nullslast())
        stmt = stmt.offset(offset).limit(limit)

        result: Sequence[Article] = self.session.scalars(stmt).all()
        return result

    def get_by_id(self, article_id: str) -> Article | None:
        """Get an article by its ID."""
        stmt = select(Article).where(Article.id == article_id)
        return self.session.scalars(stmt).first()

    def get_by_url(self, url: str) -> Article | None:
        """Get an article by its URL."""
        stmt = select(Article).where(Article.url == url)
        return self.session.scalars(stmt).first()

    def get_for_website(
        self, website_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[Article], bool]:
        """
        Get articles for a website, excluding blocked domains.

        Returns:
            Tuple of (articles, has_more)
        """
        blocked_domains = self._blocked_domains_subquery()

        stmt = (
            select(Article)
            .where(Article.website_id == website_id)
            .where(~Article.domain.in_(blocked_domains))
            .order_by(
                Article.published_at.desc().nullslast(), Article.fetched_at.desc()
            )
            .offset(offset)
            .limit(limit + 1)
        )
        articles_result = list(self.session.scalars(stmt).all())

        has_more = len(articles_result) > limit
        articles = articles_result[:limit]

        return articles, has_more

    def get_unread_for_websites(
        self, website_ids: list[str], limit: int = 50
    ) -> Sequence[Article]:
        """Get unread articles for given website IDs, excluding blocked domains."""
        if not website_ids:
            return []

        blocked_domains = self._blocked_domains_subquery()

        stmt = (
            select(Article)
            .options(joinedload(Article.website))
            .where(Article.website_id.in_(website_ids))
            .where(~Article.domain.in_(blocked_domains))
            .where(Article.is_read == False)  # noqa: E712
            .order_by(
                Article.published_at.desc().nullslast(), Article.fetched_at.desc()
            )
            .limit(limit)
        )
        return self.session.scalars(stmt).unique().all()

    def get_read_with_search(
        self,
        page: int = 1,
        per_page: int = 20,
        search_query: str = "",
    ) -> tuple[Sequence[Article], int, int]:
        """
        Get read articles with optional search and pagination.

        Returns:
            Tuple of (articles, total_count, total_pages)
        """
        blocked_domains = self._blocked_domains_subquery()

        base_stmt = (
            select(Article)
            .join(Article.website)
            .join(Website.category)
            .where(Article.is_read == True)  # noqa: E712
            .where(~Article.domain.in_(blocked_domains))
        )

        if search_query:
            search_pattern = f"%{search_query}%"
            base_stmt = base_stmt.where(
                or_(
                    Article.title.ilike(search_pattern),
                    Article.url.ilike(search_pattern),
                    Category.name.ilike(search_pattern),
                )
            )

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = self.session.execute(count_stmt).scalar() or 0

        total_pages = (total_count + per_page - 1) // per_page if total_count else 1
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page

        articles_stmt = (
            base_stmt.options(joinedload(Article.website).joinedload(Website.category))
            .order_by(
                Article.published_at.desc().nullslast(), Article.fetched_at.desc()
            )
            .offset(offset)
            .limit(per_page)
        )
        articles = self.session.scalars(articles_stmt).unique().all()

        return articles, total_count, total_pages

    def mark_as_read(self, article: Article, is_read: bool = True) -> Article:
        """Mark an article as read or unread."""
        article.is_read = is_read
        self.session.commit()
        self.session.refresh(article)
        return article

    def mark_all_as_unread_for_website(self, website_id: str) -> int:
        """Mark all articles for a website as unread.

        Returns:
            Number of articles marked as unread.
        """
        stmt = (
            select(Article)
            .where(Article.website_id == website_id)
            .where(Article.is_read == True)  # noqa: E712
        )
        articles = self.session.scalars(stmt).all()
        count = len(articles)
        for article in articles:
            article.is_read = False
        self.session.commit()
        return count

    def mark_as_favorite(self, article: Article, is_favorite: bool = True) -> Article:
        """Mark an article as favorite or remove from favorites."""
        article.favorited_at = datetime.utcnow() if is_favorite else None
        self.session.commit()
        self.session.refresh(article)
        return article

    def get_favorites(
        self, limit: int = 30, offset: int = 0, search_query: str = ""
    ) -> tuple[Sequence[Article], int, bool]:
        """
        Get favorite articles with pagination, ordered by favorited_at descending.

        Args:
            limit: Number of articles to return (default 30).
            offset: Starting offset for pagination.
            search_query: Optional search filter for title or URL.

        Returns:
            Tuple of (articles, total_count, has_more).
        """
        blocked_domains = self._blocked_domains_subquery()

        base_conditions = [
            Article.favorited_at.isnot(None),
            ~Article.domain.in_(blocked_domains),
        ]

        if search_query:
            search_pattern = f"%{search_query}%"
            base_conditions.append(
                or_(
                    Article.title.ilike(search_pattern),
                    Article.url.ilike(search_pattern),
                )
            )

        # Get total count
        count_stmt = select(func.count()).select_from(Article).where(*base_conditions)
        total_count: int = self.session.execute(count_stmt).scalar() or 0

        # Get paginated articles
        articles_stmt = (
            select(Article)
            .options(joinedload(Article.website))
            .where(*base_conditions)
            .order_by(Article.favorited_at.desc())
            .offset(offset)
            .limit(limit)
        )
        articles = self.session.scalars(articles_stmt).unique().all()

        has_more = total_count > offset + len(articles)

        return articles, total_count, has_more

    def create(
        self,
        title: str,
        url: str,
        website_id: str,
        domain: str | None = None,
        content_html: str | None = None,
        published_at: datetime | None = None,
        reading_time_minutes: int | None = None,
    ) -> Article | None:
        """
        Create a new article.

        Returns:
            The created article, or None if it already exists (duplicate URL).
        """
        article = Article(
            title=title,
            url=url,
            domain=domain,
            content_html=content_html,
            website_id=website_id,
            published_at=published_at,
            fetched_at=datetime.utcnow(),
            is_read=False,
            reading_time_minutes=reading_time_minutes,
        )

        try:
            self.session.add(article)
            self.session.flush()
            return article
        except IntegrityError:
            self.session.rollback()
            return None

    def delete_by_website_id(self, website_id: str) -> None:
        """Delete all articles for a website."""
        stmt = delete(Article).where(Article.website_id == website_id)
        self.session.execute(stmt)
        self.session.commit()

    def get_read_grouped_by_website(
        self,
        search_query: str = "",
        limit_per_website: int = 15,
    ) -> list[dict[str, Any]]:
        """
        Get read articles grouped by website with pagination support.

        Args:
            search_query: Optional search filter for title, url, category, or website name.
            limit_per_website: Maximum articles to return per website.

        Returns:
            List of dicts with website info, limited articles, total_count, and has_more.
        """
        blocked_domains = self._blocked_domains_subquery()

        base_stmt = (
            select(Article)
            .join(Article.website)
            .join(Website.category)
            .options(joinedload(Article.website))
            .where(Article.is_read == True)  # noqa: E712
            .where(~Article.domain.in_(blocked_domains))
        )

        if search_query:
            search_pattern = f"%{search_query}%"
            base_stmt = base_stmt.where(
                or_(
                    Article.title.ilike(search_pattern),
                    Article.url.ilike(search_pattern),
                    Category.name.ilike(search_pattern),
                    Website.name.ilike(search_pattern),
                )
            )

        articles_stmt = base_stmt.order_by(
            Article.published_at.desc().nullslast(), Article.fetched_at.desc()
        )
        articles = self.session.scalars(articles_stmt).unique().all()

        # Group articles by website
        websites_dict: dict[str, dict[str, Any]] = {}
        for article in articles:
            website_id = article.website_id
            if website_id not in websites_dict:
                websites_dict[website_id] = {
                    "id": article.website.id,
                    "name": article.website.name,
                    "url": article.website.url,
                    "articles": [],
                    "total_count": 0,
                }
            websites_dict[website_id]["articles"].append(article)
            websites_dict[website_id]["total_count"] += 1

        # Limit articles per website and add has_more flag
        for website_data in websites_dict.values():
            total = website_data["total_count"]
            website_data["articles"] = website_data["articles"][:limit_per_website]
            website_data["has_more"] = total > limit_per_website

        # Sort websites by most recent article
        result = list(websites_dict.values())
        result.sort(
            key=lambda w: (
                w["articles"][0].published_at or w["articles"][0].fetched_at
                if w["articles"]
                else None
            ),
            reverse=True,
        )

        return result

    def get_read_for_website_paginated(
        self,
        website_id: str,
        search_query: str = "",
        limit: int = 15,
        offset: int = 0,
    ) -> tuple[list[Article], int, bool]:
        """
        Get read articles for a specific website with pagination.

        Args:
            website_id: The website ID to fetch articles for.
            search_query: Optional search filter.
            limit: Number of articles to return.
            offset: Starting offset.

        Returns:
            Tuple of (articles, total_count, has_more).
        """
        blocked_domains = self._blocked_domains_subquery()

        base_conditions = [
            Article.website_id == website_id,
            Article.is_read == True,  # noqa: E712
            ~Article.domain.in_(blocked_domains),
        ]

        if search_query:
            search_pattern = f"%{search_query}%"
            base_conditions.append(
                or_(
                    Article.title.ilike(search_pattern),
                    Article.url.ilike(search_pattern),
                )
            )

        # Get total count
        count_stmt = select(func.count()).select_from(Article).where(*base_conditions)
        total_count: int = self.session.execute(count_stmt).scalar() or 0

        # Get paginated articles
        articles_stmt = (
            select(Article)
            .where(*base_conditions)
            .order_by(
                Article.published_at.desc().nullslast(),
                Article.fetched_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        articles = list(self.session.scalars(articles_stmt).all())

        has_more = total_count > offset + len(articles)

        return articles, total_count, has_more

    def get_unread_for_category_paginated(
        self,
        website_ids: list[str],
        limit: int = 12,
        offset: int = 0,
    ) -> tuple[Sequence[Article], int, bool]:
        """
        Get unread articles for websites in a category with pagination.

        Args:
            website_ids: List of website IDs in the category.
            limit: Number of articles to return.
            offset: Starting offset.

        Returns:
            Tuple of (articles, total_count, has_more).
        """
        if not website_ids:
            return [], 0, False

        blocked_domains = self._blocked_domains_subquery()

        base_conditions = [
            Article.website_id.in_(website_ids),
            Article.is_read == False,  # noqa: E712
            ~Article.domain.in_(blocked_domains),
        ]

        # Get total count
        count_stmt = select(func.count()).select_from(Article).where(*base_conditions)
        total_count: int = self.session.execute(count_stmt).scalar() or 0

        # Get paginated articles
        articles_stmt = (
            select(Article)
            .options(joinedload(Article.website))
            .where(*base_conditions)
            .order_by(
                Article.published_at.desc().nullslast(),
                Article.fetched_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        articles = self.session.scalars(articles_stmt).unique().all()

        has_more = total_count > offset + len(articles)

        return articles, total_count, has_more
