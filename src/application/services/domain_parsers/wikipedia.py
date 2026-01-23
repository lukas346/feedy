"""Wikipedia-specific content parser."""

import logging
from typing import Optional

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class WikipediaParser(BaseDomainParser):
    """Parser for Wikipedia articles.

    Extracts main article content while removing:
    - Navigation and meta elements
    - Infoboxes (all)
    - References section
    - Table of contents
    - Edit links
    - Categories
    """

    domains: list[str] = ["*.wikipedia.org"]

    # Elements to remove from Wikipedia pages
    REMOVE_SELECTORS: list[str] = [
        # Navigation and meta elements
        "#mw-navigation",
        "#mw-head",
        "#mw-head-base",
        "#mw-panel",
        "#mw-panel-toc",
        "#footer",
        "#siteSub",
        "#contentSub",
        "#jump-to-nav",
        ".mw-jump-link",
        ".mw-editsection",
        ".noprint",
        ".metadata",
        # Infoboxes (user preference: remove all)
        ".infobox",
        ".infobox_v2",
        ".infobox-3cols",
        ".sidebar",
        ".vertical-navbox",
        ".wikitable.infobox",
        # Navigation boxes
        ".navbox",
        ".navbox-styles",
        ".navbox-title",
        ".sistersitebox",
        ".portal",
        ".portal-bar",
        # Table of contents
        "#toc",
        ".toc",
        ".mw-parser-output > .toclimit-2",
        ".mw-parser-output > .toclimit-3",
        # References (user preference: remove)
        ".reflist",
        ".references",
        ".reference",
        "#References",
        ".mw-references-wrap",
        'ol[class*="references"]',
        # External links section often noisy
        "#External_links",
        ".external-links",
        # Notices and banners
        ".hatnote",
        ".dmbox",
        ".ambox",
        ".tmbox",
        ".mbox-small",
        ".ombox",
        ".cmbox",
        ".fmbox",
        ".imbox",
        # Categories
        "#catlinks",
        ".catlinks",
        # Coordinates
        "#coordinates",
        ".geo-default",
        ".geo-dms",
        # Other meta
        ".mw-empty-elt",
        ".mw-indicators",
        "#siteNotice",
        "#centralNotice",
        ".mw-cite-backlink",
        # Audio/pronunciation guides often clutter
        ".IPA",
        ".nowrap",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract main article content from Wikipedia."""
        try:
            soup = self._create_soup(html_content)

            # Find main content div
            content = soup.select_one("#mw-content-text .mw-parser-output")
            if not content:
                content = soup.select_one("#bodyContent")
            if not content:
                content = soup.select_one("#content")
            if not content:
                logger.debug("Wikipedia parser: Could not find main content")
                return None

            # Create new soup from content
            article_soup = self._create_soup(str(content))

            # Remove unwanted elements
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)

            # Remove reference superscripts [1], [2], etc.
            for sup in article_soup.select("sup.reference"):
                sup.decompose()

            # Remove span elements that are just anchors
            for span in article_soup.select("span.mw-headline"):
                # Keep the text but remove the span wrapper
                span.unwrap()

            # Clean up empty elements
            self._remove_empty_elements(article_soup)

            result = str(article_soup).strip()

            # Basic validation - ensure we have meaningful content
            text_content = article_soup.get_text(strip=True)
            if len(text_content) < 100:
                logger.debug(
                    f"Wikipedia parser: Content too short ({len(text_content)} chars)"
                )
                return None

            return result

        except Exception as e:
            logger.debug(f"Wikipedia parser failed: {e}")
            return None
