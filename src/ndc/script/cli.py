"""`ndc script` sub-app."""

import typer

from ndc import llm
from ndc.config import db_path
from ndc.db import Database
from ndc.script import draft as draft_mod

app = typer.Typer(help="Scripts: draft, show.", no_args_is_help=True)


def _fail(exc: Exception, code: int = 1) -> typer.Exit:
    typer.echo(f"error: {exc}", err=True)
    return typer.Exit(code=code)


def _db() -> Database:
    return Database(db_path())


def resolve_version(conn, ref: str):
    """A version id (digits, short) or a sha256 prefix of >= 8 hex chars."""
    ref = ref.strip().lower()
    if ref.isdigit() and len(ref) < 8:
        row = conn.execute("SELECT * FROM script_version WHERE id = ?", (int(ref),)).fetchone()
    elif len(ref) >= 8 and all(c in "0123456789abcdef" for c in ref):
        rows = conn.execute(
            "SELECT * FROM script_version WHERE sha256 LIKE ?", (ref + "%",)
        ).fetchall()
        if len(rows) > 1:
            raise ValueError(f"sha prefix {ref} is ambiguous")
        row = rows[0] if rows else None
    else:
        raise ValueError("give a version id or a sha256 prefix (>= 8 hex chars)")
    if row is None:
        raise ValueError(f"script version {ref} not found")
    return row


def print_version(conn, v) -> None:
    script = conn.execute("SELECT * FROM script WHERE id = ?", (v["script_id"],)).fetchone()
    topic = conn.execute(
        "SELECT working_title FROM topic WHERE id = ?", (script["topic_id"],)
    ).fetchone()
    typer.echo(f"{topic['working_title']}")
    typer.echo(f"version {v['id']} (v{v['version_no']}, {v['origin']}) sha256 {v['sha256']}")
    typer.echo(f"words {v['word_count']} · checks {v['check_status']}")
    for s in conn.execute(
        "SELECT id, ordinal, text FROM script_sentence WHERE script_version_id = ? "
        "ORDER BY ordinal",
        (v["id"],),
    ):
        cites = conn.execute(
            "SELECT DISTINCT cs.short_cite, ssent.section, ssent.page FROM script_citation c "
            "JOIN source_sentence ssent ON ssent.id = c.source_sentence_id "
            "JOIN corpus_source cs ON cs.snapshot_id = ssent.snapshot_id AND cs.corpus_id = ? "
            "WHERE c.script_sentence_id = ?",
            (script["corpus_id"], s["id"]),
        ).fetchall()
        marks = " ".join(
            f"[{c['short_cite']} §{c['section'] or ''}"
            f"{' S.' + str(c['page']) if c['page'] else ''}]"
            for c in cites
        )
        typer.echo(f"[{s['ordinal']}] {s['text']} {marks}".rstrip())


@app.command("draft")
def draft_cmd(topic_id: int) -> None:
    """Draft a grounded German script from the topic's locked corpus (one LLM call)."""
    db = _db()
    try:
        vid = draft_mod.draft(db, topic_id)
    except (draft_mod.DraftError, llm.LlmError, llm.ConfigError) as e:
        raise _fail(e) from e
    conn = db.connect()
    try:
        print_version(
            conn, conn.execute("SELECT * FROM script_version WHERE id = ?", (vid,)).fetchone()
        )
    finally:
        conn.close()


@app.command("show")
def show(ref: str) -> None:
    """Show a script version (id or sha prefix) with citation markers."""
    conn = _db().connect()
    try:
        try:
            v = resolve_version(conn, ref)
        except ValueError as e:
            raise _fail(e) from e
        print_version(conn, v)
    finally:
        conn.close()


@app.command("verify")
def verify_cmd(ref: str) -> None:
    """Adversarially verify a script version with the verify model (one LLM call)."""
    from ndc.script import verify as verify_mod

    db = _db()
    conn = db.connect()
    try:
        try:
            v = resolve_version(conn, ref)
        except ValueError as e:
            raise _fail(e) from e
    finally:
        conn.close()
    try:
        run_id = verify_mod.verify(db, v["id"])
    except (verify_mod.VerifyError, llm.LlmError, llm.ConfigError) as e:
        raise _fail(e) from e
    if run_id is None:
        typer.echo("already verified")
    conn = db.connect()
    try:
        counts = verify_mod.verdict_counts(conn, v["id"])
    finally:
        conn.close()
    typer.echo(" · ".join(f"{k} {n}" for k, n in sorted(counts.items())))


@app.command("sources")
def sources_cmd(
    sha_ref: str, variant: str = typer.Option("caption", "--variant", help="caption | comment")
) -> None:
    """Render the source list of an APPROVED version from stored source rows."""
    from ndc.review.cli import resolve_sha
    from ndc.script import sources_list

    db = _db()
    conn = db.connect()
    try:
        try:
            sha = resolve_sha(conn, sha_ref)
        except ValueError as e:
            raise _fail(e) from e
    finally:
        conn.close()
    try:
        parts = sources_list.render(db, sha, variant)
    except (sources_list.NotApproved, ValueError) as e:
        raise _fail(e) from e
    typer.echo("\n\n".join(parts))
