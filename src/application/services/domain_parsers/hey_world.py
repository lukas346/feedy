"""HEY World blog content parser."""

import logging
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import NavigableString

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class HeyWorldParser(BaseDomainParser):
    """Parser for HEY World blogs (world.hey.com).

    Extracts article content while removing:
    - Navigation and header
    - Author bio section
    - Subscription forms
    - Footer/attribution
    - RSS feed links
    """

    domains: list[str] = [
        "world.hey.com",
    ]

    # Elements to remove from HEY World pages
    REMOVE_SELECTORS: list[str] = [
        # Navigation and header
        "header",
        "nav",
        "[role='banner']",
        "[role='navigation']",
        # Author bio section (usually starts with "About [Author Name]")
        ".author-bio",
        ".about-author",
        "[class*='author']",
        "[class*='bio']",
        # Subscription forms
        "form",
        "[class*='subscribe']",
        "[class*='subscription']",
        "[class*='newsletter']",
        # Footer elements
        "footer",
        "[role='contentinfo']",
        "[class*='footer']",
        # HEY-specific attribution
        "a[href*='hey.com/world']",
        # RSS/feed links
        "a[href*='/feed']",
        "[class*='feed']",
        # Social sharing
        "[class*='share']",
        "[class*='social']",
        # Avatar/profile images in header
        ".avatar",
        "[class*='avatar']",
        # Misc UI elements
        "script",
        "style",
        "noscript",
    ]

    # Content selectors in order of preference
    CONTENT_SELECTORS: list[str] = [
        # HEY World Trix editor content (for RSS fragments)
        ".trix-content",
        # Semantic article element (for full page)
        "article",
        "main article",
        # Common content areas
        "[role='main']",
        "main",
        ".post",
        ".post-content",
        ".entry-content",
        ".content",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract article content from HEY World."""
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
                logger.debug("HEY World parser: Could not find main content")
                return None

            # Create new soup from content
            article_soup = self._create_soup(str(content))

            # Remove unwanted elements
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)

            # Convert Trix editor div structure to semantic paragraphs
            # HEY World uses: <div class="trix-content"><div>para</div>...</div>
            trix_content = article_soup.select_one(".trix-content")
            if trix_content:
                for div in trix_content.find_all("div", recursive=False):
                    # Skip if div only contains whitespace or br
                    if not div.get_text(strip=True):
                        div.decompose()
                        continue
                    # Convert div to p tag
                    div.name = "p"
                    # Remove leading br tags
                    for child in list(div.children):
                        if getattr(child, "name", None) == "br":
                            child.decompose()
                        elif isinstance(child, str) and not child.strip():
                            continue
                        else:
                            break

            # Remove elements containing "Subscribe" or "About" author text
            for element in article_soup.find_all(["div", "section", "aside", "p"]):
                text = element.get_text(strip=True).lower()
                # Remove subscription prompts
                if "subscribe" in text and "email" in text:
                    element.decompose()
                    continue
                # Remove author bio sections (typically start with "About")
                if text.startswith("about ") and len(text) > 200:
                    element.decompose()
                    continue

            # Remove "Sent to the world with HEY" footer text
            for text_node in article_soup.find_all(string=True):
                if "sent to the world" in str(text_node).lower():
                    parent = text_node.parent
                    if parent and hasattr(parent, "decompose"):
                        parent.decompose()

            # Remove data attributes
            for element in article_soup.find_all(True):
                attrs_to_remove = [
                    attr for attr in element.attrs if attr.startswith("data-")
                ]
                for attr in attrs_to_remove:
                    del element.attrs[attr]

            # Collapse multiple consecutive <br> tags into one
            self._collapse_consecutive_br_tags(article_soup)

            # Clean up empty elements
            self._remove_empty_elements(article_soup)

            result = str(article_soup).strip()

            # Basic validation
            text_content = article_soup.get_text(strip=True)
            if len(text_content) < 100:
                logger.debug(
                    f"HEY World parser: Content too short ({len(text_content)} chars)"
                )
                return None

            return result

        except Exception as e:
            logger.debug(f"HEY World parser failed: {e}")
            return None

    def _collapse_consecutive_br_tags(self, soup: BeautifulSoup) -> None:
        """Collapse multiple consecutive <br> tags into a single one."""
        br_tags = soup.find_all("br")
        for br in br_tags:
            # Check if this br was already removed
            if br.parent is None:
                continue

            # Look at next siblings and remove consecutive br tags
            sibling = br.next_sibling
            while sibling is not None:
                next_sibling = sibling.next_sibling
                # Skip whitespace-only text nodes
                if isinstance(sibling, NavigableString):
                    if not sibling.strip():
                        sibling = next_sibling
                        continue
                    else:
                        break
                # Remove consecutive br tags
                if getattr(sibling, "name", None) == "br":
                    sibling.decompose()
                    sibling = next_sibling
                else:
                    break
