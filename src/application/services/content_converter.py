"""Content converter service for extracting clean HTML from web pages.

Uses multiple extraction strategies to maximize content recovery:
1. Trafilatura - Best for news articles
2. Readability (Mozilla algorithm) - Best for blog posts
3. Direct HTML extraction - Fallback with cleaning
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup, Tag
from readability import Document

from application.services.domain_parsers import domain_parser_registry
from application.services.domain_parsers.video import VideoEmbedParser
from application.services.domain_utils import extract_domain

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result from a single extraction attempt."""

    content: str
    source: str
    score: float
    has_images: bool = False
    has_code: bool = False


class ContentConverter:
    """Extracts clean, readable HTML from web pages.

    Uses multiple extraction strategies and picks the best result
    based on content quality scoring. Preserves images and code blocks.
    """

    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Lazy-load image attributes to check
    LAZY_IMG_ATTRS: list[str] = [
        "data-src",
        "data-lazy-src",
        "data-original",
        "data-srcset",
        "data-lazy",
        "data-url",
        "data-image",
        "loading-src",
    ]

    # Elements to remove for fallback extraction
    # Note: iframe is NOT in this list - we handle video iframes specially
    REMOVE_TAGS: list[str] = [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "noscript",
        "form",
        "button",
        "svg",
        "canvas",
    ]

    # Patterns for ad/non-content elements
    REMOVE_PATTERNS: list[str] = [
        "advertisement",
        "sidebar",
        "social-share",
        "newsletter",
        "subscribe",
        "cookie",
        "gdpr",
        "promo",
        "sponsor",
    ]

    def to_html(self, html_content: str, base_url: Optional[str] = None) -> str:
        """
        Extract clean HTML content using multiple strategies.

        Tries all extractors and returns the best result based on scoring.
        Preprocesses HTML to fix lazy-loaded images before extraction.

        Args:
            html_content: Raw HTML string to process
            base_url: Base URL for converting relative URLs to absolute

        Returns:
            Clean HTML string
        """
        if not html_content or not html_content.strip():
            return ""

        # Preprocess HTML to fix lazy-loaded images and relative URLs
        html_content = self._preprocess_html(html_content, base_url)

        # Try domain-specific parser first
        if base_url:
            domain = extract_domain(base_url)
            if domain:
                parser = domain_parser_registry.get_parser(domain)
                if parser:
                    domain_result = parser.extract(html_content, base_url)
                    if domain_result:
                        score = self._score_content(domain_result)
                        # If domain parser produces good content, use it
                        if score > 30:
                            logger.debug(f"Using domain parser for {domain}")
                            return str(domain_result)
                        # Otherwise fall through to generic strategies

        results: list[ExtractionResult] = []

        # Strategy 1: Trafilatura (best for news)
        result = self._extract_with_trafilatura(html_content)
        if result:
            has_images = "<img" in result.lower()
            has_code = "<pre" in result.lower() or "<code" in result.lower()
            score = self._score_content(result, has_images, has_code)
            results.append(
                ExtractionResult(result, "trafilatura", score, has_images, has_code)
            )

        # Strategy 2: Readability (Mozilla algorithm)
        result = self._extract_with_readability(html_content)
        if result:
            has_images = "<img" in result.lower()
            has_code = "<pre" in result.lower() or "<code" in result.lower()
            score = self._score_content(result, has_images, has_code)
            results.append(
                ExtractionResult(result, "readability", score, has_images, has_code)
            )

        # Strategy 3: Direct HTML extraction fallback
        result = self._extract_with_cleaning(html_content)
        if result:
            has_images = "<img" in result.lower()
            has_code = "<pre" in result.lower() or "<code" in result.lower()
            score = self._score_content(result, has_images, has_code) * 0.9
            results.append(
                ExtractionResult(result, "direct", score, has_images, has_code)
            )

        if not results:
            return ""

        # Pick best result, preferring ones with images/code if original has them
        html_has_images = "<img" in html_content.lower()
        html_has_code = (
            "<pre" in html_content.lower() or "<code" in html_content.lower()
        )

        # Boost results that preserve images/code
        for r in results:
            if html_has_images and r.has_images:
                r.score *= 1.2
            if html_has_code and r.has_code:
                r.score *= 1.2

        best = max(results, key=lambda r: r.score)
        logger.debug(
            f"Best extractor: {best.source} "
            f"(score: {best.score:.1f}, img:{best.has_images}, code:{best.has_code})"
        )

        return best.content

    def _preprocess_html(
        self, html_content: str, base_url: Optional[str] = None
    ) -> str:
        """
        Preprocess HTML to fix common issues before extraction.

        - Converts lazy-loaded images to regular images
        - Converts relative URLs to absolute URLs
        - Preserves code blocks
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Fix lazy-loaded images
            for img in soup.find_all("img"):
                if not isinstance(img, Tag):
                    continue
                src = img.get("src", "")
                # Skip if already has valid src
                if (
                    isinstance(src, str)
                    and src
                    and not src.startswith("data:")
                    and "placeholder" not in src.lower()
                ):
                    continue

                # Try to find real image URL in lazy-load attributes
                for attr in self.LAZY_IMG_ATTRS:
                    lazy_src = img.get(attr)
                    if lazy_src and isinstance(lazy_src, str):
                        img["src"] = lazy_src
                        break

            # Fix noscript images (often contain non-lazy versions)
            for noscript in soup.find_all("noscript"):
                if not isinstance(noscript, Tag):
                    continue
                noscript_content = noscript.decode_contents()
                if "<img" in noscript_content:
                    # Parse the noscript content and extract images
                    noscript_soup = BeautifulSoup(noscript_content, "html.parser")
                    for img in noscript_soup.find_all("img"):
                        if isinstance(img, Tag) and img.get("src"):
                            # Insert the real image before the noscript tag
                            noscript.insert_before(img)

            # Convert relative URLs to absolute
            if base_url:
                self._fix_relative_urls(soup, base_url)

            return str(soup)
        except Exception as e:
            logger.debug(f"HTML preprocessing failed: {e}")
            return html_content

    def _fix_relative_urls(self, soup: BeautifulSoup, base_url: str) -> None:
        """
        Convert relative URLs to absolute URLs in HTML.

        Handles img src, a href, video src, source src, etc.
        """
        # Ensure base_url has scheme
        if not urlparse(base_url).scheme:
            base_url = "https://" + base_url

        # Fix image sources
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if (
                isinstance(src, str)
                and src
                and not src.startswith(("http://", "https://", "data:"))
            ):
                img["src"] = urljoin(base_url, src)

            # Also fix srcset
            srcset = img.get("srcset")
            if isinstance(srcset, str) and srcset:
                new_srcset = self._fix_srcset(srcset, base_url)
                img["srcset"] = new_srcset

            # Add referrerpolicy to bypass hotlinking protection
            img["referrerpolicy"] = "no-referrer"

        # Fix video/audio sources
        for media in soup.find_all(["video", "audio", "source"]):
            if not isinstance(media, Tag):
                continue
            src = media.get("src")
            if (
                isinstance(src, str)
                and src
                and not src.startswith(("http://", "https://", "data:"))
            ):
                media["src"] = urljoin(base_url, src)

        # Fix links (optional, but helpful for reference links)
        for a in soup.find_all("a"):
            if not isinstance(a, Tag):
                continue
            href = a.get("href")
            if (
                isinstance(href, str)
                and href
                and not href.startswith(
                    ("http://", "https://", "mailto:", "tel:", "#", "javascript:")
                )
            ):
                a["href"] = urljoin(base_url, href)

    def _fix_srcset(self, srcset: str, base_url: str) -> str:
        """Fix relative URLs in srcset attribute."""
        parts = []
        for part in srcset.split(","):
            part = part.strip()
            if not part:
                continue
            # srcset format: "url size" or just "url"
            tokens = part.split()
            if tokens:
                url = tokens[0]
                if not url.startswith(("http://", "https://", "data:")):
                    tokens[0] = urljoin(base_url, url)
                parts.append(" ".join(tokens))
        return ", ".join(parts)

    def _score_content(
        self, content: str, has_images: bool = False, has_code: bool = False
    ) -> float:
        """
        Score content quality based on multiple factors.

        Higher score = better content.

        Args:
            content: The extracted HTML content
            has_images: Whether the content contains images
            has_code: Whether the content contains code blocks
        """
        if not content:
            return 0.0

        score = 0.0

        # Get text content for analysis
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # Length score (logarithmic to avoid favoring overly long content)
        length = len(text)
        if length < 100:
            score += length * 0.1
        elif length < 500:
            score += 10 + (length - 100) * 0.05
        elif length < 2000:
            score += 30 + (length - 500) * 0.02
        else:
            score += 60 + min((length - 2000) * 0.005, 40)

        # Paragraph structure (good articles have multiple paragraphs)
        paragraphs = soup.find_all("p")
        meaningful_paragraphs = [
            p for p in paragraphs if len(p.get_text(strip=True)) > 50
        ]
        score += min(len(meaningful_paragraphs) * 5, 30)

        # Sentence structure (proper sentences end with punctuation)
        sentences = re.findall(r"[A-Z][^.!?]*[.!?]", text)
        score += min(len(sentences) * 0.5, 20)

        # Penalize if too many links (often navigation)
        links = soup.find_all("a")
        if len(links) > 20:
            score -= (len(links) - 20) * 0.5

        # Penalize common boilerplate patterns
        boilerplate = [
            "cookie",
            "privacy policy",
            "terms of service",
            "subscribe",
            "sign up",
            "follow us",
            "share this",
            "advertisement",
            "copyright",
            "all rights reserved",
            "loading...",
        ]
        text_lower = text.lower()
        for pattern in boilerplate:
            if pattern in text_lower:
                score -= 5

        # Bonus for headings (indicates structured content)
        headings = soup.find_all(["h1", "h2", "h3"])
        score += min(len(headings) * 3, 15)

        # Bonus for images (rich content)
        if has_images:
            images = soup.find_all("img")
            score += min(len(images) * 10, 30)

        # Bonus for code blocks (technical content)
        if has_code:
            pre_blocks = soup.find_all("pre")
            code_blocks = soup.find_all("code")
            score += min(len(pre_blocks) * 8 + len(code_blocks) * 2, 30)

        # Bonus for video embeds
        video_embeds = soup.find_all("iframe")
        video_count = sum(
            1 for iframe in video_embeds
            if isinstance(iframe.get("src"), str)
            and VideoEmbedParser.is_trusted_video_embed(iframe.get("src", ""))
        )
        if video_count > 0:
            score += min(video_count * 15, 30)

        return max(score, 0)

    def _extract_with_trafilatura(self, html_content: str) -> Optional[str]:
        """Extract content using trafilatura library."""
        try:
            result = trafilatura.extract(
                html_content,
                output_format="html",
                include_links=True,
                include_images=True,
                include_tables=True,
                include_formatting=True,
                favor_recall=True,
            )
            if result:
                return self._clean_html(result)
        except Exception as e:
            logger.debug(f"Trafilatura extraction failed: {e}")
        return None

    def _extract_with_readability(self, html_content: str) -> Optional[str]:
        """Extract content using Mozilla's Readability algorithm."""
        try:
            doc = Document(html_content)
            summary_html = doc.summary()
            if summary_html:
                return self._clean_html(summary_html)
        except Exception as e:
            logger.debug(f"Readability extraction failed: {e}")
        return None

    def _extract_with_cleaning(self, html_content: str) -> Optional[str]:
        """Extract content by cleaning HTML directly."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Try to find article content first
            article_content = self._find_article_content(soup)
            if article_content:
                soup = article_content

            # Remove unwanted tags
            self._remove_unwanted_tags(soup)

            # Remove ad elements
            self._remove_ad_elements(soup)

            result = str(soup)
            if result:
                return self._clean_html(result)
        except Exception as e:
            logger.debug(f"Direct extraction failed: {e}")
        return None

    def _find_article_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Try to find the main article content element."""
        selectors: list[str] = [
            "article",
            "[role='main']",
            "[role='article']",
            ".post-content",
            ".entry-content",
            ".article-content",
            ".article-body",
            ".article__body",
            ".post-body",
            ".story-body",
            ".story-content",
            ".content-body",
            ".body-content",
            ".rich-text",
            ".prose",
            "main article",
            "main .content",
            "main",
            "#article-body",
            "#article-content",
            "#post-content",
            "#content",
            "#main-content",
            ".main-content",
        ]

        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element and len(element.get_text(strip=True)) > 100:
                    return BeautifulSoup(str(element), "html.parser")
            except Exception:
                continue

        return None

    def _remove_unwanted_tags(self, soup: BeautifulSoup) -> None:
        """Remove script, style, nav, and other non-content tags."""
        for tag in self.REMOVE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()

        # Handle iframes specially - keep video embeds, remove others
        self._filter_iframes(soup)

    def _filter_iframes(self, soup: BeautifulSoup) -> None:
        """Remove non-video iframes while preserving trusted video embeds."""
        for iframe in soup.find_all("iframe"):
            if not isinstance(iframe, Tag):
                continue

            src = iframe.get("src", "")
            if isinstance(src, str) and VideoEmbedParser.is_trusted_video_embed(src):
                # Keep video embed and wrap in responsive container
                iframe["frameborder"] = "0"
                iframe["allowfullscreen"] = ""
                # Wrap in video container if not already wrapped
                parent = iframe.parent
                if parent and isinstance(parent, Tag):
                    parent_class = parent.get("class")
                    if not (
                        isinstance(parent_class, list)
                        and "video-wrapper" in parent_class
                    ):
                        wrapper = soup.new_tag("div")
                        wrapper["class"] = "video-wrapper"
                        iframe.wrap(wrapper)
            else:
                # Remove non-video iframes
                iframe.decompose()

    def _remove_ad_elements(self, soup: BeautifulSoup) -> None:
        """Remove elements with ad-related class names or IDs."""
        for element in soup.find_all(True):
            if element is None:
                continue

            element_classes = element.get("class")
            element_id = element.get("id")

            if element_classes and isinstance(element_classes, list):
                class_str = " ".join(str(c) for c in element_classes).lower()
                if self._matches_pattern(class_str):
                    element.decompose()
                    continue

            if element_id and isinstance(element_id, str):
                if self._matches_pattern(element_id.lower()):
                    element.decompose()

    def _matches_pattern(self, text: str) -> bool:
        """Check if text matches any of the removal patterns."""
        return any(pattern in text for pattern in self.REMOVE_PATTERNS)

    def _clean_html(self, content: str) -> str:
        """Clean up HTML content."""
        if not content:
            return ""

        try:
            soup = BeautifulSoup(content, "html.parser")

            # Remove empty elements (but keep br, hr, img, table, video elements)
            preserve_tags = {
                "br", "hr", "img", "table", "thead", "tbody", "tr", "th", "td",
                "iframe", "video", "audio", "source",
            }
            for element in soup.find_all():
                if element.name not in preserve_tags:
                    # Check for media content before removing
                    has_media = (
                        element.find("img") or
                        element.find("iframe") or
                        element.find("video")
                    )
                    if not element.get_text(strip=True) and not has_media:
                        element.decompose()

            # Wrap tables in a responsive wrapper div
            for table in soup.find_all("table"):
                if not isinstance(table, Tag):
                    continue
                # Skip if already wrapped
                parent = table.parent
                if parent and isinstance(parent, Tag):
                    parent_class = parent.get("class")
                    if (
                        isinstance(parent_class, list)
                        and "table-wrapper" in parent_class
                    ):
                        continue

                wrapper = soup.new_tag("div")
                wrapper["class"] = "table-wrapper"
                table.wrap(wrapper)

            return str(soup).strip()
        except Exception:
            return content.strip()

    async def fetch_and_convert(
        self,
        url: str,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> Optional[str]:
        """
        Fetch HTML from URL and extract clean content.

        Tries multiple strategies for both fetching and extraction.
        """
        # Strategy 1: Trafilatura fetch (handles many edge cases)
        result = self._fetch_with_trafilatura(url)
        if result and self._score_content(result) > 30:
            return result

        # Strategy 2: Direct fetch with httpx + multi-extraction
        for attempt in range(max_retries + 1):
            try:
                html_content = await self._fetch_html(url, timeout)
                if html_content:
                    result = self.to_html(html_content, url)
                    if result and self._score_content(result) > 20:
                        return result
            except Exception as e:
                logger.debug(f"Fetch attempt {attempt + 1} failed for {url}: {e}")
                if attempt == max_retries:
                    break

        return None

    def _fetch_with_trafilatura(self, url: str) -> Optional[str]:
        """Fetch and extract content using trafilatura's built-in fetcher."""
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                result = trafilatura.extract(
                    downloaded,
                    output_format="html",
                    include_links=True,
                    include_images=True,
                    include_tables=True,
                    include_formatting=True,
                    favor_recall=True,
                )
                if result:
                    return self._clean_html(result)
        except Exception as e:
            logger.debug(f"Trafilatura fetch failed for {url}: {e}")
        return None

    async def _fetch_html(self, url: str, timeout: float) -> Optional[str]:
        """Fetch HTML content from URL using httpx."""
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                text: str = response.text
                return text
        except httpx.TimeoutException:
            logger.debug(f"Timeout fetching {url}")
        except httpx.HTTPStatusError as e:
            logger.debug(f"HTTP error fetching {url}: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.debug(f"Request error fetching {url}: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error fetching {url}: {e}")
        return None

    def fetch_and_convert_sync(
        self,
        url: str,
        timeout: float = 30.0,
    ) -> Optional[str]:
        """
        Synchronous version of fetch_and_convert.

        Tries multiple extraction strategies and returns the best result.
        Prioritizes extraction methods that preserve images and code.
        """
        results: list[ExtractionResult] = []
        html_content: Optional[str] = None

        # First, fetch HTML directly so we can check for images/code
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                html_content = response.text
        except Exception as e:
            logger.debug(f"Direct fetch failed for {url}: {e}")

        # Check what the original HTML contains
        html_has_images = html_content and "<img" in html_content.lower()
        html_has_code = html_content and (
            "<pre" in html_content.lower() or "<code" in html_content.lower()
        )

        # Try domain-specific parser first if we have HTML
        domain = extract_domain(url)
        if domain and html_content:
            parser = domain_parser_registry.get_parser(domain)
            if parser:
                # Preprocess HTML first
                preprocessed = self._preprocess_html(html_content, url)
                domain_result = parser.extract(preprocessed, url)
                if domain_result:
                    has_images = "<img" in domain_result.lower()
                    has_code = (
                        "<pre" in domain_result.lower()
                        or "<code" in domain_result.lower()
                    )
                    score = self._score_content(domain_result, has_images, has_code)
                    if score > 30:
                        logger.debug(f"Using domain parser for {url}: {domain}")
                        return str(domain_result)

        # Strategy 1: Trafilatura fetch
        result = self._fetch_with_trafilatura(url)
        if result:
            has_images = "<img" in result.lower()
            has_code = "<pre" in result.lower() or "<code" in result.lower()
            score = self._score_content(result, has_images, has_code)
            results.append(
                ExtractionResult(result, "trafilatura", score, has_images, has_code)
            )

        # Strategy 2: Use fetched HTML with multiple extractors
        if html_content:
            # Preprocess to fix lazy images and relative URLs
            html_content = self._preprocess_html(html_content, url)

            # Try readability
            readability_result = self._extract_with_readability(html_content)
            if readability_result:
                has_images = "<img" in readability_result.lower()
                has_code = (
                    "<pre" in readability_result.lower()
                    or "<code" in readability_result.lower()
                )
                score = self._score_content(readability_result, has_images, has_code)
                results.append(
                    ExtractionResult(
                        readability_result, "readability", score, has_images, has_code
                    )
                )

            # Try direct cleaning
            direct_result = self._extract_with_cleaning(html_content)
            if direct_result:
                has_images = "<img" in direct_result.lower()
                has_code = (
                    "<pre" in direct_result.lower() or "<code" in direct_result.lower()
                )
                score = self._score_content(direct_result, has_images, has_code) * 0.9
                results.append(
                    ExtractionResult(
                        direct_result, "direct", score, has_images, has_code
                    )
                )

        if not results:
            return None

        # Boost results that preserve images/code when original has them
        for r in results:
            if html_has_images and r.has_images:
                r.score *= 1.2
            if html_has_code and r.has_code:
                r.score *= 1.2

        # Pick best result
        best = max(results, key=lambda r: r.score)
        logger.debug(
            f"Best extractor for {url}: {best.source} "
            f"(score: {best.score:.1f}, img:{best.has_images}, code:{best.has_code})"
        )

        return best.content if best.score > 20 else None
