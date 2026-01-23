"""URL and input validation services."""

from urllib.parse import urlparse


def validate_url(url: str) -> bool:
    """
    Validate that a URL is safe and well-formed.

    Args:
        url: The URL string to validate.

    Returns:
        True if the URL is valid and safe, False otherwise.

    Examples:
        >>> validate_url("https://example.com/feed")
        True
        >>> validate_url("javascript:alert(1)")
        False
        >>> validate_url("file:///etc/passwd")
        False
    """
    if not url or not isinstance(url, str):
        return False

    # Parse the URL
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return False

    # Only allow http and https schemes
    allowed_schemes = {"http", "https"}
    if parsed.scheme.lower() not in allowed_schemes:
        return False

    # Must have a netloc (domain)
    if not parsed.netloc:
        return False

    # Block localhost and internal IPs for SSRF protection
    dangerous_hosts = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
    }
    host = parsed.netloc.split(":")[0].lower()
    if host in dangerous_hosts:
        return False

    # Block private IP ranges (basic check)
    if host.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.")):
        return False

    return True
