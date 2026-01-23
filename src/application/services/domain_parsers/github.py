"""GitHub-specific content parser."""

import logging
from typing import Optional

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class GitHubParser(BaseDomainParser):
    """Parser for GitHub README and wiki pages.

    Extracts rendered markdown content while removing:
    - Repository header/stats
    - File browser
    - Sidebar
    - Footer
    - Navigation elements
    """

    domains: list[str] = ["github.com"]

    # Elements to remove from GitHub pages
    REMOVE_SELECTORS: list[str] = [
        # Header and navigation
        "header",
        ".Header",
        ".js-header-wrapper",
        ".gh-header",
        ".pagehead",
        ".repohead",
        # Repository stats/info
        ".repository-content > .d-flex",
        ".file-navigation",
        ".commit-tease",
        ".commit-tease-sha",
        ".Box-header",
        # File browser
        ".js-repo-nav",
        ".UnderlineNav",
        ".file-wrap",
        'nav[aria-label="Repository"]',
        'nav[aria-label="File Tree"]',
        ".react-directory-filename-column",
        # Sidebar
        ".Layout-sidebar",
        ".repository-topics",
        ".BorderGrid-cell",
        'aside[aria-label="Repository sidebar"]',
        ".sidebar-readme",
        # Footer
        "footer",
        ".footer",
        ".site-footer",
        # Social/interaction elements
        ".social-count",
        ".starring-container",
        ".watching-container",
        ".fork-button",
        ".btn-with-count",
        # Repo actions
        ".file-actions",
        ".BtnGroup",
        ".pagehead-actions",
        # Breadcrumbs and paths
        ".breadcrumb",
        ".js-path-segment",
        # Code view elements (we want README, not code viewer)
        ".blob-code-inner",
        ".blob-num",
        ".js-file-line",
        # Misc UI elements
        ".flash",
        ".flash-warn",
        ".flash-error",
        "#js-flash-container",
        ".js-notice",
        ".protip",
        ".octicon",
        # Contributors/releases panels
        ".Layout-main > div:first-child > div:first-child",
        'h2:contains("Contributors")',
        'h2:contains("Languages")',
        'h2:contains("Releases")',
        # Edit buttons
        'button[aria-label="Edit file"]',
        'button[aria-label="Edit README"]',
        ".js-toggle-hidden-gist-draft",
    ]

    # Content selectors in order of preference
    CONTENT_SELECTORS: list[str] = [
        # README content
        "article.markdown-body",
        ".markdown-body",
        "#readme .markdown-body",
        ".Box-body .markdown-body",
        # Wiki content
        "#wiki-body",
        ".wiki-body",
        ".wiki-content",
        # Gist content
        ".gist-content",
        ".js-gist-file-update-container .markdown-body",
        # Generic content areas
        ".repository-content article",
        "#repo-content-pjax-container article",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract README/wiki content from GitHub."""
        try:
            soup = self._create_soup(html_content)

            # Find main content using selectors
            content = None
            for selector in self.CONTENT_SELECTORS:
                content = soup.select_one(selector)
                if content and len(content.get_text(strip=True)) > 50:
                    break
                content = None

            if not content:
                logger.debug("GitHub parser: Could not find main content")
                return None

            # Create new soup from content
            article_soup = self._create_soup(str(content))

            # Remove unwanted elements
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)

            # Remove GitHub-specific anchor links in headings
            for anchor in article_soup.select("a.anchor"):
                anchor.decompose()

            # Remove heading links that wrap the heading text
            for heading in article_soup.select("h1, h2, h3, h4, h5, h6"):
                # Find anchor links that contain heading text
                for anchor in heading.select("a.heading-link"):
                    anchor.unwrap()

            # Clean up empty elements
            self._remove_empty_elements(article_soup)

            result = str(article_soup).strip()

            # Basic validation
            text_content = article_soup.get_text(strip=True)
            if len(text_content) < 50:
                logger.debug(
                    f"GitHub parser: Content too short ({len(text_content)} chars)"
                )
                return None

            return result

        except Exception as e:
            logger.debug(f"GitHub parser failed: {e}")
            return None
