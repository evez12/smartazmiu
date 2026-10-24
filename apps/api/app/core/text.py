"""Azerbaijani-aware text normalization (§5.7.1), shared by search, import matching and moderation."""

import re
import unicodedata
from dataclasses import dataclass

# Zero-width characters and the soft hyphen are invisible but break matching ("Mikro\u200biqtisadiyyat").
_INVISIBLE = re.compile("[\u00ad\u180e\u200b-\u200f\u2060-\u2064\ufeff]")
_WHITESPACE = re.compile(r"\s+")
_ASCII_FOLD = str.maketrans({"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ç": "c", "ş": "s", "ğ": "g"})


@dataclass(frozen=True, slots=True)
class NormalizedText:
    exact: str
    """Lower-cased with Azerbaijani rules, diacritics kept."""
    folded: str
    """ASCII-folded, so text typed without Azerbaijani letters still matches."""


def lower_az(text: str) -> str:
    """Lower-case with Azerbaijani rules: ``İ → i`` and ``I → ı`` (Python's default maps ``I → i``)."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def normalize_az(text: str) -> NormalizedText:
    cleaned = _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))
    exact = _WHITESPACE.sub(" ", lower_az(cleaned)).strip()
    return NormalizedText(exact=exact, folded=exact.translate(_ASCII_FOLD))


def search_key(*parts: str | None) -> str:
    """Folded form of several fields, used for substring search over names and identifiers."""
    return normalize_az(" ".join(part for part in parts if part)).folded
