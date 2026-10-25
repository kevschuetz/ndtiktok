"""needs_operator_check: route only uncertain or decision-relevant accounts to the operator (D-17).

Rules (any one queues the account):
- a low confidence on the latest machine (llm_session / auto) value of any field;
- the pitch-based voice estimate contradicts the visible speaker judged from frames;
- every video download was unavailable (nothing could be analyzed);
- a DACH account whose video level or an on-screen citation lifts the score to >= 2 while the
  text level is < 2 (on-screen / video evidence decides the score);
- a DACH account whose text level is >= 2 (it counts toward N_DE, which decides R1/R3; HI-01);
- an imported evidence string failed the substring guard;
- the account would count toward S_DE or S_EN (score >= 2, faceless, male).
An operator review (`ndc scan verify`) newer than every machine observation clears the flag.
The flag is stored as a field obs (provenance auto, method = the reasons).
"""

from datetime import UTC, datetime

from ndc.db import Database

FIELD = "needs_operator_check"
MACHINE = ("llm_session", "auto")
REVIEW_FIELD = "operator_review"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def evaluate(conn, account_id: int) -> list[str]:
    """Reasons the account needs an operator check (empty list = clear)."""
    latest = {}
    max_machine_id = 0
    for r in conn.execute(
        "SELECT id, field, value, provenance, confidence, method FROM competitor_field_obs"
        " WHERE account_id = ? AND provenance IN ('llm_session', 'auto') AND field != ?"
        " ORDER BY observed_at, id",
        (account_id, FIELD),
    ):
        latest[r["field"]] = r
        max_machine_id = max(max_machine_id, r["id"])
    review = conn.execute(
        "SELECT MAX(id) FROM competitor_field_obs WHERE account_id = ? AND field = ?",
        (account_id, REVIEW_FIELD),
    ).fetchone()[0]
    if review is not None and review > max_machine_id:
        return []

    reasons: list[str] = []
    low = sorted(f for f, r in latest.items() if r["confidence"] == "low")
    if low:
        reasons.append("low confidence: " + ", ".join(low))

    voice = latest.get("voice_gender")
    seen = latest.get("visible_speaker_gender")
    if (
        voice is not None
        and seen is not None
        and voice["value"] in ("male", "female")
        and seen["value"] in ("male", "female")
        and voice["value"] != seen["value"]
    ):
        reasons.append(f"pitch estimate {voice['value']} vs visible speaker {seen['value']}")

    statuses = [
        r[0]
        for r in conn.execute(
            "SELECT download_status FROM competitor_video WHERE account_id = ?", (account_id,)
        )
    ]
    if statuses and all(s == "unavailable" for s in statuses):
        reasons.append("download unavailable for all videos")

    if "evidence_guard" in latest:
        reasons.append(f"evidence guard {latest['evidence_guard']['value']}")

    row = conn.execute(
        "SELECT language, source_citing_score, source_text_level, source_video_level, face,"
        " voice_gender FROM v_competitor_sheet WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    if row is not None:
        text = _int(row["source_text_level"])
        video = _int(row["source_video_level"])
        if row["language"] == "de" and (text is None or text < 2):
            onscreen = conn.execute(
                "SELECT MAX(level) FROM competitor_post_citing WHERE account_id = ?"
                " AND source = 'onscreen'",
                (account_id,),
            ).fetchone()[0]
            if video is not None and video >= 2:
                reasons.append(f"DACH: video level {video} lifts score over text level {text}")
            elif onscreen is not None and onscreen >= 2:
                reasons.append(f"DACH: on-screen citation level {onscreen} decides the score")
        if row["language"] == "de" and text is not None and text >= 2:
            reasons.append(f"DACH: text level {text} counts toward N_DE")
        score = row["source_citing_score"]
        if (
            score is not None
            and score >= 2
            and row["face"] == "faceless"
            and row["voice_gender"] == "male"
        ):
            reasons.append(f"would count toward S_{row['language'].upper()}")
    return reasons


def recompute_conn(conn, account_id: int, now: str | None = None) -> tuple[bool, list[str]]:
    """Recompute and store the flag on an open connection (caller owns the transaction)."""
    reasons = evaluate(conn, account_id)
    flag = bool(reasons)
    conn.execute(
        "DELETE FROM competitor_field_obs WHERE account_id = ? AND field = ?"
        " AND provenance = 'auto'",
        (account_id, FIELD),
    )
    conn.execute(
        "INSERT INTO competitor_field_obs (account_id, field, value, provenance, confidence,"
        " method, observed_at) VALUES (?, ?, ?, 'auto', 'high', ?, ?)",
        (
            account_id,
            FIELD,
            "true" if flag else "false",
            "; ".join(reasons) or "no queue rule matched",
            now or _now(),
        ),
    )
    return flag, reasons


def recompute(db: Database, account_id: int) -> tuple[bool, list[str]]:
    conn = db.connect()
    try:
        conn.execute("BEGIN")
        try:
            out = recompute_conn(conn, account_id)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return out
    finally:
        conn.close()


def recompute_all(db: Database) -> dict:
    conn = db.connect()
    try:
        ids = [r[0] for r in conn.execute("SELECT id FROM competitor_account ORDER BY id")]
    finally:
        conn.close()
    counts = {"queued": 0, "clear": 0}
    for aid in ids:
        flag, _ = recompute(db, aid)
        counts["queued" if flag else "clear"] += 1
    return counts
