"""`ndc recording` sub-app: add (transcribe + align), show, list; ack/decide/srt in Task 2."""

import typer

from ndc.config import db_path
from ndc.db import Database
from ndc.recording import store
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
) -> None:
    """Transcribe a take (faster-whisper, run in ndc-heavy) and align it to the approved script."""
    if quiet_hours.in_quiet_hours() and not force:
        typer.echo("error: quiet hours (00:15-06:00 UTC); --force to override", err=True)
        raise typer.Exit(code=4)
    try:
        res = store.add_recording(Database(db_path()), file, script)
    except store.RecordingError as e:
        raise _fail(e) from e
    typer.echo(
        f"recording {res['recording_id']} · transcript sha {res['transcript_sha256'][:12]} · "
        f"match {res['match']} · deviation {res['deviation']} · extra {res['extra']} · "
        f"missing {res['missing']}"
    )


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
    typer.echo(
        f"recording {r['id']} · {r['file_name']} · {r['whisper_model']} · "
        f"{r['duration_s'] or '?'} s · transcript sha {r['transcript_sha256'][:12]} · "
        f"Skript {r['script_sha256'][:10]} · Schwelle {r['similarity_threshold']}"
    )
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
