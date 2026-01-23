"""URL filter service to identify and filter out non-article links."""

import re
from typing import Optional
from urllib.parse import urlparse, parse_qs


class URLFilter:
    """Filters URLs to identify non-article links that should be ignored."""

    # URL path patterns that indicate non-article pages
    NON_ARTICLE_PATH_PATTERNS: list[re.Pattern[str]] = [
        # Category/tag/topic pages
        re.compile(
            r"/(?:tag|tags|category|categories|topic|topics|label|labels)/", re.I
        ),
        re.compile(r"/(?:tagged|categorized)/", re.I),
        # Author/profile pages
        re.compile(
            r"/(?:author|authors|profile|profiles|user|users|contributor|contributors)/",
            re.I,
        ),
        re.compile(r"/(?:by|written-by)/[^/]+/?$", re.I),
        # Archive/listing pages
        re.compile(r"/(?:archive|archives)/", re.I),
        re.compile(r"/\d{4}/\d{2}/?$", re.I),  # Date archives like /2024/01/
        re.compile(r"/\d{4}/?$", re.I),  # Year archives like /2024/
        # Pagination
        re.compile(r"/page/\d+", re.I),
        re.compile(r"/p/\d+", re.I),
        # Comments
        re.compile(r"/comments?/?$", re.I),
        re.compile(r"#comments?$", re.I),
        re.compile(r"#respond$", re.I),
        re.compile(r"#reply", re.I),
        # Search pages
        re.compile(r"/search/?", re.I),
        re.compile(r"/results/?", re.I),
        # Login/auth pages
        re.compile(
            r"/(?:login|signin|sign-in|signup|sign-up|register|auth|authenticate)/",
            re.I,
        ),
        re.compile(r"/(?:logout|signout|sign-out)/", re.I),
        # Static pages
        re.compile(
            r"/(?:about|about-us|contact|contact-us|privacy|privacy-policy)/", re.I
        ),
        re.compile(r"/(?:terms|terms-of-service|tos|legal|disclaimer)/", re.I),
        re.compile(r"/(?:faq|help|support|sitemap)/", re.I),
        re.compile(r"/(?:advertise|advertising|sponsors|careers|jobs)/", re.I),
        # Feed pages
        re.compile(r"/(?:feed|feeds|rss|atom|xml)/?$", re.I),
        re.compile(r"\.(?:rss|atom|xml)$", re.I),
        # Print/share versions
        re.compile(r"/print/?$", re.I),
        re.compile(r"/(?:share|email|forward)/?$", re.I),
        re.compile(r"\?(?:.*&)?print=", re.I),
        # Subscription/newsletter pages
        re.compile(r"/(?:subscribe|subscription|newsletter|unsubscribe)/", re.I),
        # Media/attachment pages (not article content)
        re.compile(
            r"/(?:attachment|media|gallery|galleries|photos|images|videos)/\d+", re.I
        ),
        # Shop/commerce pages
        re.compile(r"/(?:shop|store|cart|checkout|product|products)/", re.I),
        # Homepage indicators
        re.compile(r"^/?$"),  # Root path
        re.compile(r"/(?:home|index)/?$", re.I),
    ]

    # Query parameter patterns that indicate non-article pages
    NON_ARTICLE_QUERY_PATTERNS: list[tuple[str, Optional[re.Pattern[str]]]] = [
        ("page", re.compile(r"^\d+$")),  # Pagination
        ("p", re.compile(r"^\d+$")),  # WordPress pagination
        ("paged", re.compile(r"^\d+$")),
        ("cat", None),  # Category filter
        ("tag", None),  # Tag filter
        ("author", None),  # Author filter
        ("s", None),  # Search query
        ("q", None),  # Search query
        ("search", None),  # Search query
        ("action", re.compile(r"^(?:login|logout|register)$", re.I)),
        ("replytocom", None),  # Reply to comment
        ("share", None),  # Share action
        ("utm_source", None),  # Tracking params (not disqualifying alone, but noted)
    ]

    # File extensions that are not articles
    NON_ARTICLE_EXTENSIONS: list[str] = [
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".zip",
        ".rar",
        ".tar",
        ".gz",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".exe",
        ".dmg",
        ".apk",
        ".rss",
        ".atom",
        ".xml",
    ]

    # Domains/subdomains that typically don't host articles
    NON_ARTICLE_SUBDOMAINS: list[str] = [
        "shop.",
        "store.",
        "cart.",
        "checkout.",
        "login.",
        "auth.",
        "account.",
        "accounts.",
        "mail.",
        "email.",
        "cdn.",
        "static.",
        "assets.",
        "media.",
        "images.",
        "img.",
        "api.",
        "feeds.",
        "rss.",
        "ads.",
        "ad.",
        "tracking.",
    ]

    def is_article_url(self, url: str) -> bool:
        """
        Check if a URL appears to be an article link.

        Args:
            url: The URL to check

        Returns:
            True if the URL appears to be an article, False otherwise
        """
        if not url:
            return False

        try:
            parsed = urlparse(url)
        except Exception:
            return False

        # Check scheme
        if parsed.scheme not in ("http", "https"):
            return False

        # Check for non-article subdomains
        hostname = parsed.netloc.lower()
        for subdomain in self.NON_ARTICLE_SUBDOMAINS:
            if hostname.startswith(subdomain):
                return False

        # Check file extension
        path_lower = parsed.path.lower()
        for ext in self.NON_ARTICLE_EXTENSIONS:
            if path_lower.endswith(ext):
                return False

        # Check path patterns
        full_path = parsed.path
        if parsed.fragment:
            full_path += "#" + parsed.fragment

        for pattern in self.NON_ARTICLE_PATH_PATTERNS:
            if pattern.search(full_path):
                return False

        # Check query parameters
        if parsed.query:
            query_params = parse_qs(parsed.query)
            for param, value_pattern in self.NON_ARTICLE_QUERY_PATTERNS:
                if param in query_params:
                    values = query_params[param]
                    # If no pattern specified, presence of param is enough to filter
                    if value_pattern is None:
                        # Some params like utm_* are not disqualifying alone
                        if param not in ("utm_source", "utm_medium", "utm_campaign"):
                            return False
                    else:
                        # Check if any value matches the pattern
                        for val in values:
                            if value_pattern.match(val):
                                return False

        return True

    def get_rejection_reason(self, url: str) -> Optional[str]:
        """
        Get the reason why a URL was rejected, if any.

        Args:
            url: The URL to check

        Returns:
            A string describing why the URL was rejected, or None if it's valid
        """
        if not url:
            return "Empty URL"

        try:
            parsed = urlparse(url)
        except Exception as e:
            return f"Invalid URL: {e}"

        if parsed.scheme not in ("http", "https"):
            return f"Invalid scheme: {parsed.scheme}"

        hostname = parsed.netloc.lower()
        for subdomain in self.NON_ARTICLE_SUBDOMAINS:
            if hostname.startswith(subdomain):
                return f"Non-article subdomain: {subdomain}"

        path_lower = parsed.path.lower()
        for ext in self.NON_ARTICLE_EXTENSIONS:
            if path_lower.endswith(ext):
                return f"Non-article file extension: {ext}"

        full_path = parsed.path
        if parsed.fragment:
            full_path += "#" + parsed.fragment

        for pattern in self.NON_ARTICLE_PATH_PATTERNS:
            if pattern.search(full_path):
                return f"Non-article path pattern: {pattern.pattern}"

        if parsed.query:
            query_params = parse_qs(parsed.query)
            for param, value_pattern in self.NON_ARTICLE_QUERY_PATTERNS:
                if param in query_params:
                    if value_pattern is None:
                        if param not in ("utm_source", "utm_medium", "utm_campaign"):
                            return f"Non-article query parameter: {param}"
                    else:
                        for val in query_params[param]:
                            if value_pattern.match(val):
                                return f"Non-article query parameter: {param}={val}"

        return None


# Singleton instance for convenience
url_filter = URLFilter()
