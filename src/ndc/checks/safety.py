"""Safety filter (CONT-04): blacklisted subjects, identical at topic/script/claim level."""

from ndc.checks._match import apply_rules
from ndc.checks.models import Finding
from ndc.checks.rules import load_safety


def check_safety(text: str, lang: str, level: str) -> list[Finding]:
    cfg = load_safety()
    if level not in ("topic", "script", "claim"):
        raise ValueError(f"unknown level {level!r}")
    rules = [r for r in cfg.rules if level in (r.levels or cfg.levels)]
    return apply_rules(text, lang, rules, "safety")
