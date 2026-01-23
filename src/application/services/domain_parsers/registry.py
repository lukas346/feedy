"""Registry for domain-specific content parsers."""

from typing import Optional

from .base import BaseDomainParser


class DomainParserRegistry:
    """Registry for domain-specific content parsers.

    Maintains a list of parsers and provides lookup by domain.
    """

    def __init__(self) -> None:
        self._parsers: list[BaseDomainParser] = []

    def register(self, parser: BaseDomainParser) -> None:
        """Register a domain parser."""
        self._parsers.append(parser)

    def get_parser(self, domain: str) -> Optional[BaseDomainParser]:
        """
        Get parser for a domain.

        Args:
            domain: The domain to find a parser for (e.g., "en.wikipedia.org")

        Returns:
            A parser that can handle the domain, or None for generic parsing.
        """
        for parser in self._parsers:
            if parser.can_handle(domain):
                return parser
        return None

    def has_parser(self, domain: str) -> bool:
        """Check if a domain-specific parser exists for the domain."""
        return self.get_parser(domain) is not None


# Global registry instance
domain_parser_registry = DomainParserRegistry()


def register_parser(parser: BaseDomainParser) -> None:
    """Convenience function to register a parser to the global registry."""
    domain_parser_registry.register(parser)
