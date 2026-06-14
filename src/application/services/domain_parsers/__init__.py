"""Domain-specific content parsers.

Provides specialized parsers for specific domains like Wikipedia, GitHub,
and video platforms that extract content more accurately than generic parsers.
"""

from .antirez import AntirezParser
from .base import BaseDomainParser, DomainParser
from .github import GitHubParser
from .hey_world import HeyWorldParser
from .medium import MediumParser
from .ppe import PPEParser
from .seangoedecke import SeanGoedeckeParser
from .registry import (
    DomainParserRegistry,
    domain_parser_registry,
    register_parser,
)
from .substack import SubstackParser
from .tjll import TJLLBlogParser
from .video import VideoEmbedParser
from .wikipedia import WikipediaParser

# Register built-in parsers
register_parser(AntirezParser())
register_parser(WikipediaParser())
register_parser(GitHubParser())
register_parser(MediumParser())
register_parser(VideoEmbedParser())
register_parser(HeyWorldParser())
register_parser(SeanGoedeckeParser())
register_parser(SubstackParser())
register_parser(TJLLBlogParser())
register_parser(PPEParser())

__all__ = [
    "AntirezParser",
    "BaseDomainParser",
    "DomainParser",
    "DomainParserRegistry",
    "domain_parser_registry",
    "register_parser",
    "WikipediaParser",
    "GitHubParser",
    "HeyWorldParser",
    "MediumParser",
    "PPEParser",
    "SeanGoedeckeParser",
    "SubstackParser",
    "TJLLBlogParser",
    "VideoEmbedParser",
]
