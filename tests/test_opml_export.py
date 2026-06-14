from __future__ import annotations

from collections.abc import Generator
import xml.etree.ElementTree as ET

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from application.services.opml import OPMLService
from domain.models import Category, Website
from infrastructure.database import Base


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


def test_opml_export_handles_category_icon_result(
    isolated_session: Session,
) -> None:
    category = Category(id="category-1", name="Tech", slug="tech", icon="cpu")
    website = Website(
        id="website-1",
        name="Example",
        url="https://example.com",
        rss_url="https://example.com/feed.xml",
        category_id=category.id,
    )
    isolated_session.add_all([category, website])
    isolated_session.commit()

    xml_content = OPMLService().export(isolated_session, title="My Feeds")

    root = ET.fromstring(xml_content)
    assert root.attrib["version"] == "2.0"
    assert root.findtext("./head/title") == "My Feeds"

    body = root.find("body")
    assert body is not None
    category_outline = body.find("./outline[@text='Tech']")
    assert category_outline is not None
    feed_outline = category_outline.find(
        "./outline[@xmlUrl='https://example.com/feed.xml']"
    )
    assert feed_outline is not None
    assert feed_outline.attrib["text"] == "Example"
    assert feed_outline.attrib["htmlUrl"] == "https://example.com"
