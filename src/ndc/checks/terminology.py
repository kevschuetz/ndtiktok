"""Terminology check (CONT-03): pure function over config/terminology.yaml."""

from ndc.checks._match import apply_rules
from ndc.checks.models import Finding
from ndc.checks.rules import load_terminology


def check_terminology(text: str, lang: str) -> list[Finding]:
    return apply_rules(text, lang, load_terminology().terms, "terminology")
