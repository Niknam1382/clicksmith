"""Tiny translation layer: the English source text is the lookup key."""

from __future__ import annotations

from .translations import TRANSLATIONS

LANGUAGES = {"en": "English", "fa": "فارسی"}
RTL_LANGUAGES = frozenset({"fa", "ar", "he", "ur"})

_current = "en"


def set_language(code: str) -> None:
    global _current
    _current = code if code in LANGUAGES else "en"


def get_language() -> str:
    return _current


def is_rtl(code: str | None = None) -> bool:
    return (code or _current) in RTL_LANGUAGES


def tr(text: str) -> str:
    """Translate *text* into the active language, falling back to the English original."""
    if _current == "en":
        return text
    return TRANSLATIONS.get(_current, {}).get(text, text)
