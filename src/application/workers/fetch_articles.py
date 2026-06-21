"""Background worker for fetching new articles from RSS feeds."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from application.services.content_converter import ContentConverter
from application.services.domain_utils import extract_domain
from application.services.reading_time import calculate_reading_time
from application.services.rss_parser import ParsedArticle, RSSParser
from application.services.url_filter import url_filter
from domain.models import Website
from infrastructure.database import SessionLocal
from infrastructure.repositories import (
    ArticleRepository,
    BlockedDomainRepository,
    WebsiteRepository,
)

logger = logging.getLogger(__name__)


class ArticleFetcher:
    """
    Background worker that fetches new articles for websites.

    The worker:
    - Queries websites that are due for an update
    - Fetches RSS feed and parses articles
    - Extracts clean HTML content from articles
    - Stores new articles (skipping duplicates)
    - Updates website's last_fetched_at timestamp
    """

    def __init__(
        self,
        rss_parser: Optional[RSSParser] = None,
        content_converter: Optional[ContentConverter] = None,
    ) -> None:
        """
        Initialize the article fetcher.

        Args:
            rss_parser: RSS parser instance (created if not provided)
            content_converter: Content converter instance (created if not provided)
        """
        self.rss_parser = rss_parser or RSSParser()
        self.content_converter = content_converter or ContentConverter()

    def run(self, session: Optional[Session] = None) -> int:
        """
        Run the article fetcher once, processing all websites due for update.

        Args:
            session: Database session (created if not provided)

        Returns:
            Number of new articles fetched
        """
        own_session = session is None
        db_session: Session = session if session is not None else SessionLocal()

        try:
            website_repo = WebsiteRepository(db_session)
            websites = website_repo.get_due_for_update()
            total_new_articles = 0

            for website in websites:
                try:
                    new_count = self._fetch_website_with_transaction(
                        db_session, website, own_session
                    )
                    total_new_articles += new_count
                    logger.info(f"Fetched {new_count} new articles from {website.name}")
                except Exception as e:
                    logger.error(f"Error fetching articles from {website.name}: {e}")

            return total_new_articles
        finally:
            if own_session:
                db_session.close()

    def fetch(self, session: Optional[Session] = None) -> int:
        """Alias for run() method."""
        return self.run(session)

    def fetch_all(self, session: Optional[Session] = None) -> int:
        """
        Fetch articles from all websites, ignoring their fetch intervals.

        Args:
            session: Database session (created if not provided)

        Returns:
            Number of new articles fetched
        """
        own_session = session is None
        db_session: Session = session if session is not None else SessionLocal()

        try:
            website_repo = WebsiteRepository(db_session)
            websites = website_repo.get_all()
            total_new_articles = 0

            for website in websites:
                try:
                    new_count = self._fetch_website_with_transaction(
                        db_session, website, own_session
                    )
                    total_new_articles += new_count
                    logger.info(f"Fetched {new_count} new articles from {website.name}")
                except Exception as e:
                    logger.error(f"Error fetching articles from {website.name}: {e}")

            return total_new_articles
        finally:
            if own_session:
                db_session.close()

    def force_refetch_website(
        self, website_id: str, session: Optional[Session] = None
    ) -> int:
        """
        Force refetch all articles from a specific website.

        This deletes all existing articles from the website and fetches fresh
        articles from the RSS feed.

        Args:
            website_id: ID of the website to refetch
            session: Database session (created if not provided)

        Returns:
            Number of articles fetched

        Raises:
            ValueError: If website not found
        """
        own_session = session is None
        db_session: Session = session if session is not None else SessionLocal()

        try:
            website_repo = WebsiteRepository(db_session)
            article_repo = ArticleRepository(db_session)

            website = website_repo.get_by_id(website_id)
            if website is None:
                raise ValueError(f"Website with id {website_id} not found")

            # Delete all existing articles from this website
            article_repo.delete_by_website_id(website_id)
            logger.info(f"Deleted all articles from {website.name} for refetch")

            # Fetch fresh articles
            new_count = self._fetch_website_articles(db_session, website)
            if own_session:
                db_session.commit()
            logger.info(f"Refetched {new_count} articles from {website.name}")

            return new_count
        except Exception:
            if own_session:
                db_session.rollback()
            raise
        finally:
            if own_session:
                db_session.close()

    def _fetch_website_with_transaction(
        self, session: Session, website: Website, own_session: bool
    ) -> int:
        """Fetch one website and commit when this worker owns the session."""
        if own_session:
            try:
                new_count = self._fetch_website_articles(session, website)
                session.commit()
                return new_count
            except Exception:
                session.rollback()
                raise

        with session.begin_nested():
            return self._fetch_website_articles(session, website)

    def _fetch_website_articles(self, session: Session, website: Website) -> int:
        """
        Fetch and store articles for a single website.

        Args:
            session: Database session
            website: Website to fetch articles from

        Returns:
            Number of new articles stored
        """
        parsed_articles = self.rss_parser.parse_url(website.rss_url)
        new_count = 0

        for parsed in parsed_articles:
            if self._store_article(session, website, parsed):
                new_count += 1

        website_repo = WebsiteRepository(session)
        website_repo.update_last_fetched(website)

        return new_count

    def _store_article(
        self, session: Session, website: Website, parsed: ParsedArticle
    ) -> bool:
        """
        Store a parsed article in the database.

        Args:
            session: Database session
            website: Parent website
            parsed: Parsed article data

        Returns:
            True if article was stored, False if it already exists or was filtered
        """
        # Secondary filter check (primary is in RSS parser)
        if not url_filter.is_article_url(parsed.url):
            reason = url_filter.get_rejection_reason(parsed.url)
            logger.debug(
                f"Skipping non-article URL in fetcher: {parsed.url} ({reason})"
            )
            return False

        article_repo = ArticleRepository(session)
        blocked_repo = BlockedDomainRepository(session)

        # Extract and check domain against blocked list
        domain = extract_domain(parsed.url)
        if domain and blocked_repo.is_blocked(domain):
            logger.debug(f"Skipping article from blocked domain: {domain}")
            return False

        # Check if article already exists
        existing = article_repo.get_by_url(parsed.url)
        if existing:
            return False

        content_html = self._get_article_content(parsed)
        reading_time = calculate_reading_time(content_html)

        article = article_repo.create(
            title=parsed.title,
            url=parsed.url,
            domain=domain,
            content_html=content_html,
            website_id=website.id,
            published_at=parsed.published_at,
            reading_time_minutes=reading_time,
        )

        return article is not None

    def _get_article_content(self, parsed: ParsedArticle) -> Optional[str]:
        """
        Get clean HTML content for an article.

        Strategy:
        1. If RSS content is available, extract clean HTML
        2. Use the better result between RSS content and fetched content

        Args:
            parsed: Parsed article data

        Returns:
            Clean HTML content or None
        """
        rss_content: Optional[str] = None
        fetched_content: Optional[str] = None

        # Try to extract from RSS content first
        if parsed.content:
            try:
                rss_content = self.content_converter.to_html(
                    parsed.content, base_url=parsed.url, title=parsed.title
                )
            except Exception as e:
                logger.debug(f"RSS content extraction failed: {e}")

        try:
            fetched_content = self.content_converter.fetch_and_convert_sync(
                parsed.url, title=parsed.title
            )
        except Exception as e:
            logger.warning(f"Failed to fetch content for {parsed.url}: {e}")

        # Return the better result by extraction quality, not raw HTML length.
        if rss_content and fetched_content:
            fetched_score = self.content_converter.score_content(fetched_content)
            rss_score = self.content_converter.score_content(rss_content)
            if fetched_score > rss_score:
                return fetched_content
            return rss_content
        elif fetched_content:
            return fetched_content
        elif rss_content:
            return rss_content

        return None
