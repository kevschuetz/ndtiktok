"""Operator spot-check (D-01, D-17): list the queue, then set any field as operator_verified.

Operator values win in v_competitor_sheet. Each verify also writes an `operator_review` obs, so the
queue stays clear until a newer machine observation arrives.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import get_args

from ndc.db import Database
from ndc.scan import judging, queue
from ndc.scan.decide import AccountRow

_FACE = set(get_args(AccountRow.model_fields["face"].annotation))
_VOICE = set(get_args(AccountRow.model_fields["voice_gender"].annotation))
_LIST_FIELDS = {
    "pillars": set(get_args(judging.Pillar)),
    "audiences": set(get_args(judging.Audience)),
    "monetization_signals": set(get_args(judging.Monetization)),
}
_ENUM_FIELDS = {
    "face": _FACE,
    "voice_gender": _VOICE,
    "format": set(get_args(judging.Format)),
    "hedging_or_diagnostic": set(get_args(judging.Hedging)),
}
SETTABLE = ("source_citing_score", *_ENUM_FIELDS, *_LIST_FIELDS)
SHOWN = (
    "source_text_level",
    "source_video_level",
    "face",
    "visible_speaker_gender",
    "voice_gender",
    "format",
    "pillars",
    "audiences",
    "monetization_signals",
    "hedging_or_diagnostic",
)


class VerifyError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_set(item: str) -> tuple[str, str]:
    name, sep, value = item.partition("=")
    name, value = name.strip(), value.strip()
    if not sep or not name:
        raise VerifyError(f"--set expects FIELD=VALUE, got {item!r}")
    if name not in SETTABLE:
        raise VerifyError(f"unknown field {name!r}; settable: {', '.join(SETTABLE)}")
    if name == "source_citing_score":
        if value not in ("0", "1", "2", "3"):
            raise VerifyError("source_citing_score must be 0, 1, 2 or 3")
    elif name in _ENUM_FIELDS:
        if value not in _ENUM_FIELDS[name]:
            raise VerifyError(f"{name} must be one of {', '.join(sorted(_ENUM_FIELDS[name]))}")
    else:
        parts = [p.strip() for p in value.split(",") if p.strip()]
        bad = [p for p in parts if p not in _LIST_FIELDS[name]]
        if bad or not parts:
            raise VerifyError(
                f"{name} takes a comma list of {', '.join(sorted(_LIST_FIELDS[name]))}"
            )
        if name == "monetization_signals" and "none" in parts and len(parts) > 1:
            raise VerifyError("monetization_signals: 'none' must be used alone")
        value = ",".join(parts)
    return name, value


def set_fields(
    db: Database,
    handle: str,
    platform: str,
    items: list[str],
    note: str | None,
    accept: bool = False,
) -> tuple[bool, list[str]]:
    """Write operator_verified values. accept=True with no items only logs the operator review,
    keeping the current (machine) values as accepted — the queue clears, no field changes."""
    pairs = [parse_set(i) for i in items]  # validate everything before writing anything
    if not pairs and not accept:
        raise VerifyError("nothing to set; give --set FIELD=VALUE or --accept")
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id FROM competitor_account WHERE platform = ? AND lower(handle) = lower(?)",
            (platform, handle),
        ).fetchone()
        if row is None:
            raise VerifyError(f"unknown account {platform}:{handle}")
        aid = row[0]
        method = f"operator: {note}" if note else "operator"
        if accept:
            method = f"{method} (accepted as is)"
        now = _now()
        conn.execute("BEGIN")
        try:
            for name, value in pairs:
                conn.execute(
                    "INSERT INTO competitor_field_obs (account_id, field, value, provenance,"
                    " confidence, method, observed_at) VALUES (?, ?, ?, 'operator_verified',"
                    " 'high', ?, ?)",
                    (aid, name, value, method, now),
                )
            conn.execute(
                "INSERT INTO competitor_field_obs (account_id, field, value, provenance,"
                " confidence, method, observed_at) VALUES (?, ?, ?, 'operator_verified',"
                " 'high', ?, ?)",
                (aid, queue.REVIEW_FIELD, note or "reviewed", method, now),
            )
            out = queue.recompute_conn(conn, aid, now)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return out
    finally:
        conn.close()


@dataclass
class QueueEntry:
    account_id: int
    key: str
    language: str
    reasons: str
    fields: list  # (field, value, provenance, confidence, method)
    evidence: list  # (source, level, claimed_level, guard_result, evidence)


def list_queue(db: Database) -> list[QueueEntry]:
    conn = db.connect()
    try:
        accounts = conn.execute(
            "SELECT s.account_id, s.handle, s.platform, s.language FROM v_competitor_sheet s"
            " WHERE s.needs_operator_check = 'true'"
            " ORDER BY CASE s.language WHEN 'de' THEN 0 ELSE 1 END, s.platform, s.handle"
        ).fetchall()
        out = []
        for a in accounts:
            aid = a["account_id"]
            reasons = conn.execute(
                "SELECT method FROM competitor_field_obs WHERE account_id = ? AND field = ?"
                " ORDER BY id DESC LIMIT 1",
                (aid, queue.FIELD),
            ).fetchone()
            fields = []
            for f in SHOWN:
                r = conn.execute(
                    "SELECT value, provenance, confidence, method FROM competitor_field_obs"
                    " WHERE account_id = ? AND field = ? ORDER BY observed_at DESC, id DESC"
                    " LIMIT 1",
                    (aid, f),
                ).fetchone()
                if r:
                    fields.append((f, r["value"], r["provenance"], r["confidence"], r["method"]))
            ev = [
                (r["source"], r["level"], r["claimed_level"], r["guard_result"], r["evidence"])
                for r in conn.execute(
                    "SELECT source, level, claimed_level, guard_result, evidence"
                    " FROM competitor_post_citing WHERE account_id = ?"
                    " AND (level > 0 OR guard_result = 'downgraded') ORDER BY id",
                    (aid,),
                )
            ]
            out.append(
                QueueEntry(
                    aid,
                    f"{a['platform']}:{a['handle']}",
                    a["language"],
                    reasons[0] if reasons else "",
                    fields,
                    ev,
                )
            )
        return out
    finally:
        conn.close()
