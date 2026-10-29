"""Recording gate and hash-bound approval (D-02). Mirrors review/gate.py + review/store.py:
blockers = unsupported/contradicts deviations, unverified deviations, superseded script;
needs_ack = partial/overstated/escalation without an ack for THIS transcript sha; warnings =
sentences not spoken, low-confidence words. Zero deviations -> automatic approval row.
The publish log refuses a publication whose recording is not approved (PUBLISH_GATES hook)."""

import json

from ndc.db import Database
from ndc.publish import store as pstore
from ndc.recording import store
from ndc.review.gate import BLOCKING, NEEDS_ACK, VERDICT_LABELS_DE, GateResult, Issue, is_latest
from ndc.review.store import CHANNELS, DECISIONS, latest_decision

RISK = {"contradicts": 0, "unsupported": 1, "overstated": 2, "partial": 3, "supports": 5}


def _acks(conn, sha: str) -> dict[int, str | None]:
    return {
        r["sentence_ordinal"]: r["note"]
        for r in conn.execute(
            "SELECT sentence_ordinal, note FROM recording_ack WHERE transcript_sha256 = ?", (sha,)
        )
    }


def latest_recording_decision(conn, sha: str):
    return conn.execute(
        "SELECT * FROM recording_review WHERE transcript_sha256 = ? ORDER BY id DESC LIMIT 1",
        (sha,),
    ).fetchone()


def recording_gate(db: Database, recording_id: int, conn=None, cfg=None) -> GateResult:
    own = conn is None
    conn = conn or db.connect()
    cfg = cfg or store.load_config()
    try:
        rec = conn.execute("SELECT * FROM recording WHERE id = ?", (recording_id,)).fetchone()
        if rec is None:
            return GateResult(False, [Issue("missing", None, "Aufnahme nicht gefunden")])
        res = GateResult(False)
        v = conn.execute(
            "SELECT * FROM script_version WHERE id = ?", (rec["script_version_id"],)
        ).fetchone()
        dec = latest_decision(conn, rec["script_sha256"])
        if not is_latest(conn, v) or dec is None or dec["decision"] != "approved":
            res.blockers.append(
                Issue("block_stale", None, "Skriptversion ist veraltet oder nicht mehr freigegeben")
            )
        acks = _acks(conn, rec["transcript_sha256"])
        for s in store.sentences(conn, recording_id):
            if s["status"] in ("deviation", "extra"):
                if s["verdict"] is None:
                    res.blockers.append(
                        Issue(
                            "unverified",
                            s["ordinal"],
                            f"Satz {s['ordinal']}: Abweichung nicht geprüft",
                        )
                    )
                elif s["verdict"] in BLOCKING:
                    why = {
                        "hidden_claim": " (versteckte Aussage)",
                        "uncited": " (ohne Quelle)",
                    }.get(s["forced_reason"] or "", "")
                    res.blockers.append(
                        Issue(
                            s["verdict"],
                            s["ordinal"],
                            f"Satz {s['ordinal']}: {VERDICT_LABELS_DE[s['verdict']]}{why}",
                        )
                    )
                elif (
                    s["verdict"] in NEEDS_ACK
                    or (s["verdict"] == "supports" and s["certainty_escalation"])
                ) and s["ordinal"] not in acks:
                    label = "escalation" if s["verdict"] == "supports" else s["verdict"]
                    res.needs_ack.append(
                        Issue(
                            label,
                            s["ordinal"],
                            f"Satz {s['ordinal']}: {VERDICT_LABELS_DE[label]} — bestätigen",
                        )
                    )
            elif s["status"] == "missing":
                res.warnings.append(
                    Issue(
                        "missing",
                        s["ordinal"],
                        f"Satz {s['ordinal']} nicht gesprochen: {s['approved_text']}",
                    )
                )
            elif s["status"] == "match":
                low = [
                    w[2]
                    for w in json.loads(s["words_json"] or "[]")
                    if w[3] is not None and w[3] < cfg.low_confidence_word_prob
                ]
                if low:
                    res.warnings.append(
                        Issue(
                            "low_confidence",
                            s["ordinal"],
                            f"Satz {s['ordinal']}: unsichere Wörter {', '.join(low[:5])}",
                        )
                    )
        res.approvable = not res.blockers and not res.needs_ack
        return res
    finally:
        if own:
            conn.close()


def _version_for_sha(conn, sha: str):
    rec = conn.execute("SELECT * FROM recording WHERE transcript_sha256 = ?", (sha,)).fetchone()
    if rec is None:
        raise store.RecordingError("Aufnahme nicht gefunden")
    return rec


