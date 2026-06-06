from __future__ import annotations

from collections.abc import Generator, Sequence
from datetime import date, datetime
from io import BytesIO
from types import SimpleNamespace
from typing import cast
from zipfile import ZIP_STORED, ZipFile

import httpx
import pytest
from fastapi import Request
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from api.routers import epub as epub_router
from application.services.epub import EPUBImageError, EPUBService
from domain.models import Article, Category, Website
from infrastructure.database import Base

PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
    "x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@pytest.fixture()
def isolated_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )

    session = session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_article(
    article_id: str = "article-1",
    content_html: str | None = None,
) -> Article:
    return Article(
        id=article_id,
        title="Example Article",
        url="https://example.com/articles/example",
        domain="example.com",
        content_html=content_html or f'<p>Hello</p><img src="{PNG_DATA_URL}">',
        website_id="website-1",
        published_at=datetime(2026, 1, 2),
        fetched_at=datetime(2026, 1, 3),
        is_read=False,
    )


def make_webp_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buffer, format="WEBP")
    return buffer.getvalue()


def test_epub_service_embeds_images() -> None:
    service = EPUBService()
    article = make_article()

    epub_bytes = service.generate([article], title="Test Book")

    with ZipFile(BytesIO(epub_bytes)) as archive:
        assert archive.read("mimetype") == b"application/epub+zip"
        assert archive.getinfo("mimetype").compress_type == ZIP_STORED
        assert "META-INF/container.xml" in archive.namelist()
        assert "OEBPS/content.opf" in archive.namelist()
        assert "OEBPS/nav.xhtml" in archive.namelist()

        content_opf = archive.read("OEBPS/content.opf").decode("utf-8")
        nav_index = content_opf.index('idref="nav"')
        first_article_index = content_opf.index('idref="article-1"')
        assert nav_index < first_article_index

        nav_xhtml = archive.read("OEBPS/nav.xhtml").decode("utf-8")
        expected_link = "".join(
            [
                '<a href="articles/article_1.xhtml">',
                "Example Article</a>",
            ]
        )
        assert expected_link in nav_xhtml

        image_names = []
        for name in archive.namelist():
            if name.startswith("OEBPS/images/"):
                image_names.append(name)
        assert len(image_names) == 1
        assert image_names[0].endswith(".png")

        article_bytes = archive.read("OEBPS/articles/article_1.xhtml")
        article_html = article_bytes.decode("utf-8")
        assert "../images/" in article_html
        assert "data:image" not in article_html
        assert "https://example.com/articles/example" in article_html


def test_epub_service_fails_when_image_download_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = EPUBService(http_client=client)
    article = make_article(content_html='<p>Hello</p><img src="/missing.png">')

    try:
        with pytest.raises(EPUBImageError) as exc_info:
            service.generate([article])
    finally:
        client.close()

    assert "HTTP 404" in str(exc_info.value)
    assert "https://example.com/missing.png" in str(exc_info.value)


def test_epub_service_converts_webp_images_to_png() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=make_webp_bytes(),
            headers={"content-type": "image/webp"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = EPUBService(http_client=client)
    article = make_article(content_html='<p>Hello</p><img src="/image.webp">')

    try:
        epub_bytes = service.generate([article])
    finally:
        client.close()

    with ZipFile(BytesIO(epub_bytes)) as archive:
        image_names = []
        for name in archive.namelist():
            if name.startswith("OEBPS/images/"):
                image_names.append(name)

        assert len(image_names) == 1
        assert image_names[0].endswith(".png")
        assert archive.read(image_names[0]).startswith(b"\x89PNG")


def test_epub_endpoint_marks_articles_as_read_after_success(
    isolated_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDate(date):
        @classmethod
        def today(cls: type["FixedDate"]) -> date:
            return cls(2026, 6, 5)

    category = Category(id="category-1", name="Tech", slug="tech", icon="tag")
    website = Website(
        id="website-1",
        name="Example",
        url="https://example.com",
        rss_url="https://example.com/feed.xml",
        category_id=category.id,
    )
    article = make_article()
    isolated_session.add_all([category, website, article])
    isolated_session.commit()

    def fake_generate(
        articles: Sequence[Article],
        title: str = "Feedy Articles",
    ) -> bytes:
        assert [selected.id for selected in articles] == [article.id]
        assert title == "Feedy Articles"
        return b"epub-bytes"

    monkeypatch.setattr(epub_router.epub_service, "generate", fake_generate)
    monkeypatch.setattr(epub_router, "date", FixedDate)
    request = cast(
        Request,
        SimpleNamespace(state=SimpleNamespace(lang="en")),
    )

    response = epub_router.export_epub(
        request,
        epub_router.EPUBExportRequest(article_ids=[article.id]),
        isolated_session,
    )

    assert response.body == b"epub-bytes"
    assert response.media_type == "application/epub+zip"
    assert response.headers["content-disposition"] == (
        "attachment; filename=feedy-2026-06-05.epub"
    )

    isolated_session.expire(article)
    updated_article = isolated_session.scalars(
        select(Article).where(Article.id == article.id)
    ).one()
    assert updated_article.is_read is True
