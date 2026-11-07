"""
Accent-insensitive, case-insensitive, word-boundary-safe text matching,
used by the banned-word tracker (so "café" matches "cafe", "CAFE!" etc.,
but "scaffold" does NOT match a banned word "caffo").
"""
import re
import unicodedata


def normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return stripped.lower()


def contains_word(haystack: str, needle: str) -> bool:
    """True if `needle` (a word or short phrase) appears in `haystack` on its own,
    not merely as part of a longer word (e.g. "class" never matches "ass")."""
    pattern = r"\b" + re.escape(normalize(needle)) + r"\b"
    return re.search(pattern, normalize(haystack)) is not None
