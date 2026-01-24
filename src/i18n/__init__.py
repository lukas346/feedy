"""Internationalization (i18n) module for the Feedy application."""

import json
from pathlib import Path
from typing import Any, Callable, Optional

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
SUPPORTED_LANGUAGES = ["en", "pl"]
DEFAULT_LANGUAGE = "en"

_translations: dict[str, dict[str, Any]] = {}


def load_translations() -> None:
    """Load all translation files into memory."""
    global _translations  # noqa: F824
    for lang in SUPPORTED_LANGUAGES:
        file_path = TRANSLATIONS_DIR / f"{lang}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)


def get_translation(lang: str, key: str, **kwargs: str) -> str:
    """
    Get a translation string by key.

    Key format: "section.subsection.key" (e.g., "nav.feeds", "settings_page.title")
    Supports variable interpolation with {variable_name} syntax.

    Args:
        lang: Language code (e.g., "en", "pl")
        key: Dot-separated key path
        **kwargs: Variables to interpolate

    Returns:
        Translated string, or the key itself if not found
    """
    if lang not in _translations:
        lang = DEFAULT_LANGUAGE

    translations = _translations.get(lang, _translations.get(DEFAULT_LANGUAGE, {}))

    # Navigate nested keys
    keys = key.split(".")
    value: Any = translations
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, None)
        else:
            value = None
            break

    # Fallback to English if key not found
    if value is None and lang != DEFAULT_LANGUAGE:
        return get_translation(DEFAULT_LANGUAGE, key, **kwargs)

    if value is None:
        return key  # Return key itself as last resort

    if not isinstance(value, str):
        return key

    # Interpolate variables
    result: str = value
    if kwargs:
        for var_name, var_value in kwargs.items():
            result = result.replace(f"{{{var_name}}}", str(var_value))

    return result


def parse_accept_language(header: Optional[str]) -> str:
    """
    Parse Accept-Language header and return best matching language.

    Example: "pl,en;q=0.9,en-US;q=0.8" -> "pl"

    Args:
        header: Accept-Language header value

    Returns:
        Best matching supported language code
    """
    if not header:
        return DEFAULT_LANGUAGE

    languages: list[tuple[str, float]] = []
    for part in header.split(","):
        part = part.strip()
        if ";q=" in part:
            lang, q = part.split(";q=")
            try:
                quality = float(q)
            except ValueError:
                quality = 0.0
        else:
            lang = part
            quality = 1.0

        # Extract base language (en-US -> en)
        lang = lang.split("-")[0].lower()
        languages.append((lang, quality))

    # Sort by quality descending
    languages.sort(key=lambda x: x[1], reverse=True)

    # Return first supported language
    for lang, _ in languages:
        if lang in SUPPORTED_LANGUAGES:
            return lang

    return DEFAULT_LANGUAGE


def create_t_function(lang: str) -> Callable[..., str]:
    """
    Create a translation function bound to a specific language.

    This is used to pass a `t()` function to Jinja2 templates.

    Args:
        lang: Language code

    Returns:
        Translation function that takes a key and optional kwargs
    """

    def t(key: str, **kwargs: str) -> str:
        return get_translation(lang, key, **kwargs)

    return t


# Load translations on module import
load_translations()
