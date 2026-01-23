"""Domain extraction utilities for URL processing."""

from urllib.parse import urlparse


def extract_domain(url: str) -> str | None:
    """Extract and normalize domain from a URL.

    Args:
        url: Full URL string (e.g., "https://www.example.com/path")

    Returns:
        Normalized domain (lowercase, no www. prefix) or None if invalid.
        Example: "example.com"
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.lower()

        # Strip www. prefix for consistency
        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname if hostname else None
    except Exception:
        return None
