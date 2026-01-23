"""Antirez blog content parser."""

import logging
from typing import Optional

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class AntirezParser(BaseDomainParser):
    """Parser for antirez.com blog.

    Extracts article content while removing:
    - Site header and navigation
    - Author metadata (username, date, views)
    - Disqus comments section
    - Footer links
    """

    domains: list[str] = [
        "antirez.com",
        "www.antirez.com",
    ]

    # Elements to remove from pages
    REMOVE_SELECTORS: list[str] = [
        # Site header
        "header",
        # Author/date info
        "span.info",
        # Disqus comments
        "#disqus_thread",
        "#disqus_thread_outdiv",
        ".dsq-brlink",
        # Footer
        "footer",
        # Scripts and styles
        "script",
        "style",
        "noscript",
    ]

    # Content selectors in order of preference
    CONTENT_SELECTORS: list[str] = [
        # Main article comment contains the post content
        "topcomment article.comment",
        "topcomment",
        "article.comment",
        "#content",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract article content from antirez.com."""
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
                logger.debug("Antirez parser: Could not find content")
                return None

            # Create new soup from content
            article_soup = self._create_soup(str(content))

            # Remove unwanted elements
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)

            # Convert pre tags to paragraphs for better rendering
            # antirez.com uses <pre> for article text (plain text format)
            for pre in article_soup.find_all("pre"):
                text = pre.get_text()
                if not text.strip():
                    pre.decompose()
                    continue

                # Split by double newlines to create paragraphs
                paragraphs = text.split("\n\n")
                new_content = []
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        # Create a p tag for each paragraph
                        p_tag = article_soup.new_tag("p")
                        p_tag.string = para
                        new_content.append(p_tag)

                # Replace pre with paragraphs
                if new_content:
                    for p_tag in new_content:
                        pre.insert_before(p_tag)
                pre.decompose()

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
                logger.debug(f"Antirez parser: Too short ({char_count})")
                return None

            return result

        except Exception as e:
            logger.debug(f"Antirez parser failed: {e}")
            return None
