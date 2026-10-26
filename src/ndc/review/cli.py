"""`ndc review` sub-app: status, show, ack, decide (CLI channel of SCR-03)."""

import typer

from ndc.config import db_path
from ndc.db import Database
from ndc.review import store
from ndc.review.gate import VERDICT_LABELS_DE, cards, gate, sorted_cards

app = typer.Typer(help="Review: status, show, ack, decide.", no_args_is_help=True)


def _fail(exc: Exception, code: int = 1) -> typer.Exit:
    typer.echo(f"error: {exc}", err=True)
    return typer.Exit(code=code)


def _db() -> Database:
    return Database(db_path())


def resolve_sha(conn, ref: str) -> str:
    ref = ref.strip().lower()
    if len(ref) < 8 or any(c not in "0123456789abcdef" for c in ref):
        raise ValueError("give a sha256 prefix of at least 8 hex chars")
    rows = conn.execute(
        "SELECT sha256 FROM script_version WHERE sha256 LIKE ?", (ref + "%",)
    ).fetchall()
    if not rows:
        raise ValueError(f"no script version with sha {ref}")
    if len(rows) > 1:
        raise ValueError(f"sha prefix {ref} is ambiguous")
    return rows[0][0]


def banner(res) -> str:
    if res.blockers:
        return f"✗ Nicht freigebbar — {len(res.blockers)} Blocker"
    if res.needs_ack:
        return f"⚠ Noch {len(res.needs_ack)} Bestätigungen offen"
    return "✓ Bereit zur Freigabe"


@app.command("status")
def status() -> None:
    """Latest version of every verified script and its gate/decision."""
    db = _db()
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT v.* FROM script_version v WHERE v.version_no = (SELECT max(version_no) "
            "FROM script_version WHERE script_id = v.script_id) ORDER BY v.id DESC"
        ).fetchall()
        if not rows:
            typer.echo("Nichts zu prüfen")
        for v in rows:
            topic = conn.execute(
                "SELECT t.working_title FROM script s JOIN topic t ON t.id = s.topic_id "
                "WHERE s.id = ?",
                (v["script_id"],),
            ).fetchone()[0]
            dec = store.latest_decision(conn, v["sha256"])
            state = dec["decision"] if dec else banner(gate(db, v["id"], conn=conn))
            typer.echo(f"{v['sha256'][:10]}  v{v['version_no']}  {state}  — {topic}")
    finally:
        conn.close()


@app.command("show")
def show(ref: str) -> None:
    """Gate banner, warnings, script and risk-sorted claim ↔ source pairs."""
    db = _db()
    conn = db.connect()
    try:
        try:
            sha = resolve_sha(conn, ref)
        except ValueError as e:
            raise _fail(e) from e
        v = store.version_by_sha(conn, sha)
        res = gate(db, v["id"], conn=conn)
        dec = store.latest_decision(conn, sha)
        typer.echo(f"{sha}  v{v['version_no']}  {v['word_count']} Wörter")
        typer.echo(banner(res) + (f"  · Entscheidung: {dec['decision']}" if dec else ""))
        for i in res.blockers:
            typer.echo(f"  ✗ {i.message_de}")
        for i in res.warnings:
            typer.echo(f"  ⚠ {i.message_de}")
        cs = cards(conn, v["id"])
        typer.echo("\nSkript:")
        for c in cs:
            typer.echo(f"  [{c.ordinal}] {c.text}")
        typer.echo("")
        for c in sorted_cards(cs):
            label = VERDICT_LABELS_DE.get(c.verdict or "unsupported", c.verdict or "?")
            extra = []
            if c.escalation:
                extra.append(VERDICT_LABELS_DE["escalation"])
            if c.hidden_claim:
                extra.append(VERDICT_LABELS_DE["hidden_claim"])
            if c.acked:
                extra.append("✓ bestätigt")
            typer.echo(f"[{c.ordinal}] {label}" + (f"  ({', '.join(extra)})" if extra else ""))
            typer.echo(f"    „{c.text}“")
            if not c.cited and c.kind != "framing":
                typer.echo("    Quelle: Keine Quelle")
            for q in c.cited:
                loc = q.section or ""
                if q.page:
                    loc += f" S.{q.page}"
                typer.echo(f"    Quelle: {q.short_cite} · {loc}\n      “{q.text}”")
            if c.note_de:
                typer.echo(f"    Prüfer: {c.note_de}")
            if c.suggested_fix_de:
                typer.echo(f"    Vorschlag: {c.suggested_fix_de}")
    finally:
        conn.close()


@app.command("ack")
def ack_cmd(ref: str, sentence: int, note: str = typer.Option(None, "--note")) -> None:
    """Confirm one overstated/partial/escalation claim for this exact script hash."""
    db = _db()
    conn = db.connect()
    try:
        sha = resolve_sha(conn, ref)
    except ValueError as e:
        raise _fail(e) from e
    finally:
        conn.close()
    try:
        store.ack(db, sha, sentence, note=note, channel="cli")
    except store.ReviewRefused as e:
        raise _fail(e) from e
    typer.echo(f"Satz {sentence} bestätigt")


@app.command("decide")
def decide_cmd(ref: str, decision: str, note: str = typer.Option(None, "--note")) -> None:
    """approved | rejected | changes_requested (note required for the latter two)."""
    db = _db()
    conn = db.connect()
    try:
        sha = resolve_sha(conn, ref)
    except ValueError as e:
        raise _fail(e) from e
    finally:
        conn.close()
    try:
        store.decide(db, sha, decision, note=note, channel="cli")
    except store.ReviewRefused as e:
        raise _fail(e) from e
    typer.echo(f"{decision}: {sha[:10]}")
