import html
import logging
from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import Optional

import feedparser
from feedparser import FeedParserDict

from application.services.url_filter import url_filter

logger = logging.getLogger(__name__)


@dataclass
class ParsedArticle:
    """Represents an article parsed from an RSS/Atom feed."""

    title: str
    url: str
    published_at: Optional[datetime]
    content: Optional[str]


class RSSParser:
    """Parser for RSS/Atom feeds using feedparser."""

    def parse(self, feed_content: str) -> list[ParsedArticle]:
        """
        Parse RSS/Atom feed content and extract articles.

        Args:
            feed_content: Raw XML string of the RSS/Atom feed

        Returns:
            List of ParsedArticle objects extracted from the feed
        """
        feed: FeedParserDict = feedparser.parse(feed_content)
        articles: list[ParsedArticle] = []

        for entry in feed.entries:
            article = self._parse_entry(entry)
            if article:
                articles.append(article)

        return articles

    def parse_url(self, url: str) -> list[ParsedArticle]:
        """
        Fetch and parse RSS/Atom feed from a URL.

        Args:
            url: URL of the RSS/Atom feed

        Returns:
            List of ParsedArticle objects extracted from the feed
        """
        feed: FeedParserDict = feedparser.parse(url)
        articles: list[ParsedArticle] = []

        for entry in feed.entries:
            article = self._parse_entry(entry)
            if article:
                articles.append(article)

        return articles

    def _parse_entry(self, entry: FeedParserDict) -> Optional[ParsedArticle]:
        """
        Parse a single feed entry into a ParsedArticle.

        Args:
            entry: A feedparser entry object

        Returns:
            ParsedArticle if entry has required fields, None otherwise
        """
        title = self._get_title(entry)
        url = self._get_url(entry)

        if not title or not url:
            return None

        # Filter out non-article URLs
        if not url_filter.is_article_url(url):
            reason = url_filter.get_rejection_reason(url)
            logger.debug(f"Skipping non-article URL: {url} (reason: {reason})")
            return None

        return ParsedArticle(
            title=title,
            url=url,
            published_at=self._get_published_date(entry),
            content=self._get_content(entry),
        )

    def _get_title(self, entry: FeedParserDict) -> Optional[str]:
        """Extract title from feed entry, decoding HTML entities."""
        title: Optional[str] = getattr(entry, "title", None)
        if title:
            return html.unescape(title)
        return None

    def _get_url(self, entry: FeedParserDict) -> Optional[str]:
        """Extract URL from feed entry."""
        return getattr(entry, "link", None)

    def _get_published_date(self, entry: FeedParserDict) -> Optional[datetime]:
        """Extract and parse publication date from feed entry."""
        published_parsed = getattr(entry, "published_parsed", None)
        if published_parsed:
            try:
                return datetime.fromtimestamp(mktime(published_parsed))
            except (ValueError, OverflowError):
                pass

        updated_parsed = getattr(entry, "updated_parsed", None)
        if updated_parsed:
            try:
                return datetime.fromtimestamp(mktime(updated_parsed))
            except (ValueError, OverflowError):
                pass

        return None

    def _get_content(self, entry: FeedParserDict) -> Optional[str]:
        """Extract content from feed entry, decoding HTML entities."""
        content: Optional[str] = None

        if hasattr(entry, "content") and entry.content:
            value = entry.content[0].get("value", None)
            content = str(value) if value is not None else None
        elif hasattr(entry, "summary"):
            content = str(entry.summary)
        elif hasattr(entry, "description"):
            content = str(entry.description)

        if content:
            return html.unescape(content)
        return None
