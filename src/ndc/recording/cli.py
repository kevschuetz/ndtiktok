"""`ndc recording` sub-app: add (transcribe + align), show, list; ack/decide/srt in Task 2."""

import typer

from ndc.config import db_path
from ndc.db import Database
from ndc.recording import gate, srt, store
from ndc.scan import quiet_hours

app = typer.Typer(
    help="Recording: add, show, list (diff of the take vs the approved script).",
    no_args_is_help=True,
)


def _fail(exc: Exception, code: int = 1) -> typer.Exit:
    typer.echo(f"error: {exc}", err=True)
    return typer.Exit(code=code)


@app.command("add")
def rec_add(
    file: str,
    script: str = typer.Option(..., "--script", help="approved script version sha (prefix ok)"),
    force: bool = typer.Option(False, "--force", help="Override quiet hours (heavy CPU job)."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip the verifier call for now."),
) -> None:
    """Transcribe a take (faster-whisper, run in ndc-heavy), align it to the approved script,
    verify deviations and auto-approve when there are none."""
    if quiet_hours.in_quiet_hours() and not force:
        typer.echo("error: quiet hours (00:15-06:00 UTC); --force to override", err=True)
        raise typer.Exit(code=4)
    db = Database(db_path())
    try:
        res = gate.process_recording(db, file, script, verify=not no_verify)
    except store.RecordingError as e:
        raise _fail(e) from e
    typer.echo(
        f"recording {res['recording_id']} · transcript sha {res['transcript_sha256'][:12]} · "
        f"match {res['match']} · deviation {res['deviation']} · extra {res['extra']} · "
        f"missing {res['missing']}"
    )
    if res.get("auto_approved"):
        typer.echo("✓ automatisch freigegeben (keine Abweichungen)")
    else:
        typer.echo(gate.banner(gate.recording_gate(db, res["recording_id"])))


@app.command("show")
def rec_show(ref: str) -> None:
    """Aligned sentences: status, similarity, spoken vs approved, verdict (once verified)."""
    conn = Database(db_path()).connect()
    try:
        try:
            r = store.recording_by_ref(conn, ref)
        except store.RecordingError as e:
            raise _fail(e) from e
        rows = store.sentences(conn, r["id"])
    finally:
        conn.close()
    db = Database(db_path())
    res = gate.recording_gate(db, r["id"])
    dec = None
    c2 = db.connect()
    try:
        dec = gate.latest_recording_decision(c2, r["transcript_sha256"])
    finally:
        c2.close()
    typer.echo(
        f"recording {r['id']} · {r['file_name']} · {r['whisper_model']} · "
        f"{r['duration_s'] or '?'} s · transcript sha {r['transcript_sha256'][:12]} · "
        f"Skript {r['script_sha256'][:10]} · Schwelle {r['similarity_threshold']}"
    )
    typer.echo(dec["decision"] if dec else gate.banner(res))
    for i in res.blockers + res.needs_ack + res.warnings:
        typer.echo(f"  {i.message_de}")
    for s in rows:
        sim = f"{s['similarity']:.2f}" if s["similarity"] is not None else "  — "
        line = f"[{s['ordinal']:>2}] {s['status']:<9} {sim}"
        if s["verdict"]:
            line += f"  {s['verdict']}"
        typer.echo(line)
        if s["status"] != "extra":
            typer.echo(f"      Skript : {s['approved_text']}")
        if s["status"] != "missing":
            typer.echo(f"      gesagt : {s['spoken_text']}")
        if s["reason"]:
            typer.echo(f"      Grund  : {s['reason']}")
        if s["note_de"]:
            typer.echo(f"      Prüfer : {s['note_de']}")


@app.command("list")
def rec_list() -> None:
    conn = Database(db_path()).connect()
    try:
        rows = conn.execute(
            "SELECT r.*, t.working_title FROM recording r "
            "JOIN script_version v ON v.id = r.script_version_id "
            "JOIN script s ON s.id = v.script_id JOIN topic t ON t.id = s.topic_id "
            "ORDER BY r.id DESC"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        typer.echo("keine Aufnahmen")
    for r in rows:
        typer.echo(
            f"{r['id']}  {r['transcript_sha256'][:10]}  {r['created_at']}  "
            f"match {r['n_match']} dev {r['n_deviation']} extra {r['n_extra']} "
            f"miss {r['n_missing']}  "
            f"— {r['working_title']}"
        )


@app.command("ack")
def rec_ack(ref: str, sentence: int, note: str = typer.Option(None, "--note")) -> None:
    """Confirm one partial/overstated/escalation deviation for this exact transcript hash."""
    db = Database(db_path())
    conn = db.connect()
    try:
        r = store.recording_by_ref(conn, ref)
    except store.RecordingError as e:
        raise _fail(e) from e
    finally:
        conn.close()
    try:
        gate.ack(db, r["transcript_sha256"], sentence, note=note, channel="cli")
    except store.RecordingError as e:
        raise _fail(e) from e
    typer.echo(f"Satz {sentence} bestätigt")


@app.command("decide")
def rec_decide(ref: str, decision: str, note: str = typer.Option(None, "--note")) -> None:
    """approved | rejected | changes_requested (note required for the latter two)."""
    db = Database(db_path())
    conn = db.connect()
    try:
        r = store.recording_by_ref(conn, ref)
    except store.RecordingError as e:
        raise _fail(e) from e
    finally:
        conn.close()
    try:
        gate.decide(db, r["transcript_sha256"], decision, note=note, channel="cli")
    except store.RecordingError as e:
        raise _fail(e) from e
    typer.echo(f"{decision} · transcript {r['transcript_sha256'][:12]}")


@app.command("srt")
def rec_srt(ref: str, out: str = typer.Option(None, "-o", "--out")) -> None:
    """Word-timed SRT whose text is the final (approved) transcript."""
    conn = Database(db_path()).connect()
    try:
        try:
            r = store.recording_by_ref(conn, ref)
        except store.RecordingError as e:
            raise _fail(e) from e
        text = srt.to_srt(conn, r["id"])
    finally:
        conn.close()
    if out:
        from pathlib import Path

        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"written {out} ({text.count('-->')} cues)")
    else:
        typer.echo(text)
