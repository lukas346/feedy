"""OPML import/export service for feed migration."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from typing import Optional
from xml.dom import minidom

from sqlalchemy.orm import Session

from domain.models import Website
from infrastructure.repositories import CategoryRepository, WebsiteRepository


@dataclass
class OPMLFeed:
    """Represents a feed from OPML."""

    name: str
    rss_url: str
    url: Optional[str] = None
    category: Optional[str] = None


@dataclass
class ImportResult:
    """Result of an OPML import operation."""

    categories_created: int
    feeds_created: int
    feeds_skipped: int
    errors: list[str]


class OPMLParseError(Exception):
    """Exception raised when OPML parsing fails."""

    pass


class OPMLService:
    """Service for OPML import/export operations."""

    def export(self, session: Session, title: str = "Feedy Feeds") -> str:
        """
        Export all feeds to OPML format.

        Args:
            session: Database session.
            title: Title for the OPML document.

        Returns:
            OPML XML string.
        """
        website_repo = WebsiteRepository(session)
        websites_with_categories = website_repo.get_all_with_category_names()

        # Build OPML structure
        opml = ET.Element("opml", version="2.0")

        head = ET.SubElement(opml, "head")
        title_elem = ET.SubElement(head, "title")
        title_elem.text = title

        body = ET.SubElement(opml, "body")

        # Group websites by category
        categories: dict[str, list[tuple[Website, str | None]]] = {}
        for website, category_name in websites_with_categories:
            cat_name = category_name or "Uncategorized"
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append((website, category_name))

        # Create category outlines with feed outlines
        for category_name in sorted(categories.keys()):
            category_outline = ET.SubElement(
                body, "outline", text=category_name, title=category_name
            )
            for website, _ in categories[category_name]:
                ET.SubElement(
                    category_outline,
                    "outline",
                    type="rss",
                    text=website.name,
                    title=website.name,
                    xmlUrl=website.rss_url,
                    htmlUrl=website.url,
                )

        # Pretty print XML
        xml_str = ET.tostring(opml, encoding="unicode")
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ", encoding="UTF-8")

        # Remove extra blank lines and fix XML declaration
        lines = pretty_xml.decode("utf-8").split("\n")
        cleaned_lines = [line for line in lines if line.strip()]
        return "\n".join(cleaned_lines)

    def parse(self, content: bytes) -> list[OPMLFeed]:
        """
        Parse OPML content and extract feeds.

        Args:
            content: Raw OPML file content.

        Returns:
            List of OPMLFeed objects.

        Raises:
            OPMLParseError: If the OPML is invalid.
        """
        try:
            tree = ET.parse(BytesIO(content))
            root = tree.getroot()
        except ET.ParseError as e:
            raise OPMLParseError(f"Invalid XML: {e}")

        if root.tag != "opml":
            raise OPMLParseError("Not a valid OPML file: missing opml root element")

        body = root.find("body")
        if body is None:
            raise OPMLParseError("Not a valid OPML file: missing body element")

        feeds: list[OPMLFeed] = []
        self._parse_outlines(body, feeds, category=None)

        return feeds

    def _parse_outlines(
        self,
        parent: ET.Element,
        feeds: list[OPMLFeed],
        category: Optional[str],
    ) -> None:
        """Recursively parse outline elements."""
        for outline in parent.findall("outline"):
            xml_url = outline.get("xmlUrl")

            if xml_url:
                # This is a feed
                name = outline.get("text") or outline.get("title") or xml_url
                html_url = outline.get("htmlUrl")

                feeds.append(
                    OPMLFeed(
                        name=name,
                        rss_url=xml_url,
                        url=html_url,
                        category=category,
                    )
                )
            else:
                # This is a category/folder, recurse
                cat_name = outline.get("text") or outline.get("title")
                self._parse_outlines(outline, feeds, category=cat_name)

    def import_feeds(self, session: Session, content: bytes) -> ImportResult:
        """
        Import feeds from OPML content.

        Args:
            session: Database session.
            content: Raw OPML file content.

        Returns:
            ImportResult with counts of created/skipped items.

        Raises:
            OPMLParseError: If the OPML is invalid.
        """
        feeds = self.parse(content)

        category_repo = CategoryRepository(session)
        website_repo = WebsiteRepository(session)

        # Get existing data
        existing_categories = {cat.name: cat for cat in category_repo.get_all()}
        existing_rss_urls = {w.rss_url for w in website_repo.get_all()}

        result = ImportResult(
            categories_created=0,
            feeds_created=0,
            feeds_skipped=0,
            errors=[],
        )

        # Ensure "Uncategorized" category exists for feeds without category
        uncategorized_name = "Uncategorized"
        if uncategorized_name not in existing_categories:
            uncategorized = category_repo.create(
                name=uncategorized_name,
                slug=self._slugify(uncategorized_name),
                icon="folder",
            )
            existing_categories[uncategorized_name] = uncategorized
            result.categories_created += 1

        for feed in feeds:
            try:
                # Get or create category
                cat_name = feed.category or uncategorized_name
                if cat_name not in existing_categories:
                    category = category_repo.create(
                        name=cat_name,
                        slug=self._slugify(cat_name),
                        icon="tag",
                    )
                    existing_categories[cat_name] = category
                    result.categories_created += 1
                else:
                    category = existing_categories[cat_name]

                # Skip if RSS URL already exists
                if feed.rss_url in existing_rss_urls:
                    result.feeds_skipped += 1
                    continue

                # Create website
                website_repo.create(
                    name=feed.name,
                    url=feed.url or feed.rss_url,
                    rss_url=feed.rss_url,
                    category_id=category.id,
                    fetch_interval_minutes=60,
                )
                existing_rss_urls.add(feed.rss_url)
                result.feeds_created += 1

            except Exception as e:
                result.errors.append(f"Failed to import '{feed.name}': {e}")

        return result

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        # Lowercase and replace spaces with hyphens
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug


# Singleton instance
opml_service = OPMLService()
