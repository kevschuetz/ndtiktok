"""check(text, lang, level) -> CheckResult, plus hash-bound overrides for warn findings."""

import hashlib
from typing import Literal

from ndc.checks.models import CheckResult, Finding
from ndc.checks.rules import load_terminology
from ndc.checks.safety import check_safety
from ndc.checks.terminology import check_terminology
from ndc.checks.text import nfc
from ndc.db import Database

__all__ = ["check", "CheckResult", "Finding", "text_sha256"]


def text_sha256(text: str) -> str:
    return hashlib.sha256(nfc(text).encode("utf-8")).hexdigest()


def check(
    text: str,
    lang: Literal["de", "en"],
    level: Literal["topic", "script", "claim"],
    db: Database | None = None,
) -> CheckResult:
    if lang not in ("de", "en"):
        raise ValueError(f"unknown lang {lang!r}")
    findings = sorted(
        check_safety(text, lang, level) + check_terminology(text, lang),
        key=lambda f: (f.span[0], f.rule_id),
    )
    digest = text_sha256(text)
    version = load_terminology().version
    warn_ids = {f.rule_id for f in findings if f.tier == "warn"}
    overridden: list[str] = []
    if db is not None and warn_ids:
        overridden = sorted(warn_ids & _overrides_for(db, digest))
    if any(f.tier == "block" for f in findings):
        status = "blocked"
    elif warn_ids - set(overridden):
        status = "needs_override"
    else:
        status = "ok"
    return CheckResult(status, findings, digest, version, overridden)


def _overrides_for(db: Database, digest: str) -> set[str]:
    conn = db.connect()
    try:
        rows = conn.execute("SELECT rule_id FROM check_override WHERE text_sha256 = ?", (digest,))
        return {r[0] for r in rows}
    finally:
        conn.close()
