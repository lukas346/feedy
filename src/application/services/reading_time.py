"""Reading time calculation utilities."""

import math

from bs4 import BeautifulSoup

# Average reading speed in words per minute (conservative estimate)
WORDS_PER_MINUTE = 200


def calculate_reading_time(html_content: str | None) -> int | None:
    """Calculate estimated reading time in minutes from HTML content.

    Args:
        html_content: HTML string containing article content.

    Returns:
        Estimated reading time in minutes (minimum 1), or None if no content.
    """
    if not html_content or not html_content.strip():
        return None

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        if not text:
            return None

        word_count = len(text.split())

        if word_count == 0:
            return None

        # Calculate reading time, minimum 1 minute
        minutes = math.ceil(word_count / WORDS_PER_MINUTE)
        return max(1, minutes)
    except Exception:
        return None