def ack(db: Database, sha: str, ordinal: int, *, reviewer="operator", note=None, channel="cli"):
    if channel not in CHANNELS:
        raise store.RecordingError(f"unbekannter Kanal {channel}")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            rec = _version_for_sha(conn, sha)
            res = recording_gate(db, rec["id"], conn=conn)
            if ordinal not in {i.sentence_ordinal for i in res.needs_ack}:
                raise store.RecordingError(f"Satz {ordinal} braucht keine Bestätigung")
            conn.execute(
                "INSERT INTO recording_ack (transcript_sha256, sentence_ordinal, reviewer, "
                "channel, note) VALUES (?,?,?,?,?)",
                (sha, ordinal, reviewer, channel, (note or "").strip() or None),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def decide(db: Database, sha: str, decision: str, *, reviewer="operator", note=None, channel="cli"):
    if decision not in DECISIONS:
        raise store.RecordingError(f"unbekannte Entscheidung {decision}")
    if channel not in CHANNELS:
        raise store.RecordingError(f"unbekannter Kanal {channel}")
    if decision != "approved" and len((note or "").strip()) < 5:
        raise store.RecordingError("Bitte kurz begründen.")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            rec = _version_for_sha(conn, sha)
            if decision == "approved":
                res = recording_gate(db, rec["id"], conn=conn)
                if not res.approvable:
                    msgs = [i.message_de for i in res.blockers + res.needs_ack]
                    raise store.RecordingError("nicht freigebbar: " + "; ".join(msgs))
            rid = conn.execute(
                "INSERT INTO recording_review (transcript_sha256, decision, reviewer, channel, "
                "note) VALUES (?,?,?,?,?)",
                (sha, decision, reviewer, channel, (note or "").strip() or None),
            ).lastrowid
            conn.execute("COMMIT")
            return rid
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def auto_approve_if_clean(db: Database, recording_id: int) -> bool:
    """No deviation and no extra sentence -> approve automatically (D-02); diff stays on record."""
    conn = db.connect()
    try:
        rec = conn.execute("SELECT * FROM recording WHERE id = ?", (recording_id,)).fetchone()
        if rec["n_deviation"] or rec["n_extra"]:
            return False
        if latest_recording_decision(conn, rec["transcript_sha256"]) is not None:
            return False
        if not recording_gate(db, recording_id, conn=conn).approvable:
            return False
    finally:
        conn.close()
    decide(
        db,
        rec["transcript_sha256"],
        "approved",
        reviewer="system",
        note="automatisch: keine Abweichungen vom freigegebenen Skript",
        channel="cli",
    )
    return True


def process_recording(
    db: Database, path, script_ref: str, *, transcriber=None, client=None, cfg=None, verify=True
) -> dict:
    """add -> verify deviations -> auto-approve when clean. Used by the CLI."""
    res = store.add_recording(db, path, script_ref, transcriber=transcriber, cfg=cfg)
    if verify and (res["deviation"] or res["extra"]):
        res["llm_run_id"] = store.verify_deviations(db, res["recording_id"], client=client)
    res["auto_approved"] = auto_approve_if_clean(db, res["recording_id"])
    return res


def publish_gate_hook(conn, script_sha: str, recording_sha: str | None) -> list[Issue]:
    """PUBLISH_GATES: a publication needs an APPROVED recording of exactly this script version."""
    if not recording_sha:
        return [Issue("block_recording", None, "Aufnahme fehlt (--recording <transcript-sha>)")]
    rec = conn.execute(
        "SELECT * FROM recording WHERE transcript_sha256 = ?", (recording_sha,)
    ).fetchone()
    if rec is None:
        return [Issue("block_recording", None, f"Aufnahme {recording_sha[:12]} nicht gefunden")]
    if rec["script_sha256"] != script_sha:
        return [Issue("block_recording", None, "Aufnahme gehört zu einer anderen Skriptversion")]
    dec = latest_recording_decision(conn, recording_sha)
    if dec is None or dec["decision"] != "approved":
        return [Issue("block_recording", None, "Aufnahme ist nicht freigegeben")]
    return []


if publish_gate_hook not in pstore.PUBLISH_GATES:
    pstore.PUBLISH_GATES.append(publish_gate_hook)


def banner(res: GateResult) -> str:
    if res.blockers:
        return f"✗ Nicht freigebbar — {len(res.blockers)} Blocker"
    if res.needs_ack:
        return f"⚠ Noch {len(res.needs_ack)} Bestätigungen offen"
    return "✓ Bereit zur Freigabe"
