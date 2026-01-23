"""Medium-specific content parser."""

import logging
from typing import Optional

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class MediumParser(BaseDomainParser):
    """Parser for Medium articles.

    Extracts article content while removing:
    - Site header/navigation
    - Author bio/sidebar
    - Related articles
    - Comments section
    - Subscription prompts
    - Footer
    """

    domains: list[str] = [
        "medium.com",
        "*.medium.com",
    ]

    # Elements to remove from Medium pages
    REMOVE_SELECTORS: list[str] = [
        # Navigation and header
        "header",
        "nav",
        "[role='banner']",
        ".metabar",
        ".js-metabar",
        ".js-stickyFooter",
        # Author bio and profile sections
        ".pw-author-block",
        ".postMetaInline",
        ".js-postMetaLockup",
        "[data-testid='authorName']",
        ".followState",
        ".js-followState",
        ".profileCard",
        # Related articles and recommendations
        ".relatedPostsWrapper",
        ".js-relatedPosts",
        ".postRelatedTitle",
        "[data-testid='relatedPosts']",
        ".recommendedPosts",
        # Subscription/membership prompts
        ".js-membershipPrompt",
        ".js-subscriberWall",
        ".membershipUpsellModal",
        ".paywall",
        "[data-testid='membershipUpsell']",
        "[role='dialog']",
        ".overlay",
        ".modal",
        ".js-overlay",
        # Comments and responses
        ".responsesWrapper",
        ".js-responses",
        "[data-testid='responses']",
        ".postFooterSocialMenu",
        # Social sharing
        ".socialMeta",
        ".js-socialMeta",
        ".shareButtons",
        ".js-shareButtons",
        "[data-action='show-share']",
        # Clap/appreciation buttons
        ".js-multirecommendCount",
        ".clapButton",
        "[data-testid='clapButton']",
        ".js-postActions",
        # Footer
        "footer",
        ".footer",
        ".globalFooter",
        ".siteFooter",
        # Tags
        ".tags",
        ".js-postTags",
        "[data-testid='postTags']",
        # Misc UI elements
        ".progressiveMedia-noscript",
        ".js-postLeftRail",
        ".postLeftRail",
        ".bottomBanner",
        ".js-bottomBanner",
        # App promotion
        ".branch-journeys-top",
        "[data-testid='appPromo']",
        ".appBanner",
        # Highlighting menu
        ".highlightMenu",
        ".js-highlightMenu",
        # User menu/avatar
        ".userAvatar",
        ".avatar",
        # Post footer actions (bookmarks, etc.)
        ".postActionsFooter",
        ".js-postActionsFooter",
    ]

    # Content selectors in order of preference
    CONTENT_SELECTORS: list[str] = [
        # Modern Medium structure
        "article",
        "[data-testid='post']",
        # Older Medium structure
        ".postArticle-content",
        ".section-content",
        # Generic content areas
        "main article",
        ".post-content",
        ".entry-content",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract article content from Medium."""
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
                logger.debug("Medium parser: Could not find main content")
                return None

            # Create new soup from content
            article_soup = self._create_soup(str(content))

            # Remove unwanted elements
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)

            # Remove empty figure captions
            for figcaption in article_soup.select("figcaption"):
                if not figcaption.get_text(strip=True):
                    figcaption.decompose()

            # Remove data attributes that are just noise
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
                logger.debug(
                    f"Medium parser: Content too short ({len(text_content)} chars)"
                )
                return None

            return result

        except Exception as e:
            logger.debug(f"Medium parser failed: {e}")
            return None
