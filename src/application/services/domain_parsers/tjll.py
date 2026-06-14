"""blog.tjll.net-specific content parser."""

import logging
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class TJLLBlogParser(BaseDomainParser):
    """Parser for Tyblog article pages on blog.tjll.net.

    The site renders full posts in ``main.post section#content`` and appends
    prev/next links plus Discourse embed chrome to the same section.
    """

    domains: list[str] = ["blog.tjll.net"]

    CONTENT_SELECTORS: list[str] = [
        "main.container.post section#content",
        "main.post section#content",
        "main.post #content",
    ]

    REMOVE_SELECTORS: list[str] = [
        "script",
        "style",
        "noscript",
        "#page-nav",
        "#discourse-comments",
        ".org-src-tab",
        ".org-src-legend",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract article content from a blog.tjll.net page."""
        try:
            soup = self._create_soup(html_content)

            content = self._find_content(soup)
            if not content:
                logger.debug("TJLL parser: Could not find main content")
                return None

            article_soup = self._create_soup(str(content))
            self._normalize_article_headings(article_soup)
            self._normalize_code_blocks(article_soup)
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)
            self._remove_trailing_rules(article_soup)
            self._remove_empty_tjll_elements(article_soup)

            text_content = article_soup.get_text(strip=True)
            if len(text_content) < 100:
                logger.debug(
                    f"TJLL parser: Content too short ({len(text_content)} chars)"
                )
                return None

            return str(article_soup).strip()

        except Exception as e:
            logger.debug(f"TJLL parser failed: {e}")
            return None

    def _find_content(self, soup: BeautifulSoup) -> BeautifulSoup | Tag | None:
        """Find full-page content or accept RSS description fragments."""
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 100:
                return content

        if self._looks_like_rss_content_fragment(soup):
            return soup

        return None

    def _looks_like_rss_content_fragment(self, soup: BeautifulSoup) -> bool:
        """Return whether the parsed HTML looks like Tyblog RSS content."""
        if soup.find(["html", "body", "main", "header", "nav", "footer"]):
            return False

        if len(soup.get_text(strip=True)) <= 100:
            return False

        return bool(soup.find(["p", "pre", "blockquote", "ul", "ol"]))

    def _normalize_article_headings(self, soup: BeautifulSoup) -> None:
        """Promote org-mode body headings to reader-friendly heading levels."""
        heading_map = {
            "h4": "h2",
            "h5": "h3",
            "h6": "h4",
        }
        for heading in soup.find_all(list(heading_map)):
            if not isinstance(heading, Tag):
                continue
            heading.name = heading_map[str(heading.name)]

    def _normalize_code_blocks(self, soup: BeautifulSoup) -> None:
        """Convert org-mode source blocks into plain Feedy code blocks."""
        for container in list(soup.select(".org-src-container")):
            if not isinstance(container, Tag):
                continue

            language_label = self._extract_previous_code_label(container)
            for pre in container.find_all("pre"):
                if isinstance(pre, Tag):
                    self._set_code_language(pre, language_label)
            container.unwrap()

        for pre in soup.find_all("pre"):
            if not isinstance(pre, Tag):
                continue

            self._normalize_pre_content(soup, pre)
            self._remove_org_pre_classes(pre)

    def _extract_previous_code_label(self, container: Tag) -> Optional[str]:
        """Remove and return the org-mode language label before a code block."""
        sibling = container.previous_sibling
        while sibling is not None:
            previous_sibling = sibling.previous_sibling

            if isinstance(sibling, NavigableString):
                if sibling.strip():
                    return None
            elif isinstance(sibling, Tag):
                classes = sibling.get("class")
                class_names = (
                    [str(class_name) for class_name in classes]
                    if isinstance(classes, list)
                    else []
                )
                if "org-src-tab" in class_names:
                    text = sibling.get_text(" ", strip=True)
                    sibling.decompose()
                    return text
                if "org-src-legend" in class_names:
                    sibling.decompose()
                else:
                    return None

            sibling = previous_sibling

        return None

    def _set_code_language(
        self,
        pre: Tag,
        language_label: Optional[str],
    ) -> None:
        """Store the source block language as metadata, not article text."""
        language = self._language_from_pre_class(pre)
        if not language and language_label:
            language = self._clean_language_label(language_label)

        if language:
            pre["data-language"] = language

    def _language_from_pre_class(self, pre: Tag) -> Optional[str]:
        """Read org-mode source language from classes like ``src-systemd``."""
        classes = pre.get("class")
        if not isinstance(classes, list):
            return None

        for class_name in classes:
            class_text = str(class_name)
            if class_text == "src" or not class_text.startswith("src-"):
                continue

            language = class_text.removeprefix("src-")
            return language.removesuffix("-ts")

        return None

    def _clean_language_label(self, language_label: str) -> str:
        """Normalize a source block label for use as an HTML attribute."""
        text = " ".join(language_label.lower().split())
        return "".join(
            char if char.isalnum() else "-"
            for char in text
        ).strip("-")

    def _normalize_pre_content(self, soup: BeautifulSoup, pre: Tag) -> None:
        """Flatten org-mode nested code/span markup into one code element."""
        code_text = pre.get_text("", strip=False).strip("\n")
        code = soup.new_tag("code")
        code.string = code_text

        pre.clear()
        pre.append(code)

    def _remove_org_pre_classes(self, pre: Tag) -> None:
        """Remove org-mode source classes after preserving language metadata."""
        classes = pre.get("class")
        if not isinstance(classes, list):
            return

        cleaned_classes = [
            str(class_name)
            for class_name in classes
            if str(class_name) != "src" and not str(class_name).startswith("src-")
        ]
        if cleaned_classes:
            pre["class"] = cleaned_classes
        elif "class" in pre.attrs:
            del pre.attrs["class"]

    def _remove_trailing_rules(self, soup: BeautifulSoup) -> None:
        """Remove separator lines left behind after stripping footer chrome."""
        for rule in list(soup.find_all("hr")):
            if not isinstance(rule, Tag):
                continue
            if not self._has_meaningful_following_sibling(rule):
                rule.decompose()

    def _has_meaningful_following_sibling(self, element: Tag) -> bool:
        """Return whether an element has non-separator content after it."""
        sibling = element.next_sibling
        while sibling is not None:
            if isinstance(sibling, NavigableString):
                if sibling.strip():
                    return True
            elif isinstance(sibling, Tag) and sibling.name != "hr":
                return True
            sibling = sibling.next_sibling
        return False

    def _remove_empty_tjll_elements(self, soup: BeautifulSoup) -> None:
        """Remove empty wrappers while preserving article media and code blocks."""
        preserve_tags = {
            "br",
            "hr",
            "img",
            "pre",
            "code",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            "iframe",
            "video",
            "audio",
            "source",
        }

        for element in soup.find_all():
            if not isinstance(element, Tag) or element.name in preserve_tags:
                continue

            has_media = (
                element.find("img")
                or element.find("iframe")
                or element.find("video")
                or element.find("audio")
            )
            if not element.get_text(strip=True) and not has_media:
                element.decompose()
