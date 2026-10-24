"""check(text, lang, level) -> CheckResult, plus hash-bound overrides for warn findings."""

import hashlib
from datetime import UTC, datetime
from typing import Literal

from ndc.checks.models import CheckResult, Finding
from ndc.checks.rules import load_safety, load_terminology
from ndc.checks.safety import check_safety
from ndc.checks.terminology import check_terminology
from ndc.checks.text import nfc
from ndc.db import Database

__all__ = ["check", "CheckResult", "Finding", "record_override", "rule_tier", "text_sha256"]


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
        overridden = sorted(_overrides_for(db, digest, warn_ids))
    if any(f.tier == "block" for f in findings):
        status = "blocked"
    elif warn_ids - set(overridden):
        status = "needs_override"
    else:
        status = "ok"
    return CheckResult(status, findings, digest, version, overridden)


def _overrides_for(db: Database, digest: str, rule_ids: set[str]) -> set[str]:
    conn = db.connect()
    try:
        return {
            rid
            for rid in rule_ids
            if conn.execute(
                "SELECT 1 FROM check_override WHERE text_sha256 = ? AND rule_id = ?",
                (digest, rid),
            ).fetchone()
        }
    finally:
        conn.close()


def rule_tier(rule_id: str) -> str | None:
    """Tier of a rule in either file, or None if the id is unknown."""
    for r in load_terminology().terms:
        if r.id == rule_id:
            return r.tier
    for r in load_safety().rules:
        if r.id == rule_id:
            return r.tier
    return None


def record_override(db: Database, text: str, rule_id: str, level: str, reason: str) -> None:
    """Record a warn-tier override bound to this exact text (sha256 of NFC text).

    Raises ValueError for unknown or block-tier rules (D-12: block is never overridable),
    an unknown level, or a reason shorter than 5 characters.
    """
    tier = rule_tier(rule_id)
    if tier is None:
        raise ValueError(f"unknown rule_id {rule_id!r}")
    if tier == "block":
        raise ValueError(f"{rule_id} is a block finding; block findings cannot be overridden")
    if level not in ("topic", "script", "claim"):
        raise ValueError(f"unknown level {level!r}")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("override reason must be at least 5 characters")
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO check_override (text_sha256, rule_id, level, reason, "
            "terminology_version, created_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (text_sha256, rule_id) DO UPDATE SET level = excluded.level, "
            "reason = excluded.reason, terminology_version = excluded.terminology_version, "
            "created_at = excluded.created_at",
            (
                text_sha256(text),
                rule_id,
                level,
                reason,
                load_terminology().version,
                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
    finally:
        conn.close()
