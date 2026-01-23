"""Base classes and protocols for domain-specific content parsers."""

from abc import ABC, abstractmethod
from typing import Optional, Protocol, runtime_checkable

from bs4 import BeautifulSoup


@runtime_checkable
class DomainParser(Protocol):
    """Protocol for domain-specific content parsers."""

    domains: list[str]

    def can_handle(self, domain: str) -> bool:
        """Check if this parser can handle the given domain."""
        ...

    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract clean HTML content from the page.

        Args:
            html_content: Preprocessed HTML (lazy images fixed, relative URLs resolved)
            base_url: Original URL for context

        Returns:
            Clean HTML string or None if extraction fails
        """
        ...


class BaseDomainParser(ABC):
    """Base class for domain-specific parsers with common utilities."""

    domains: list[str] = []

    def can_handle(self, domain: str) -> bool:
        """
        Check if this parser handles the domain.

        Supports:
        - Exact match: "en.wikipedia.org"
        - Wildcard subdomains: "*.wikipedia.org" matches en/de.wikipedia.org
        - Base domain: "wikipedia.org" matches only the base domain
        """
        domain = domain.lower()
        for pattern in self.domains:
            pattern = pattern.lower()
            if pattern.startswith("*."):
                # Wildcard subdomain match
                suffix = pattern[2:]
                if domain == suffix or domain.endswith("." + suffix):
                    return True
            elif domain == pattern:
                return True
        return False

    @abstractmethod
    def extract(
        self,
        html_content: str,
        base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Extract content - must be implemented by subclasses."""
        ...

    def _create_soup(self, html: str) -> BeautifulSoup:
        """Create a BeautifulSoup instance."""
        return BeautifulSoup(html, "html.parser")

    def _remove_elements(self, soup: BeautifulSoup, selectors: list[str]) -> None:
        """Remove elements matching CSS selectors."""
        for selector in selectors:
            for element in soup.select(selector):
                element.decompose()

    def _remove_empty_elements(self, soup: BeautifulSoup) -> None:
        """Remove elements that are empty after other removals."""
        preserve_tags = {"br", "hr", "img", "table", "tr", "td", "th", "thead", "tbody"}
        for element in soup.find_all():
            if element.name not in preserve_tags:
                if not element.get_text(strip=True) and not element.find("img"):
                    element.decompose()
