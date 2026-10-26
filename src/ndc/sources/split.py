"""Sentence splitting for source and script text (pysbd, rule-based, DE + EN)."""

import re
import unicodedata
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    import pysbd

_MIN_WORDS = 3
_SEGMENTERS: dict[str, "pysbd.Segmenter"] = {}


def _segmenter(lang: str) -> "pysbd.Segmenter":
    if lang not in ("de", "en"):
        raise ValueError(f"unknown lang {lang!r}")
    if lang not in _SEGMENTERS:
        _SEGMENTERS[lang] = pysbd.Segmenter(language=lang, clean=False)
    return _SEGMENTERS[lang]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def split_sentences(text: str, lang: str) -> list[str]:
    """Split text into sentences; drop fragments under three words."""
    text = normalize(text)
    if not text:
        return []
    out = []
    for s in _segmenter(lang).segment(text):
        s = s.strip()
        if len(s.split()) >= _MIN_WORDS:
            out.append(s)
    return out
