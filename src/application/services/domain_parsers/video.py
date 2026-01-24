"""Video platform content parsers.

Handles embedding videos from popular platforms:
- YouTube (youtube.com, youtu.be)
- Vimeo (vimeo.com)
- Dailymotion (dailymotion.com)
- Twitch (twitch.tv)
- TED (ted.com)
- PeerTube instances
"""

import logging
import re
from typing import Any, Optional
from urllib.parse import ParseResult, parse_qs, urlparse

from .base import BaseDomainParser

logger = logging.getLogger(__name__)


class VideoEmbedParser(BaseDomainParser):
    """Parser for video platform pages.

    Extracts video content and creates responsive embed iframes.
    Preserves video metadata (title, description) when available.
    """

    domains: list[str] = [
        # YouTube
        "youtube.com",
        "*.youtube.com",
        "youtu.be",
        # Vimeo
        "vimeo.com",
        "*.vimeo.com",
        # Dailymotion
        "dailymotion.com",
        "*.dailymotion.com",
        "dai.ly",
        # Twitch
        "twitch.tv",
        "*.twitch.tv",
        # TED
        "ted.com",
        "*.ted.com",
    ]

    # Trusted video embed domains for iframe allowlisting
    TRUSTED_VIDEO_DOMAINS: list[str] = [
        "youtube.com",
        "youtube-nocookie.com",
        "youtu.be",
        "vimeo.com",
        "player.vimeo.com",
        "dailymotion.com",
        "twitch.tv",
        "player.twitch.tv",
        "ted.com",
        "embed.ted.com",
    ]

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract video content and create embed."""
        if not base_url:
            return None

        try:
            soup = self._create_soup(html_content)
            parsed_url = urlparse(base_url)
            domain = parsed_url.netloc.lower()

            # Extract video ID and create embed based on platform
            embed_html: Optional[str] = None
            description: Optional[str] = None

            # Try to get description from meta tags
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                meta_content = meta_desc.get("content")
                if isinstance(meta_content, str):
                    description = meta_content
            if description is None:
                og_desc = soup.find("meta", attrs={"property": "og:description"})
                if og_desc:
                    og_content = og_desc.get("content")
                    if isinstance(og_content, str):
                        description = og_content

            # Platform-specific extraction
            if "youtube.com" in domain or "youtu.be" in domain:
                embed_html = self._extract_youtube(base_url, parsed_url)
            elif "vimeo.com" in domain:
                embed_html = self._extract_vimeo(base_url, parsed_url)
            elif "dailymotion.com" in domain or "dai.ly" in domain:
                embed_html = self._extract_dailymotion(base_url, parsed_url)
            elif "twitch.tv" in domain:
                embed_html = self._extract_twitch(base_url, parsed_url)
            elif "ted.com" in domain:
                embed_html = self._extract_ted(base_url, parsed_url, soup)

            if not embed_html:
                return None

            # Build final HTML with video embed and metadata
            result_parts: list[str] = []

            # Add video embed in responsive wrapper
            result_parts.append(f'<div class="video-wrapper">{embed_html}</div>')

            # Add description if available
            if description:
                # Clean and truncate description
                description = description.strip()
                if len(description) > 500:
                    description = description[:500] + "..."
                result_parts.append(f"<p>{description}</p>")

            return "\n".join(result_parts)

        except Exception as e:
            logger.debug(f"Video parser failed for {base_url}: {e}")
            return None

    def _extract_youtube(self, url: str, parsed_url: ParseResult) -> Optional[str]:
        """Extract YouTube video ID and create embed."""
        video_id: Optional[str] = None

        # Handle youtu.be short URLs
        if "youtu.be" in parsed_url.netloc:
            path = parsed_url.path.strip("/")
            if path:
                video_id = path.split("/")[0]
        # Handle youtube.com URLs
        elif "youtube.com" in parsed_url.netloc:
            if "/watch" in parsed_url.path:
                # Standard watch URL: youtube.com/watch?v=VIDEO_ID
                query = parse_qs(parsed_url.query)
                video_ids = query.get("v")
                if video_ids:
                    video_id = video_ids[0]
            elif "/embed/" in parsed_url.path:
                # Already embed URL: youtube.com/embed/VIDEO_ID
                match = re.search(r"/embed/([a-zA-Z0-9_-]+)", parsed_url.path)
                if match:
                    video_id = match.group(1)
            elif "/shorts/" in parsed_url.path:
                # YouTube Shorts: youtube.com/shorts/VIDEO_ID
                match = re.search(r"/shorts/([a-zA-Z0-9_-]+)", parsed_url.path)
                if match:
                    video_id = match.group(1)
            elif "/live/" in parsed_url.path:
                # YouTube Live: youtube.com/live/VIDEO_ID
                match = re.search(r"/live/([a-zA-Z0-9_-]+)", parsed_url.path)
                if match:
                    video_id = match.group(1)

        if not video_id:
            return None

        # Use privacy-enhanced embed (youtube-nocookie.com)
        return (
            f'<iframe src="https://www.youtube-nocookie.com/embed/{video_id}" '
            f'frameborder="0" allowfullscreen '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
            f'gyroscope; picture-in-picture; web-share"></iframe>'
        )

    def _extract_vimeo(self, url: str, parsed_url: ParseResult) -> Optional[str]:
        """Extract Vimeo video ID and create embed."""
        video_id: Optional[str] = None

        # Standard Vimeo URL: vimeo.com/VIDEO_ID or vimeo.com/channels/xxx/VIDEO_ID
        path = parsed_url.path.strip("/")

        # Try to find numeric video ID
        match = re.search(r"(\d+)", path)
        if match:
            video_id = match.group(1)

        if not video_id:
            return None

        return (
            f'<iframe src="https://player.vimeo.com/video/{video_id}" '
            f'frameborder="0" allowfullscreen '
            f'allow="autoplay; fullscreen; picture-in-picture"></iframe>'
        )

    def _extract_dailymotion(self, url: str, parsed_url: ParseResult) -> Optional[str]:
        """Extract Dailymotion video ID and create embed."""
        video_id: Optional[str] = None

        # Handle dai.ly short URLs
        if "dai.ly" in parsed_url.netloc:
            path = parsed_url.path.strip("/")
            if path:
                video_id = path.split("/")[0]
        # Handle dailymotion.com URLs
        elif "dailymotion.com" in parsed_url.netloc:
            # Standard URL: dailymotion.com/video/VIDEO_ID
            match = re.search(r"/video/([a-zA-Z0-9]+)", parsed_url.path)
            if match:
                video_id = match.group(1)

        if not video_id:
            return None

        return (
            f'<iframe src="https://www.dailymotion.com/embed/video/{video_id}" '
            f'frameborder="0" allowfullscreen '
            f'allow="autoplay; fullscreen; picture-in-picture"></iframe>'
        )

    def _extract_twitch(self, url: str, parsed_url: ParseResult) -> Optional[str]:
        """Extract Twitch channel/video and create embed."""
        path = parsed_url.path.strip("/")

        if not path:
            return None

        # Twitch video: twitch.tv/videos/VIDEO_ID
        if path.startswith("videos/"):
            video_id = path.replace("videos/", "").split("/")[0]
            embed_url = f"https://player.twitch.tv/?video={video_id}&parent=localhost"
            return (
                f'<iframe src="{embed_url}" '
                f'frameborder="0" allowfullscreen '
                f'allow="autoplay; fullscreen"></iframe>'
            )

        # Twitch clip: twitch.tv/CHANNEL/clip/CLIP_ID
        if "/clip/" in path:
            match = re.search(r"/clip/([a-zA-Z0-9-]+)", path)
            if match:
                clip_id = match.group(1)
                embed_url = (
                    f"https://clips.twitch.tv/embed?clip={clip_id}&parent=localhost"
                )
                return (
                    f'<iframe src="{embed_url}" '
                    f'frameborder="0" allowfullscreen '
                    f'allow="autoplay; fullscreen"></iframe>'
                )

        # Twitch channel (live): twitch.tv/CHANNEL
        channel = path.split("/")[0]
        if channel:
            embed_url = f"https://player.twitch.tv/?channel={channel}&parent=localhost"
            return (
                f'<iframe src="{embed_url}" '
                f'frameborder="0" allowfullscreen '
                f'allow="autoplay; fullscreen"></iframe>'
            )

        return None

    def _extract_ted(
        self, url: str, parsed_url: ParseResult, soup: Any
    ) -> Optional[str]:
        """Extract TED talk and create embed."""
        path = parsed_url.path.strip("/")

        # TED talk URL: ted.com/talks/TALK_SLUG
        if not path.startswith("talks/"):
            return None

        talk_slug = path.replace("talks/", "").split("/")[0].split("?")[0]
        if not talk_slug:
            return None

        return (
            f'<iframe src="https://embed.ted.com/talks/{talk_slug}" '
            f'frameborder="0" allowfullscreen '
            f'allow="autoplay; fullscreen"></iframe>'
        )

    @classmethod
    def is_trusted_video_embed(cls, iframe_src: str) -> bool:
        """Check if an iframe src is from a trusted video platform."""
        try:
            parsed = urlparse(iframe_src)
            domain = parsed.netloc.lower()

            for trusted in cls.TRUSTED_VIDEO_DOMAINS:
                if domain == trusted or domain.endswith("." + trusted):
                    return True

            return False
        except Exception:
            return False

    @classmethod
    def extract_video_embed_from_html(cls, html_content: str) -> Optional[str]:
        """
        Find and preserve video embeds in HTML content.

        Searches for iframes pointing to trusted video platforms
        and returns them wrapped in responsive containers.
        """
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            video_embeds: list[str] = []

            # Find all iframes
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src", "")
                if isinstance(src, str) and cls.is_trusted_video_embed(src):
                    # Preserve the iframe with proper attributes
                    iframe["frameborder"] = "0"
                    iframe["allowfullscreen"] = ""
                    video_embeds.append(
                        f'<div class="video-wrapper">{str(iframe)}</div>'
                    )

            # Also look for video URLs in anchor tags to convert
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if isinstance(href, str):
                    embed_html = cls._url_to_embed(href)
                    if embed_html:
                        video_embeds.append(
                            f'<div class="video-wrapper">{embed_html}</div>'
                        )

            return "\n".join(video_embeds) if video_embeds else None
        except Exception:
            return None

    @classmethod
    def _url_to_embed(cls, url: str) -> Optional[str]:
        """Convert a video URL to an embed iframe."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Only convert known video URLs
            parser = VideoEmbedParser()

            if "youtube.com" in domain or "youtu.be" in domain:
                return parser._extract_youtube(url, parsed)
            elif "vimeo.com" in domain:
                return parser._extract_vimeo(url, parsed)
            elif "dailymotion.com" in domain or "dai.ly" in domain:
                return parser._extract_dailymotion(url, parsed)

            return None
        except Exception:
            return None
