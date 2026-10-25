"""Pre-registration guard for the language decision rule (MKT-02, D-20).

- config/decision_rule.lock (JSON: sha256, approved_by, approved_at, rule_file) is written only
  after operator approval; assert_rule_approved() gates every scan fetch.
- The first scan_run row stores the hash the scan ran under. check_rule_unchanged() refuses a
  different rule unless an amendment reason is given, which is logged in rule_amendment.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ndc.config import config_dir as _config_dir
from ndc.db import Database

RULE_FILE = "decision_rule.yaml"
LOCK_FILE = "decision_rule.lock"


class RuleNotApproved(Exception):
    pass


class RuleChanged(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def rule_path(cfg: str | Path | None = None) -> Path:
    return Path(cfg or _config_dir()) / RULE_FILE


def rule_sha256(cfg: str | Path | None = None) -> str:
    return hashlib.sha256(rule_path(cfg).read_bytes()).hexdigest()


def lock_status(cfg: str | Path | None = None) -> str:
    """'ok', 'missing', or 'invalid: <why>' — never raises."""
    try:
        assert_rule_approved(cfg)
        return "ok"
    except RuleNotApproved as exc:
        msg = str(exc)
        return "missing" if msg == "missing" else f"invalid: {msg}"


def assert_rule_approved(cfg: str | Path | None = None) -> str:
    lock = Path(cfg or _config_dir()) / LOCK_FILE
    if not lock.is_file():
        raise RuleNotApproved("missing")
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuleNotApproved(f"unreadable lock ({exc})") from exc
    current = rule_sha256(cfg)
    if data.get("sha256") != current:
        raise RuleNotApproved("lock sha256 does not match decision_rule.yaml")
    if not data.get("approved_at"):
        raise RuleNotApproved("lock has no approved_at")
    return current


def record_scan_run(db: Database, stage: str, cfg: str | Path | None = None) -> int:
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO scan_run (stage, started_at, rule_sha256) VALUES (?, ?, ?)",
            (stage, _now(), rule_sha256(cfg)),
        )
        return cur.lastrowid
    finally:
        conn.close()


def _reference_sha(conn) -> str | None:
    amended = conn.execute(
        "SELECT new_sha256 FROM rule_amendment ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if amended:
        return amended[0]
    first = conn.execute("SELECT rule_sha256 FROM scan_run ORDER BY id LIMIT 1").fetchone()
    return first[0] if first else None


def check_rule_unchanged(
    db: Database, amend_reason: str | None, cfg: str | Path | None = None
) -> int | None:
    """No scan_run yet -> nothing to compare. Otherwise the current hash must equal the first
    scan_run's hash (or the latest amendment's new hash); else an amendment reason is required.
    Returns the id of the rule_amendment row logged by this call, or None."""
    current = rule_sha256(cfg)
    conn = db.connect()
    try:
        ref = _reference_sha(conn)
        if ref is None or ref == current:
            return None
        if amend_reason is None:
            raise RuleChanged(
                f"decision rule changed after the first scan run ({ref[:12]} -> {current[:12]}); "
                'pass --amend "reason" to log an amendment'
            )
        if len(amend_reason.strip()) < 5:
            raise ValueError("amendment reason must be at least 5 characters")
        cur = conn.execute(
            "INSERT INTO rule_amendment (old_sha256, new_sha256, reason, created_at)"
            " VALUES (?, ?, ?, ?)",
            (ref, current, amend_reason.strip(), _now()),
        )
        return cur.lastrowid
    finally:
        conn.close()
