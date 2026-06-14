"""PPE.pl-specific content parser."""

import logging
from typing import Optional

from bs4 import BeautifulSoup, Tag

from .base import BaseDomainParser
from .video import VideoEmbedParser

logger = logging.getLogger(__name__)


class PPEParser(BaseDomainParser):
    """Parser for PPE.pl article pages.

    Extracts news, journalism, review, and guide bodies while removing:
    - Site chrome and article metadata
    - Ad placeholders and sponsored product widgets
    - Recommendation blocks, sharing controls, and comments
    """

    domains: list[str] = [
        "ppe.pl",
        "*.ppe.pl",
    ]

    CONTENT_SELECTORS: list[str] = [
        "article.news-section div.content.news",
        ".review-content > div.content.review",
        ".review-content > div.content.journalism",
        ".guide-content.text-content",
        "div.content.news",
        "div.content.review",
        "div.content.journalism",
        "div.content.guide",
        "article .content",
        "main article",
    ]

    REMOVE_SELECTORS: list[str] = [
        # Generic page chrome and scripts
        "header",
        "nav",
        "footer",
        "script",
        "style",
        "noscript",
        "svg",
        "form",
        "button",
        "[role='banner']",
        "[role='navigation']",
        "[role='contentinfo']",
        # Article header/metadata when a fallback container is used
        ".news-top-wrapper",
        ".news-image-bottom",
        ".review-img",
        ".review-author",
        ".labels-and-title-wrapper",
        ".article-labels",
        ".labels",
        ".label",
        ".battery",
        ".tag",
        ".tags",
        ".review-tags",
        # PPE ad slots and sponsored widgets
        ".banner-parent-screening",
        ".banner-placeholder-screening",
        ".banner-placeholder",
        ".banner-max-width",
        ".onnetwork",
        ".banner-optad-player",
        ".optad360-player",
        ".content-array__media-expert",
        ".media-expert-card",
        ".samsung-badge",
        ".samsung-badge-above-image",
        ".samsung-badge-above-video",
        ".samsung-url",
        ".single-gallery",
        ".resize-icon",
        ".resize-icon__icon",
        "[id^='div-gpt-ad-']",
        "[id^='article-']",
        "img[src*='resize-icon']",
        "img[src*='doubleclick.net']",
        "a[href*='doubleclick.net']",
        # Recommendations, guide navigation, sharing, comments
        ".news-additional-wrapper",
        ".additional-content",
        ".table-of-contents",
        ".sub-guide-nav",
        ".share-btns",
        ".share-wiget-wrapper",
        ".share-widget-wrapper",
        ".content__source",
        ".guide-content__source",
        "#comments-box",
        ".comments-wrapper",
        "#comment-input-area",
        ".comment-input-wrapper",
    ]

    BOILERPLATE_TEXT_MARKERS: list[str] = [
        "dalsza część tekstu pod wideo",
        "wybrane okazje dla ciebie",
        "najniższa cena",
    ]

    BOILERPLATE_EXACT_TEXT: set[str] = {"kup teraz", "reklama"}

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract article content from a PPE.pl page."""
        try:
            soup = self._create_soup(html_content)

            content = None
            for selector in self.CONTENT_SELECTORS:
                content = soup.select_one(selector)
                if content and len(content.get_text(strip=True)) > 100:
                    break
                content = None

            if not content:
                logger.debug("PPE parser: Could not find main content")
                return None

            article_soup = self._create_soup(str(content))
            self._remove_elements(article_soup, self.REMOVE_SELECTORS)
            self._remove_boilerplate_text(article_soup)
            self._normalize_lazy_media(article_soup)
            self._filter_iframes(article_soup)
            self._remove_noise_attributes(article_soup)
            self._remove_empty_ppe_elements(article_soup)

            text_content = article_soup.get_text(strip=True)
            if len(text_content) < 100:
                logger.debug(
                    f"PPE parser: Content too short ({len(text_content)} chars)"
                )
                return None

            return str(article_soup).strip()

        except Exception as e:
            logger.debug(f"PPE parser failed: {e}")
            return None

    def _normalize_lazy_media(self, soup: BeautifulSoup) -> None:
        """Promote PPE lazy-media attributes to regular browser-readable URLs."""
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue

            src = img.get("src")
            if not isinstance(src, str) or not src or src.startswith("data:"):
                lazy_src = img.get("data-src")
                if isinstance(lazy_src, str) and lazy_src:
                    img["src"] = lazy_src

        for source in soup.find_all("source"):
            if not isinstance(source, Tag):
                continue

            lazy_srcset = source.get("data-srcset")
            if isinstance(lazy_srcset, str) and lazy_srcset:
                source["srcset"] = lazy_srcset

            lazy_sizes = source.get("data-sizes")
            if isinstance(lazy_sizes, str) and lazy_sizes:
                source["sizes"] = lazy_sizes

    def _filter_iframes(self, soup: BeautifulSoup) -> None:
        """Keep trusted video embeds and remove ad/tracking iframes."""
        for iframe in soup.find_all("iframe"):
            if not isinstance(iframe, Tag):
                continue

            src = iframe.get("src", "")
            if isinstance(src, str) and VideoEmbedParser.is_trusted_video_embed(src):
                iframe["frameborder"] = "0"
                iframe["allowfullscreen"] = ""
                continue

            iframe.decompose()

    def _remove_boilerplate_text(self, soup: BeautifulSoup) -> None:
        """Remove short PPE ad/source labels that survive selector cleanup."""
        for element in soup.find_all(["aside", "div", "p", "section", "span"]):
            if not isinstance(element, Tag):
                continue

            text = " ".join(element.get_text(" ", strip=True).lower().split())
            if not text or len(text) > 700:
                continue

            if (
                text in self.BOILERPLATE_EXACT_TEXT
                or text.startswith("źródło:")
                or any(marker in text for marker in self.BOILERPLATE_TEXT_MARKERS)
            ):
                element.decompose()

    def _remove_noise_attributes(self, soup: BeautifulSoup) -> None:
        """Remove PPE app metadata attributes from extracted content."""
        for element in soup.find_all(True):
            if not isinstance(element, Tag):
                continue

            attrs_to_remove = [
                attr
                for attr in element.attrs
                if attr.startswith("data-")
                or attr in {"style", "onclick", "id"}
            ]
            for attr in attrs_to_remove:
                del element.attrs[attr]

    def _remove_empty_ppe_elements(self, soup: BeautifulSoup) -> None:
        """Remove empty wrappers while preserving media and tables."""
        preserve_tags = {
            "br",
            "hr",
            "img",
            "picture",
            "source",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            "iframe",
            "video",
            "audio",
        }

        for element in soup.find_all():
            if not isinstance(element, Tag) or element.name in preserve_tags:
                continue

            has_media = (
                element.find("img")
                or element.find("picture")
                or element.find("iframe")
                or element.find("video")
            )
            if not element.get_text(strip=True) and not has_media:
                element.decompose()
