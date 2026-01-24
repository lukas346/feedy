"""Feed discovery service for locating and parsing RSS/Atom feeds."""

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup
from feedparser import FeedParserDict

from application.services.validators import validate_url

logger = logging.getLogger(__name__)

# Common RSS feed path patterns to try
COMMON_FEED_PATHS = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss/",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
    "/index.xml",
    "/feeds/posts/default",
    "/?feed=rss2",
]


@dataclass
class DiscoveredFeed:
    """Represents a discovered RSS/Atom feed with metadata."""

    name: str
    url: str
    rss_url: str
    description: Optional[str] = None


class FeedDiscoveryError(Exception):
    """Exception raised when feed discovery fails."""

    pass


class FeedDiscoveryService:
    """Service for discovering RSS/Atom feeds from URLs."""

    def __init__(self, timeout: float = 10.0) -> None:
        """Initialize the feed discovery service.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self._timeout = timeout

    def discover(self, url: str) -> DiscoveredFeed:
        """
        Discover feed information from a URL.

        The URL can be either a website URL or a direct feed URL.
        This method will:
        1. Try to parse the URL as a feed directly
        2. If not a feed, look for feed links in the HTML
        3. Try common feed URL patterns

        Args:
            url: The URL to discover feed from.

        Returns:
            DiscoveredFeed with feed metadata.

        Raises:
            FeedDiscoveryError: If no feed could be discovered.
        """
        if not validate_url(url):
            raise FeedDiscoveryError("Invalid URL provided")

        url = url.strip()

        # First, try to parse as a feed directly
        feed_result = self._try_parse_feed(url)
        if feed_result:
            return feed_result

        # Fetch the page content
        content = self._fetch_url(url)
        if not content:
            raise FeedDiscoveryError("Failed to fetch URL content")

        # Look for feed links in HTML
        feed_urls = self._find_feed_links(content, url)

        # Try each discovered feed URL
        for feed_url in feed_urls:
            if not validate_url(feed_url):
                continue
            feed_result = self._try_parse_feed(feed_url, website_url=url)
            if feed_result:
                return feed_result

        # Try common feed paths
        base_url = self._get_base_url(url)
        for path in COMMON_FEED_PATHS:
            feed_url = urljoin(base_url, path)
            if not validate_url(feed_url):
                continue
            feed_result = self._try_parse_feed(feed_url, website_url=url)
            if feed_result:
                return feed_result

        raise FeedDiscoveryError(
            "No RSS/Atom feed found. Please provide the feed URL directly."
        )

    def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL content with proper headers."""
        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; Feedy/1.0; "
                        "+https://github.com/feedy)"
                    ),
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,*/*;q=0.8"
                    ),
                },
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch URL {url}: {e}")
            return None

    def _try_parse_feed(
        self, url: str, website_url: Optional[str] = None
    ) -> Optional[DiscoveredFeed]:
        """Try to parse a URL as an RSS/Atom feed."""
        try:
            feed: FeedParserDict = feedparser.parse(url)

            # Check if it's a valid feed
            if not feed.entries and not feed.feed.get("title"):
                return None

            # Check for bozo (malformed feed) without any entries
            if feed.bozo and not feed.entries:
                return None

            title = feed.feed.get("title", "")
            if not title:
                # Try to extract from URL
                parsed_url = urlparse(url)
                title = parsed_url.netloc

            # Get description
            description = feed.feed.get("subtitle") or feed.feed.get("description")

            # Determine the website URL
            site_url = website_url or feed.feed.get("link") or self._get_base_url(url)

            return DiscoveredFeed(
                name=str(title),
                url=str(site_url),
                rss_url=url,
                description=str(description) if description else None,
            )
        except Exception as e:
            logger.debug(f"Failed to parse feed from {url}: {e}")
            return None

    def _find_feed_links(self, html_content: str, base_url: str) -> list[str]:
        """Find RSS/Atom feed links in HTML content."""
        feed_urls: list[str] = []

        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Look for <link> tags with RSS/Atom types
            feed_types = [
                "application/rss+xml",
                "application/atom+xml",
                "application/feed+json",
                "application/xml",
                "text/xml",
            ]

            for link in soup.find_all("link", rel=["alternate", "feed"]):
                link_type_attr = link.get("type")
                link_type = str(link_type_attr).lower() if link_type_attr else ""
                href_attr = link.get("href")
                href = str(href_attr) if href_attr else None

                if href and any(ft in link_type for ft in feed_types):
                    # Convert relative URL to absolute
                    absolute_url = urljoin(base_url, href)
                    feed_urls.append(absolute_url)

            # Also look for <a> tags that might link to feeds
            for anchor in soup.find_all("a", href=True):
                href_attr = anchor.get("href")
                href = str(href_attr) if href_attr else ""
                href_lower = href.lower()
                if any(
                    pattern in href_lower
                    for pattern in ["/feed", "/rss", ".xml", "atom"]
                ):
                    absolute_url = urljoin(base_url, href)
                    if absolute_url not in feed_urls:
                        feed_urls.append(absolute_url)

        except Exception as e:
            logger.warning(f"Error parsing HTML for feed links: {e}")

        return feed_urls

    def _get_base_url(self, url: str) -> str:
        """Get the base URL (scheme + netloc) from a URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"


# Singleton instance for convenience
feed_discovery_service = FeedDiscoveryService()
