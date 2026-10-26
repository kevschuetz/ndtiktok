"""Review decisions and per-claim acks, keyed on script_sha256 (SCR-03). CLI, web (and M2
Telegram) all write through here; the gate is re-evaluated inside the write transaction."""

from ndc.db import Database
from ndc.review.gate import gate, is_latest

DECISIONS = ("approved", "rejected", "changes_requested")
CHANNELS = ("cli", "web", "telegram")


class ReviewRefused(Exception):
    pass


def version_by_sha(conn, sha: str):
    v = conn.execute("SELECT * FROM script_version WHERE sha256 = ?", (sha,)).fetchone()
    if v is None:
        raise ReviewRefused("Version nicht gefunden")
    return v


def _note_ok(note: str | None) -> bool:
    return bool(note and len(note.strip()) >= 5)


def ack(
    db: Database,
    sha: str,
    sentence_ordinal: int,
    reviewer: str = "operator",
    note: str | None = None,
    channel: str = "cli",
) -> None:
    if channel not in CHANNELS:
        raise ReviewRefused(f"unbekannter Kanal {channel}")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            v = version_by_sha(conn, sha)
            if not is_latest(conn, v):
                raise ReviewRefused("veraltet — es gibt eine neuere Version")
            res = gate(db, v["id"], conn=conn)
            if sentence_ordinal not in {i.sentence_ordinal for i in res.needs_ack}:
                raise ReviewRefused(f"Satz {sentence_ordinal} braucht keine Bestätigung")
            conn.execute(
                "INSERT INTO claim_ack (script_sha256, sentence_ordinal, reviewer, channel, note) "
                "VALUES (?,?,?,?,?)",
                (sha, sentence_ordinal, reviewer, channel, (note or "").strip() or None),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def decide(
    db: Database,
    sha: str,
    decision: str,
    reviewer: str = "operator",
    note: str | None = None,
    channel: str = "cli",
) -> int:
    if decision not in DECISIONS:
        raise ReviewRefused(f"unbekannte Entscheidung {decision}")
    if channel not in CHANNELS:
        raise ReviewRefused(f"unbekannter Kanal {channel}")
    if decision != "approved" and not _note_ok(note):
        raise ReviewRefused("Bitte kurz begründen.")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            v = version_by_sha(conn, sha)
            if not is_latest(conn, v):
                raise ReviewRefused("veraltet — es gibt eine neuere Version")
            if decision == "approved":
                res = gate(db, v["id"], conn=conn)
                if not res.approvable:
                    msgs = [i.message_de for i in res.blockers + res.needs_ack]
                    raise ReviewRefused("nicht freigebbar: " + "; ".join(msgs))
            rid = conn.execute(
                "INSERT INTO review (script_sha256, decision, reviewer, channel, note) "
                "VALUES (?,?,?,?,?)",
                (sha, decision, reviewer, channel, (note or "").strip() or None),
            ).lastrowid
            conn.execute("COMMIT")
            return rid
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def latest_decision(db_or_conn, sha: str):
    own = isinstance(db_or_conn, Database)
    conn = db_or_conn.connect() if own else db_or_conn
    try:
        return conn.execute(
            "SELECT * FROM review WHERE script_sha256 = ? ORDER BY id DESC LIMIT 1", (sha,)
        ).fetchone()
    finally:
        if own:
            conn.close()
