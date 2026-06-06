"""EPUB generation service."""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from typing import Final, Sequence
from urllib.parse import unquote_to_bytes, urljoin
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag
from PIL import Image, UnidentifiedImageError

from domain.models import Article

EPUB_MAX_ARTICLES: Final[int] = 100
EPUB_MAX_IMAGES: Final[int] = 300
EPUB_MAX_IMAGE_BYTES: Final[int] = 10 * 1024 * 1024
EPUB_IMAGE_TIMEOUT_SECONDS: Final[float] = 15.0

SUPPORTED_IMAGE_TYPES: Final[dict[str, str]] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}

CONVERTIBLE_IMAGE_TYPES: Final[set[str]] = {"image/webp", "image/avif"}

IMAGE_MEDIA_ALIASES: Final[dict[str, str]] = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
}

ALLOWED_TAGS: Final[set[str]] = {
    "a",
    "article",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "section",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

REMOVED_TAGS: Final[set[str]] = {
    "audio",
    "canvas",
    "embed",
    "iframe",
    "noscript",
    "object",
    "script",
    "source",
    "style",
    "video",
}

ALLOWED_ATTRIBUTES: Final[dict[str, set[str]]] = {
    "a": {"href", "title"},
    "img": {"alt", "src", "title"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}

EPUB_STYLES: Final[str] = """
body {
  font-family: serif;
  line-height: 1.6;
  margin: 2rem;
}
h1, h2, h3, h4, h5, h6 {
  line-height: 1.25;
}
img {
  display: block;
  height: auto;
  margin: 1rem auto;
  max-width: 100%;
}
blockquote {
  border-left: 0.25rem solid #999;
  margin-left: 0;
  padding-left: 1rem;
}
pre {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
table {
  border-collapse: collapse;
  width: 100%;
}
td, th {
  border: 1px solid #999;
  padding: 0.35rem;
}
.article-meta {
  color: #555;
  font-size: 0.9rem;
  margin-bottom: 2rem;
}
""".strip()


class EPUBGenerationError(Exception):
    """Base exception for EPUB generation failures."""


class EPUBImageError(EPUBGenerationError):
    """Raised when an article image cannot be embedded."""

    def __init__(
        self,
        article_title: str,
        image_url: str,
        reason: str,
    ) -> None:
        self.article_title = article_title
        self.image_url = image_url
        self.reason = reason
        template = 'Failed image download in "{title}": {url} ({reason})'
        message = template.format(
            title=article_title,
            url=image_url,
            reason=reason,
        )
        super().__init__(message)


@dataclass(frozen=True)
class EPUBImage:
    """Image embedded in the EPUB package."""

    href: str
    media_type: str
    data: bytes


@dataclass(frozen=True)
class EPUBArticleDocument:
    """Article XHTML document included in the EPUB package."""

    href: str
    title: str
    content: str


@dataclass
class EPUBBuildState:
    """Mutable state collected while building an EPUB."""

    images_by_source: dict[str, EPUBImage] = field(default_factory=dict)
    images_by_href: dict[str, EPUBImage] = field(default_factory=dict)
    image_count: int = 0


class EPUBService:
    """Generate EPUB files from Feedy articles."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self.http_client = http_client

    def generate(
        self,
        articles: Sequence[Article],
        title: str = "Feedy Articles",
    ) -> bytes:
        """Generate an EPUB file in memory.

        Images referenced by article content are downloaded and embedded.
        Any failed image download aborts the whole export so the user never
        receives a partial book.
        """
        if not articles:
            raise EPUBGenerationError("Select at least one article.")
        if len(articles) > EPUB_MAX_ARTICLES:
            template = "Cannot export more than {count} articles at once."
            message = template.format(
                count=EPUB_MAX_ARTICLES,
            )
            raise EPUBGenerationError(message)

        if self.http_client is not None:
            return self._generate_with_client(
                articles,
                title,
                self.http_client,
            )

        headers = {"User-Agent": "Feedy EPUB exporter"}
        timeout = httpx.Timeout(EPUB_IMAGE_TIMEOUT_SECONDS)
        with httpx.Client(
            follow_redirects=True,
            headers=headers,
            timeout=timeout,
        ) as client:
            return self._generate_with_client(articles, title, client)

    def _generate_with_client(
        self,
        articles: Sequence[Article],
        title: str,
        client: httpx.Client,
    ) -> bytes:
        state = EPUBBuildState()
        documents = [
            self._build_article_document(article, index, state, client)
            for index, article in enumerate(articles, start=1)
        ]
        images = list(state.images_by_href.values())
        return self._package_epub(title, documents, images)

    def _build_article_document(
        self,
        article: Article,
        index: int,
        state: EPUBBuildState,
        client: httpx.Client,
    ) -> EPUBArticleDocument:
        href = f"articles/article_{index}.xhtml"
        body = self._sanitize_article_content(article, state, client)
        metadata = self._article_metadata(article)
        escaped_title = html.escape(article.title)

        content = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>{escaped_title}</title>
  <link rel="stylesheet" type="text/css" href="../styles/style.css" />
</head>
<body>
  <article>
    <h1>{escaped_title}</h1>
    {metadata}
    {body}
  </article>
</body>
</html>"""
        return EPUBArticleDocument(
            href=href,
            title=article.title,
            content=content,
        )

    def _article_metadata(self, article: Article) -> str:
        parts: list[str] = []
        website = getattr(article, "website", None)
        website_name = getattr(website, "name", None)
        if isinstance(website_name, str) and website_name:
            parts.append(html.escape(website_name))

        published_at = article.published_at or article.fetched_at
        if published_at is not None:
            parts.append(html.escape(published_at.strftime("%Y-%m-%d")))

        escaped_url = html.escape(article.url, quote=True)
        original_link = f'<a href="{escaped_url}">{escaped_url}</a>'
        parts.append(original_link)

        return f'<p class="article-meta">{" | ".join(parts)}</p>'

    def _sanitize_article_content(
        self,
        article: Article,
        state: EPUBBuildState,
        client: httpx.Client,
    ) -> str:
        soup = BeautifulSoup(article.content_html or "", "html.parser")

        for tag in soup.find_all(list(REMOVED_TAGS)):
            tag.decompose()

        for picture in soup.find_all("picture"):
            picture.unwrap()

        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue
            self._embed_tag_image(article, img, state, client)

        self._sanitize_tags(soup, article.url)

        body = "".join(str(child) for child in soup.contents).strip()
        if not body:
            return "<p>No content available for this article.</p>"
        return body

    def _embed_tag_image(
        self,
        article: Article,
        img: Tag,
        state: EPUBBuildState,
        client: httpx.Client,
    ) -> None:
        raw_src = str(img.get("src") or "").strip()
        if not raw_src:
            raise EPUBImageError(
                article.title, "missing image src", "Missing image URL"
            )

        embedded = self._embed_image(article, raw_src, state, client)
        img["src"] = f"../{embedded.href}"
        if img.get("alt") is None:
            img["alt"] = ""

    def _embed_image(
        self,
        article: Article,
        raw_src: str,
        state: EPUBBuildState,
        client: httpx.Client,
    ) -> EPUBImage:
        if raw_src.startswith("data:"):
            image_url = raw_src
        else:
            image_url = urljoin(article.url, raw_src)
        source_key = self._source_key(image_url)
        existing = state.images_by_source.get(source_key)
        if existing is not None:
            return existing

        if state.image_count >= EPUB_MAX_IMAGES:
            raise EPUBGenerationError(
                f"Cannot export more than {EPUB_MAX_IMAGES} images at once."
            )
        state.image_count += 1

        data, media_type = self._read_image(article, image_url, client)
        digest = hashlib.sha256(data).hexdigest()[:20]
        href = f"images/{digest}{SUPPORTED_IMAGE_TYPES[media_type]}"
        image = state.images_by_href.get(href)
        if image is None:
            image = EPUBImage(href=href, media_type=media_type, data=data)
            state.images_by_href[href] = image

        state.images_by_source[source_key] = image
        return image

    def _read_image(
        self,
        article: Article,
        image_url: str,
        client: httpx.Client,
    ) -> tuple[bytes, str]:
        if image_url.startswith("data:"):
            return self._decode_data_image(article, image_url)
        return self._download_image(article, image_url, client)

    def _decode_data_image(
        self,
        article: Article,
        image_url: str,
    ) -> tuple[bytes, str]:
        try:
            header, payload = image_url[5:].split(",", 1)
        except ValueError:
            raise EPUBImageError(
                article.title, "embedded data image", "Invalid data URL"
            )

        parts = [part.strip() for part in header.split(";") if part.strip()]
        media_type = self._normalize_media_type(parts[0] if parts else "")
        if media_type is None:
            media_type_label = parts[0] if parts else "unknown"
            reason = f"Unsupported image type: {media_type_label}"
            raise EPUBImageError(article.title, "embedded data image", reason)

        try:
            if any(part.lower() == "base64" for part in parts[1:]):
                data = base64.b64decode(payload, validate=True)
            else:
                data = unquote_to_bytes(payload)
        except (binascii.Error, ValueError):
            raise EPUBImageError(
                article.title,
                "embedded data image",
                "Invalid data",
            )

        self._validate_image_size(article, "embedded data image", data)
        return self._ensure_epub_image_type(
            article,
            "embedded data image",
            data,
            media_type,
        )

    def _download_image(
        self,
        article: Article,
        image_url: str,
        client: httpx.Client,
    ) -> tuple[bytes, str]:
        try:
            with client.stream("GET", image_url) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise EPUBImageError(
                        article.title,
                        image_url,
                        f"HTTP {response.status_code}",
                    )

                header_media_type = response.headers.get("content-type", "")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > EPUB_MAX_IMAGE_BYTES:
                        reason = self._image_too_large_reason()
                        raise EPUBImageError(
                            article.title,
                            image_url,
                            reason,
                        )
        except EPUBImageError:
            raise
        except httpx.TimeoutException:
            raise EPUBImageError(
                article.title,
                image_url,
                "Download timed out",
            )
        except httpx.HTTPError as exc:
            raise EPUBImageError(article.title, image_url, str(exc))

        image_data = bytes(data)
        self._validate_image_size(article, image_url, image_data)
        media_type = self._detect_media_type(
            article, image_url, image_data, header_media_type
        )
        return self._ensure_epub_image_type(
            article,
            image_url,
            image_data,
            media_type,
        )

    def _ensure_epub_image_type(
        self,
        article: Article,
        image_url: str,
        data: bytes,
        media_type: str,
    ) -> tuple[bytes, str]:
        if media_type in SUPPORTED_IMAGE_TYPES:
            return data, media_type
        if media_type in CONVERTIBLE_IMAGE_TYPES:
            return self._convert_image_to_png(article, image_url, data)
        raise EPUBImageError(
            article.title,
            image_url,
            f"Unsupported image type: {media_type}",
        )

    def _convert_image_to_png(
        self,
        article: Article,
        image_url: str,
        data: bytes,
    ) -> tuple[bytes, str]:
        try:
            with Image.open(BytesIO(data)) as image:
                output_image: Image.Image
                if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
                    output_image = image.convert("RGBA")
                else:
                    output_image = image
                converted = BytesIO()
                output_image.save(converted, format="PNG")
        except (OSError, UnidentifiedImageError) as exc:
            raise EPUBImageError(
                article.title,
                image_url,
                f"Could not convert image to PNG: {exc}",
            ) from exc

        converted_data = converted.getvalue()
        self._validate_image_size(article, image_url, converted_data)
        return converted_data, "image/png"

    def _validate_image_size(
        self,
        article: Article,
        image_url: str,
        data: bytes,
    ) -> None:
        if not data:
            raise EPUBImageError(
                article.title,
                image_url,
                "Image response is empty",
            )
        if len(data) > EPUB_MAX_IMAGE_BYTES:
            reason = self._image_too_large_reason()
            raise EPUBImageError(
                article.title,
                image_url,
                reason,
            )

    def _image_too_large_reason(self) -> str:
        return f"Image is larger than {EPUB_MAX_IMAGE_BYTES} bytes"

    def _detect_media_type(
        self,
        article: Article,
        image_url: str,
        data: bytes,
        header_media_type: str,
    ) -> str:
        normalized_header = self._normalize_media_type(header_media_type)
        if normalized_header is not None:
            return normalized_header

        detected = self._detect_media_type_from_signature(data)
        if detected is not None:
            return detected

        if header_media_type:
            media_type_label = header_media_type.split(";", 1)[0]
            reason = f"Unsupported image type: {media_type_label}"
        else:
            reason = "Could not determine image type"
        raise EPUBImageError(article.title, image_url, reason)

    def _normalize_media_type(self, media_type: str) -> str | None:
        normalized = media_type.split(";", 1)[0].strip().lower()
        normalized = IMAGE_MEDIA_ALIASES.get(normalized, normalized)
        is_epub_safe = normalized in SUPPORTED_IMAGE_TYPES
        is_convertible = normalized in CONVERTIBLE_IMAGE_TYPES
        if is_epub_safe or is_convertible:
            return normalized
        return None

    def _detect_media_type_from_signature(self, data: bytes) -> str | None:
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        if b"ftypavif" in data[:32] or b"ftypavis" in data[:32]:
            return "image/avif"

        prefix = data.lstrip()[:200].lower()
        if prefix.startswith((b"<svg", b"<?xml")) and b"<svg" in prefix:
            return "image/svg+xml"
        return None

    def _sanitize_tags(self, soup: BeautifulSoup, base_url: str) -> None:
        for element in list(soup.find_all(True)):
            if not isinstance(element, Tag):
                continue

            tag_name = str(element.name).lower()
            if tag_name not in ALLOWED_TAGS:
                element.unwrap()
                continue

            allowed = ALLOWED_ATTRIBUTES.get(tag_name, set())
            original_attrs = dict(element.attrs)
            element.attrs = {}

            for attr_name in allowed:
                if attr_name not in original_attrs:
                    continue
                value = original_attrs[attr_name]
                if isinstance(value, list):
                    value = " ".join(str(item) for item in value)
                value_str = str(value).strip()
                if not value_str:
                    continue

                if tag_name == "a" and attr_name == "href":
                    element[attr_name] = self._normalize_link(
                        base_url,
                        value_str,
                    )
                else:
                    element[attr_name] = value_str

    def _normalize_link(self, base_url: str, href: str) -> str:
        if href.startswith(("#", "mailto:", "tel:")):
            return href
        return urljoin(base_url, href)

    def _package_epub(
        self,
        title: str,
        documents: Sequence[EPUBArticleDocument],
        images: Sequence[EPUBImage],
    ) -> bytes:
        buffer = BytesIO()
        with ZipFile(buffer, "w") as epub:
            epub.writestr(
                "mimetype",
                "application/epub+zip",
                compress_type=ZIP_STORED,
            )
            epub.writestr(
                "META-INF/container.xml",
                self._container_xml(),
                compress_type=ZIP_DEFLATED,
            )
            epub.writestr(
                "OEBPS/content.opf",
                self._content_opf(title, documents, images),
                compress_type=ZIP_DEFLATED,
            )
            epub.writestr(
                "OEBPS/nav.xhtml",
                self._nav_xhtml(title, documents),
                compress_type=ZIP_DEFLATED,
            )
            epub.writestr(
                "OEBPS/styles/style.css",
                EPUB_STYLES,
                compress_type=ZIP_DEFLATED,
            )

            for document in documents:
                epub.writestr(
                    f"OEBPS/{document.href}",
                    document.content,
                    compress_type=ZIP_DEFLATED,
                )
            for image in images:
                epub.writestr(
                    f"OEBPS/{image.href}",
                    image.data,
                    compress_type=ZIP_DEFLATED,
                )

        return buffer.getvalue()

    def _container_xml(self) -> str:
        return """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0"
           xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
              media-type="application/oebps-package+xml" />
  </rootfiles>
</container>"""

    def _content_opf(
        self,
        title: str,
        documents: Sequence[EPUBArticleDocument],
        images: Sequence[EPUBImage],
    ) -> str:
        book_id = f"urn:uuid:{uuid.uuid4()}"
        updated_dt = datetime.now(UTC).replace(microsecond=0).isoformat()
        updated = updated_dt.replace("+00:00", "Z")
        escaped_title = html.escape(title)

        style_manifest_item = " ".join(
            [
                '<item id="style"',
                'href="styles/style.css"',
                'media-type="text/css" />',
            ]
        )

        manifest_items = [
            '<item id="nav" href="nav.xhtml" '
            'media-type="application/xhtml+xml" properties="nav" />',
            style_manifest_item,
        ]
        spine_items = ['<itemref idref="nav" />']

        for index, document in enumerate(documents, start=1):
            item_id = f"article-{index}"
            manifest_items.append(
                f'<item id="{item_id}" href="{document.href}" '
                'media-type="application/xhtml+xml" />'
            )
            spine_items.append(f'<itemref idref="{item_id}" />')

        for index, image in enumerate(images, start=1):
            manifest_items.append(
                f'<item id="image-{index}" href="{image.href}" '
                f'media-type="{image.media_type}" />'
            )

        manifest = "\n    ".join(manifest_items)
        spine = "\n    ".join(spine_items)

        return f"""<?xml version="1.0" encoding="utf-8"?>
<package version="3.0" unique-identifier="book-id"
         xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{book_id}</dc:identifier>
    <dc:title>{escaped_title}</dc:title>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">{updated}</meta>
  </metadata>
  <manifest>
    {manifest}
  </manifest>
  <spine>
    {spine}
  </spine>
</package>"""

    def _nav_xhtml(
        self,
        title: str,
        documents: Sequence[EPUBArticleDocument],
    ) -> str:
        nav_items = "\n".join(
            f'      <li><a href="{document.href}">'
            f"{html.escape(document.title)}</a></li>"
            for document in documents
        )
        escaped_title = html.escape(title)

        return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{escaped_title}</title>
  <link rel="stylesheet" type="text/css" href="styles/style.css" />
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{escaped_title}</h1>
    <ol>
{nav_items}
    </ol>
  </nav>
</body>
</html>"""

    def _source_key(self, image_url: str) -> str:
        if image_url.startswith("data:"):
            digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
            return f"data:{digest}"
        return image_url


epub_service = EPUBService()
