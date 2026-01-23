"""Sean Goedecke blog content parser."""

import logging
from typing import Optional

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class SeanGoedeckeParser(BaseDomainParser):
    """Parser for seangoedecke.com blog.

    Extracts article content while removing:
    - Site header and navigation
    - Post metadata (date, tags)
    - Subscribe/share prompts
    - Related post previews
    - Search form
    - Footer navigation
    """

    domains: list[str] = [
        "seangoedecke.com",
        "www.seangoedecke.com",
    ]

    # Elements to remove from pages
    REMOVE_SELECTORS: list[str] = [
        # Site header with navigation
        "header",
        "nav",
        # Post metadata (date, tags line)
        ".post-meta",
        # Footer navigation links
        "article > footer",
        "footer",
        # Search form
        ".search-container",
        "form.site-search",
        # Subscribe/share prompts (paragraph after article content)
        # Scripts and styles
        "script",
        "style",
        "noscript",
        # Gatsby announcer
        "#gatsby-announcer",
    ]

    # Content selectors in order of preference
    CONTENT_SELECTORS: list[str] = [
        # Article section contains main content
        "article section",
        "article",
        "main article",
        "main",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract article content from seangoedecke.com."""
        try:
            soup = self._create_soup(html_content)

            # Find main content using selectors
            content = None
            for selector in self.CONTENT_SELECTORS:
                content = soup.select_one(selector)
                if content and len(content.get_text(strip=True)) > 100:
                    break
                content = None

            if not content:
                logger.debug("SeanGoedecke parser: Could not find content")
                return None

            # Create new soup from content
            article_soup = self._create_soup(str(content))

            # Remove unwanted elements
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)

            # Remove subscribe/share prompt paragraphs
            # These contain "subscribe" or "sharing it on Hacker News"
            for p in article_soup.find_all("p"):
                text = p.get_text(strip=True).lower()
                if "if you liked this post" in text and "subscrib" in text:
                    p.decompose()
                    continue
                if "sharing it on hacker news" in text:
                    p.decompose()
                    continue

            # Remove related post blockquotes (previews of other posts)
            for blockquote in article_soup.find_all("blockquote"):
                # Check if it contains "Continue reading..." link
                has_continue_link = any(
                    "continue reading" in (a.get_text(strip=True).lower())
                    for a in blockquote.find_all("a")
                )
                if has_continue_link:
                    blockquote.decompose()
                    continue
                # Check for preview header "Here's a preview of a related post"
                prev = blockquote.find_previous_sibling()
                if prev:
                    prev_text = prev.get_text(strip=True).lower()
                    if "preview of a related post" in prev_text:
                        prev.decompose()
                        blockquote.decompose()

            # Remove horizontal rules before footer
            for hr in article_soup.find_all("hr"):
                # If hr is followed only by footer-like content, remove it
                next_elem = hr.find_next_sibling()
                if next_elem and next_elem.name == "footer":
                    hr.decompose()

            # Remove data attributes
            for element in article_soup.find_all(True):
                attrs_to_remove = [
                    attr for attr in element.attrs if attr.startswith("data-")
                ]
                for attr in attrs_to_remove:
                    del element.attrs[attr]

            # Clean up empty elements
            self._remove_empty_elements(article_soup)

            result = str(article_soup).strip()

            # Basic validation
            text_content = article_soup.get_text(strip=True)
            if len(text_content) < 100:
                char_count = len(text_content)
                logger.debug(f"SeanGoedecke parser: Too short ({char_count})")
                return None

            return result

        except Exception as e:
            logger.debug(f"SeanGoedecke parser failed: {e}")
            return None
