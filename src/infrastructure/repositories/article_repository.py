"""Repository for Article data access."""

from datetime import datetime
from typing import Any, Sequence, cast

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.selectable import ScalarSelect

from domain.models import Article, BlockedDomain, Website
from infrastructure.config import DEFAULT_PAGE_SIZE


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
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Sequence[Article]:
        """Get articles with pagination and blocked-domain filtering."""
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

    def get_by_ids(self, article_ids: Sequence[str]) -> list[Article]:
        """Get articles by IDs, preserving the provided ID order."""
        if not article_ids:
            return []

        stmt = (
            select(Article)
            .options(joinedload(Article.website))
            .where(Article.id.in_(article_ids))
        )
        articles_by_id = {}
        for article in self.session.scalars(stmt).unique().all():
            articles_by_id[article.id] = article
        return [
            articles_by_id[article_id]
            for article_id in article_ids
            if article_id in articles_by_id
        ]

    def get_by_url(self, url: str) -> Article | None:
        """Get an article by its URL."""
        stmt = select(Article).where(Article.url == url)
        return self.session.scalars(stmt).first()

    def get_reader_neighbors(
        self, article: Article
    ) -> tuple[Article | None, Article | None]:
        """Get previous and next article in the website article list order."""
        blocked_domains = self._blocked_domains_subquery()
        ordered_articles = (
            select(
                Article.id.label("id"),
                func.lag(Article.id)
                .over(
                    order_by=(
                        Article.published_at.desc().nullslast(),
                        Article.fetched_at.desc(),
                        Article.id.desc(),
                    )
                )
                .label("previous_id"),
                func.lead(Article.id)
                .over(
                    order_by=(
                        Article.published_at.desc().nullslast(),
                        Article.fetched_at.desc(),
                        Article.id.desc(),
                    )
                )
                .label("next_id"),
            )
            .where(Article.website_id == article.website_id)
            .where(~Article.domain.in_(blocked_domains))
            .subquery()
        )

        row = self.session.execute(
            select(ordered_articles.c.previous_id, ordered_articles.c.next_id).where(
                ordered_articles.c.id == article.id
            )
        ).one_or_none()
        if row is None:
            return None, None

        previous_id = cast(str | None, row[0])
        next_id = cast(str | None, row[1])
        previous_article = self.get_by_id(previous_id) if previous_id else None
        next_article = self.get_by_id(next_id) if next_id else None

        return previous_article, next_article

    def get_reader_neighbors_for_category(
        self, article: Article, category_id: str
    ) -> tuple[Article | None, Article | None]:
        """Get previous and next unread article in the category list order."""
        blocked_domains = self._blocked_domains_subquery()
        ordered_articles = (
            select(
                Article.id.label("id"),
                func.lag(Article.id)
                .over(
                    order_by=(
                        Article.published_at.desc().nullslast(),
                        Article.fetched_at.desc(),
                        Article.id.desc(),
                    )
                )
                .label("previous_id"),
                func.lead(Article.id)
                .over(
                    order_by=(
                        Article.published_at.desc().nullslast(),
                        Article.fetched_at.desc(),
                        Article.id.desc(),
                    )
                )
                .label("next_id"),
            )
            .join(Website, Article.website_id == Website.id)
            .where(Website.category_id == category_id)
            .where(~Article.domain.in_(blocked_domains))
            .where(or_(Article.is_read == False, Article.id == article.id))  # noqa: E712
            .subquery()
        )

        row = self.session.execute(
            select(ordered_articles.c.previous_id, ordered_articles.c.next_id).where(
                ordered_articles.c.id == article.id
            )
        ).one_or_none()
        if row is None:
            return None, None

        previous_id = cast(str | None, row[0])
        next_id = cast(str | None, row[1])
        previous_article = self.get_by_id(previous_id) if previous_id else None
        next_article = self.get_by_id(next_id) if next_id else None

        return previous_article, next_article

    def get_for_website(
        self,
        website_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> tuple[list[Article], int, bool]:
        """
        Get articles for a website, excluding blocked domains.

        Returns:
            Tuple of (articles, total_count, has_more)
        """
        blocked_domains = self._blocked_domains_subquery()

        base_conditions = [
            Article.website_id == website_id,
            ~Article.domain.in_(blocked_domains),
        ]

        # Get total count
        count_select = select(func.count()).select_from(Article)
        count_stmt = count_select.where(*base_conditions)
        total_count: int = self.session.execute(count_stmt).scalar() or 0

        # Get paginated articles
        stmt = (
            select(Article)
            .where(*base_conditions)
            .order_by(
                Article.published_at.desc().nullslast(),
                Article.fetched_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        articles = list(self.session.scalars(stmt).all())

        has_more = total_count > offset + len(articles)

        return articles, total_count, has_more

    def get_unread_for_websites(
        self,
        website_ids: list[str],
        limit: int = 50,
    ) -> Sequence[Article]:
        """Get unread articles with blocked-domain filtering."""
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
                Article.published_at.desc().nullslast(),
                Article.fetched_at.desc(),
            )
            .limit(limit)
        )
        return self.session.scalars(stmt).unique().all()

    def mark_as_read(self, article: Article, is_read: bool = True) -> Article:
        """Mark an article as read or unread."""
        article.is_read = is_read
        self.session.flush()
        self.session.refresh(article)
        return article

    def mark_all_as_unread_for_website(self, website_id: str) -> int:
        """Mark all articles for a website as unread.

        Returns:
            Number of articles marked as unread.
        """
        stmt = (
            update(Article)
            .where(Article.website_id == website_id)
            .where(Article.is_read == True)  # noqa: E712
            .values(is_read=False)
        )
        result = cast(CursorResult[Any], self.session.execute(stmt))
        self.session.flush()
        return result.rowcount or 0

    def mark_all_as_read_for_website(self, website_id: str) -> int:
        """Mark all articles for a website as read.

        Returns:
            Number of articles marked as read.
        """
        stmt = (
            update(Article)
            .where(Article.website_id == website_id)
            .where(Article.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        result = cast(CursorResult[Any], self.session.execute(stmt))
        self.session.flush()
        return result.rowcount or 0

    def mark_all_as_read_for_websites(self, website_ids: Sequence[str]) -> int:
        """Mark all articles for multiple websites as read.

        Returns:
            Number of articles marked as read.
        """
        if not website_ids:
            return 0

        stmt = (
            update(Article)
            .where(Article.website_id.in_(website_ids))
            .where(Article.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        result = cast(CursorResult[Any], self.session.execute(stmt))
        self.session.flush()
        return result.rowcount or 0

    def mark_as_read_by_ids(self, article_ids: Sequence[str]) -> int:
        """Mark selected articles as read.

        Returns:
            Number of articles changed from unread to read.
        """
        if not article_ids:
            return 0

        stmt = (
            update(Article)
            .where(Article.id.in_(article_ids))
            .where(Article.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        result = cast(CursorResult[Any], self.session.execute(stmt))
        self.session.flush()
        return result.rowcount or 0

    def mark_as_favorite(
        self,
        article: Article,
        is_favorite: bool = True,
    ) -> Article:
        """Mark an article as favorite or remove from favorites."""
        article.favorited_at = datetime.utcnow() if is_favorite else None
        self.session.flush()
        self.session.refresh(article)
        return article

    def get_favorites(
        self,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        search_query: str = "",
    ) -> tuple[Sequence[Article], int, bool]:
        """
        Get favorite articles with pagination.

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
        count_select = select(func.count()).select_from(Article)
        count_stmt = count_select.where(*base_conditions)
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
            with self.session.begin_nested():
                self.session.add(article)
                self.session.flush()
            return article
        except IntegrityError:
            return None

    def delete_by_website_id(self, website_id: str) -> None:
        """Delete all articles for a website."""
        stmt = delete(Article).where(Article.website_id == website_id)
        self.session.execute(stmt)
        self.session.flush()

    def get_unread_for_category_paginated(
        self,
        website_ids: list[str],
        limit: int = DEFAULT_PAGE_SIZE,
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
        count_select = select(func.count()).select_from(Article)
        count_stmt = count_select.where(*base_conditions)
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
