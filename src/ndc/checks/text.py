"""Offset-preserving text normalization, quote stripping, tokenizing and lemmatizing.

Every transformation after NFC keeps string length, so spans found on a derived string
point at the same characters in the NFC text that the caller sees.
"""

import re
import unicodedata
from functools import lru_cache

import simplemma

# Typographic dashes -> ASCII hyphen (1:1, length-preserving).
_DASHES = str.maketrans({c: "-" for c in "‐‑‒–—−"})

# Balanced quote pairs whose content is blanked for allow_in_quotes rules.
# ASCII ' and typographic ' (U+2019) are deliberately absent: they double as apostrophes
# ("Asperger's", "it's"), so treating them as quotes would hide real findings.
QUOTE_PAIRS: list[tuple[str, str]] = [
    ("„", "“"),  # „…“
    ('"', '"'),
    ("“", "”"),  # “…”
    ("»", "«"),  # »…«
    ("«", "»"),  # «…»
    ("‚", "‘"),  # ‚…‘
]
_QUOTE_RES = [
    re.compile(re.escape(o) + "[^" + re.escape(c) + "\n]*" + re.escape(c)) for o, c in QUOTE_PAIRS
]
TOKEN_RE = re.compile(r"\w+(?:-\w+)*")


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize(text: str) -> str:
    """NFC + dash normalization. Callers should pass the result of nfc() for stable spans."""
    return nfc(text).translate(_DASHES)


def strip_quoted(text: str) -> str:
    """Blank the content of balanced quote pairs (same length). Unbalanced quotes stay."""
    for rx in _QUOTE_RES:
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    return text


@lru_cache(maxsize=50_000)
def _lemma(token: str, lang: str) -> str:
    return simplemma.lemmatize(token, lang=lang).lower()


def tokens(text: str, lang: str) -> list[tuple[str, str, int, int]]:
    """(lowercased surface, lowercased lemma, start, end) for every token."""
    return [
        (m.group(0).lower(), _lemma(m.group(0), lang), m.start(), m.end())
        for m in TOKEN_RE.finditer(text)
    ]
