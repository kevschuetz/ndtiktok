"""Pre-registered go/no-go readout rule (MEAS-01). Same discipline as scan/prereg.py:

- config/readout_rule.yaml is the rule; `lock()` writes config/readout_rule.lock (sha256,
  committed_at) AND a readout_rule DB row, so "committed before video 1" is provable.
- `check_locked()` refuses when no row exists or the file no longer matches the latest row;
  `amend()` logs a new row (old -> new sha) with a reason of >= 5 characters.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ndc.config import config_dir
from ndc.db import Database

RULE_FILE = "readout_rule.yaml"
LOCK_FILE = "readout_rule.lock"


class ReadoutNotLocked(Exception):
    pass


class ReadoutChanged(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def rule_path(cfg: str | Path | None = None) -> Path:
    return Path(cfg or config_dir()) / RULE_FILE


def lock_path(cfg: str | Path | None = None) -> Path:
    return Path(cfg or config_dir()) / LOCK_FILE


def load_rule(cfg: str | Path | None = None) -> dict:
    data = yaml.safe_load(rule_path(cfg).read_text(encoding="utf-8")) or {}
    for key in ("primary_variable", "arms", "snapshot_of_record", "min_exposure_views", "winner"):
        if key not in data:
            raise ValueError(f"readout_rule.yaml: missing '{key}'")
    if data["primary_variable"] != "pillar" or len(data["arms"]) != 4:
        raise ValueError("readout_rule.yaml: pillar must be the only primary variable (4 arms)")
    return data


def rule_sha(cfg: str | Path | None = None) -> str:
    return hashlib.sha256(rule_path(cfg).read_bytes()).hexdigest()


def latest_row(conn):
    return conn.execute("SELECT * FROM readout_rule ORDER BY id DESC LIMIT 1").fetchone()


def _write_lock(data: dict, cfg, lock_out: str | Path | None) -> Path:
    """Write the lock JSON. The config dir is read-only inside the container, so `lock_out`
    (e.g. /data) can receive the file for the operator to copy into config/."""
    target = Path(lock_out) / LOCK_FILE if lock_out else lock_path(cfg)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return target


def lock(db: Database, cfg: str | Path | None = None, lock_out: str | Path | None = None) -> dict:
    """First commit of the rule. Refuses if a row already exists (use amend).
    The lock file is written first (fails fast on a read-only config dir), then the DB row."""
    rule = load_rule(cfg)
    sha = rule_sha(cfg)
    conn = db.connect()
    try:
        if latest_row(conn) is not None:
            raise ReadoutChanged("rule is already locked — use `ndc readout amend --reason`")
        now = _now()
        data = {
            "sha256": sha,
            "committed_at": now,
            "rule_file": RULE_FILE,
            "version": rule.get("version", 1),
        }
        _write_lock(data, cfg, lock_out)
        conn.execute(
            "INSERT INTO readout_rule (version, sha256, committed_at) VALUES (?, ?, ?)",
            (int(rule.get("version", 1)), sha, now),
        )
    finally:
        conn.close()
    return data


def check_locked(conn, cfg: str | Path | None = None) -> str:
    """Return the committed sha; raise when unlocked or changed."""
    row = latest_row(conn)
    if row is None:
        raise ReadoutNotLocked("Readout-Regel ist nicht gesperrt (ndc readout lock)")
    current = rule_sha(cfg)
    if row["sha256"] != current:
        raise ReadoutChanged(
            f"readout_rule.yaml geändert ({row['sha256'][:12]} -> {current[:12]}) — "
            "ndc readout amend --reason '...' oder Datei zurücksetzen"
        )
    lp = lock_path(cfg)
    if not lp.is_file() or json.loads(lp.read_text(encoding="utf-8")).get("sha256") != current:
        raise ReadoutChanged("readout_rule.lock fehlt oder passt nicht zur Datei")
    return current


def amend(
    db: Database, reason: str, cfg: str | Path | None = None, lock_out: str | Path | None = None
) -> dict:
    if len((reason or "").strip()) < 5:
        raise ValueError("amendment reason must be at least 5 characters")
    rule = load_rule(cfg)
    sha = rule_sha(cfg)
    conn = db.connect()
    try:
        prev = latest_row(conn)
        if prev is None:
            raise ReadoutNotLocked("nothing to amend — lock first")
        if prev["sha256"] == sha:
            raise ReadoutChanged("rule unchanged — nothing to amend")
        now = _now()
        data = {
            "sha256": sha,
            "committed_at": now,
            "rule_file": RULE_FILE,
            "version": rule.get("version", 1),
        }
        _write_lock(data, cfg, lock_out)
        conn.execute(
            "INSERT INTO readout_rule (version, sha256, committed_at, amended_from, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (int(rule.get("version", 1)), sha, now, prev["id"], reason.strip()),
        )
    finally:
        conn.close()
    return data


def status(conn, cfg: str | Path | None = None) -> dict:
    row = latest_row(conn)
    out = {"locked": row is not None, "file_sha256": rule_sha(cfg)}
    if row is not None:
        out |= {
            "sha256": row["sha256"],
            "committed_at": row["committed_at"],
            "amended": row["amended_from"] is not None,
            "matches_file": row["sha256"] == out["file_sha256"],
        }
    return out
