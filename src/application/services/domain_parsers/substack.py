"""Substack-specific content parser."""

import logging
from typing import Optional

from bs4 import BeautifulSoup

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class SubstackParser(BaseDomainParser):
    """Parser for Substack article pages.

    Extracts the post body while removing:
    - Site chrome and post metadata
    - Subscription widgets and paywall prompts
    - Comments, sharing, and reaction controls
    - Footer/navigation content
    """

    domains: list[str] = [
        "substack.com",
        "*.substack.com",
    ]

    REMOVE_SELECTORS: list[str] = [
        # Site chrome
        "header",
        "nav",
        "footer",
        "script",
        "style",
        "noscript",
        "[role='banner']",
        "[role='navigation']",
        "[role='contentinfo']",
        # Post title/metadata when falling back to a full article container
        ".post-header",
        ".post-meta",
        ".post-footer",
        ".byline",
        ".subtitle",
        ".pencraft",
        # Subscription and paid-content prompts
        "form",
        ".subscription-widget-wrap",
        ".subscription-widget",
        ".subscribe-widget",
        ".signup-widget",
        ".paywall",
        "[class*='subscribe']",
        "[class*='subscription']",
        "[class*='signup']",
        "[class*='paywall']",
        "[data-testid*='subscribe']",
        "[data-testid*='subscription']",
        "[data-testid*='paywall']",
        # Engagement chrome
        ".comments",
        ".comment-section",
        ".reaction-bar",
        ".share-dialog",
        ".share-button",
        "[class*='comment']",
        "[class*='reaction']",
        "[class*='share']",
        # Misc Substack app chrome
        ".footer-wrap",
        ".post-ufi",
        ".reader2-post-footer",
        ".recommendations",
        ".related-posts",
    ]

    CONTENT_SELECTORS: list[str] = [
        # Common Substack article body containers
        ".body.markup",
        "article .body.markup",
        ".available-content .body.markup",
        "[data-testid='post-content']",
        ".post-content",
        ".available-content",
        # Fallbacks for older or server-rendered pages
        "article.post",
        "article",
        "main article",
        "main",
    ]

    BOILERPLATE_TEXT_MARKERS: list[str] = [
        "subscribe to continue reading",
        "subscribe to receive new posts",
        "subscribe now",
        "thanks for reading",
        "this post is public so feel free to share it",
        "share it with anyone",
        "leave a comment",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract article content from a Substack page."""
        try:
            soup = self._create_soup(html_content)

            content = None
            for selector in self.CONTENT_SELECTORS:
                content = soup.select_one(selector)
                if content and len(content.get_text(strip=True)) > 100:
                    break
                content = None

            if not content:
                logger.debug("Substack parser: Could not find main content")
                return None

            article_soup = self._create_soup(str(content))
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)
            self._remove_boilerplate_text(article_soup)
            self._remove_noise_attributes(article_soup)
            self._remove_empty_elements(article_soup)

            text_content = article_soup.get_text(strip=True)
            if len(text_content) < 100:
                logger.debug(
                    f"Substack parser: Content too short ({len(text_content)} chars)"
                )
                return None

            return str(article_soup).strip()

        except Exception as e:
            logger.debug(f"Substack parser failed: {e}")
            return None

    def _remove_boilerplate_text(self, soup: BeautifulSoup) -> None:
        """Remove short text blocks that Substack injects around posts."""
        for element in soup.find_all(["aside", "div", "p", "section"]):
            if len(element.find_all("p")) > 1:
                continue
            text = " ".join(element.get_text(" ", strip=True).lower().split())
            if not text or len(text) > 500:
                continue
            if any(marker in text for marker in self.BOILERPLATE_TEXT_MARKERS):
                element.decompose()

    def _remove_noise_attributes(self, soup: BeautifulSoup) -> None:
        """Remove Substack app metadata attributes from extracted content."""
        for element in soup.find_all(True):
            attrs_to_remove = [
                attr
                for attr in element.attrs
                if attr.startswith("data-") or attr in {"style", "onclick"}
            ]
            for attr in attrs_to_remove:
                del element.attrs[attr]
