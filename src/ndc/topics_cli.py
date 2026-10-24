"""`ndc topic` sub-app."""

import csv
import json
import sqlite3
import sys
from enum import StrEnum

import typer
from rich.console import Console
from rich.table import Table

from ndc import topics
from ndc.config import db_path
from ndc.db import Database
from ndc.topics import LIST_COLUMNS, TopicError, add_topic, import_seed, list_topics

app = typer.Typer(help="Topic matrix: import, add, list, review.", no_args_is_help=True)


def _fail(exc: Exception, code: int = 1) -> typer.Exit:
    typer.echo(f"error: {exc}", err=True)
    return typer.Exit(code=code)


class OutFormat(StrEnum):
    table = "table"
    csv = "csv"


@app.command("add")
def add(
    pillar: str = typer.Option(..., help="Content pillar key"),
    condition: str = typer.Option(..., help="Condition key (adhd, autism, ...)"),
    domain: str = typer.Option(..., help="Life domain key"),
    audience: str = typer.Option(..., help="Audience key"),
    angle: str = typer.Option(..., help="Angle key"),
    title: str = typer.Option(..., "--title", help="Working title"),
    tag: str = typer.Option(..., "--tag", help="whitelist | blacklist"),
    source_likely: str = typer.Option(..., help="yes | maybe | no"),
    summary: str | None = typer.Option(None, help="Short summary"),
    language: str | None = typer.Option(None, help="de | en (empty until decided)"),
    origin: str = typer.Option("operator", help="matrix | operator"),
) -> None:
    """Add one topic and print its id."""
    try:
        new_id = add_topic(
            Database(db_path()),
            pillar=pillar,
            condition=condition,
            domain=domain,
            audience=audience,
            angle=angle,
            working_title=title,
            list_tag=tag,
            source_likely=source_likely,
            summary=summary,
            language=language,
            origin=origin,
        )
    except TopicError as exc:
        raise _fail(exc) from exc
    except sqlite3.IntegrityError as exc:
        typer.echo(f"error: topic rejected by database: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"added topic {new_id}")


@app.command("import")
def import_cmd(path: str = typer.Argument(..., help="Reviewed seed YAML")) -> None:
    """Import a reviewed seed YAML (vocab-validated, safety-checked, all-or-nothing)."""
    try:
        res = import_seed(Database(db_path()), path)
    except TopicError as exc:
        raise _fail(exc) from exc
    typer.echo(
        f"inserted {res.inserted}, skipped {res.skipped} (already present); "
        f"safety in file: {res.blocked} blocked, {res.flagged} flagged"
    )


@app.command("list")
def list_cmd(
    pillar: str | None = typer.Option(None),
    condition: str | None = typer.Option(None),
    domain: str | None = typer.Option(None),
    audience: str | None = typer.Option(None),
    angle: str | None = typer.Option(None),
    tag: str | None = typer.Option(None, "--tag", help="whitelist | blacklist"),
    status: str | None = typer.Option(None),
    fmt: OutFormat = typer.Option(OutFormat.table, "--format", help="table | csv"),
) -> None:
    """List topics; list_tag and safety_status are always shown."""
    try:
        rows = list_topics(
            Database(db_path()),
            {
                "pillar": pillar,
                "condition": condition,
                "domain": domain,
                "audience": audience,
                "angle": angle,
                "list_tag": tag,
                "status": status,
            },
        )
    except TopicError as exc:
        raise _fail(exc, code=2) from exc
    if fmt is OutFormat.csv:
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(LIST_COLUMNS)
        for r in rows:
            writer.writerow([r[c] for c in LIST_COLUMNS])
        return
    table = Table(title=f"topics ({len(rows)})")
    for c in LIST_COLUMNS:
        table.add_column(c, overflow="fold")
    for r in rows:
        table.add_row(*[str(r[c]) for c in LIST_COLUMNS])
    Console(width=None if sys.stdout.isatty() else 200).print(table)


def _hits_text(hits_json: str | None) -> str:
    if not hits_json:
        return "-"
    hits = json.loads(hits_json)
    return "; ".join(f"{h['rule_id']} ({h['matched_text']!r})" for h in hits) or "-"


@app.command("review")
def review() -> None:
    """Walk proposed topics: k keep, x kill (asks for a reason), s skip, q quit."""
    db = Database(db_path())
    rows = topics.proposed_topics(db)
    if not rows:
        typer.echo("no proposed topics")
        return
    kept = killed = 0
    for n, r in enumerate(rows, 1):
        typer.echo(f"\n[{n}/{len(rows)}] #{r['id']}  {r['working_title']}")
        if r["summary"]:
            typer.echo(f"  {r['summary']}")
        typer.echo(
            f"  pillar={r['pillar']} condition={r['condition']} domain={r['domain']} "
            f"audience={r['audience']} angle={r['angle']}"
        )
        typer.echo(
            f"  tag={r['list_tag']} safety={r['safety_status']} "
            f"source_likely={r['source_likely']} hits={_hits_text(r['safety_hits_json'])}"
        )
        while True:
            choice = typer.prompt("  [k]eep / [x] kill / [s]kip / [q]uit").strip().lower()
            if choice in ("k", "x", "s", "q"):
                break
            typer.echo("  please answer k, x, s or q")
        if choice == "q":
            break
        if choice == "k":
            topics.keep(db, [r["id"]])
            kept += 1
        elif choice == "x":
            while True:
                reason = typer.prompt("  kill reason (>= 5 chars)").strip()
                if len(reason) >= topics.MIN_REASON:
                    break
                typer.echo("  reason too short")
            topics.kill(db, r["id"], reason)
            killed += 1
    typer.echo(f"\nkept {kept}, killed {killed}")


@app.command("keep")
def keep_cmd(ids: list[int] = typer.Argument(..., help="Topic ids (proposed)")) -> None:
    """Move proposed topics to the backlog (all-or-nothing)."""
    try:
        n = topics.keep(Database(db_path()), ids)
    except TopicError as exc:
        raise _fail(exc) from exc
    typer.echo(f"kept {n}: {' '.join(map(str, ids))}")


@app.command("kill")
def kill_cmd(
    topic_id: int = typer.Argument(..., help="Topic id (proposed)"),
    reason: str = typer.Option(..., "--reason", help="Why (>= 5 chars, stored)"),
) -> None:
    """Reject a proposed topic with a reason."""
    try:
        topics.kill(Database(db_path()), topic_id, reason)
    except TopicError as exc:
        raise _fail(exc) from exc
    typer.echo(f"killed {topic_id}")


@app.command("select")
def select_cmd(topic_id: int = typer.Argument(..., help="Topic id (backlog)")) -> None:
    """Move a backlog topic to selected; refuses blacklist-tagged or safety-blocked topics."""
    try:
        topics.select(Database(db_path()), topic_id)
    except TopicError as exc:
        raise _fail(exc) from exc
    typer.echo(f"selected {topic_id}")


@app.command("stats")
def stats_cmd() -> None:
    """Counts per pillar x status, and kept whitelist topics per pillar vs the target."""
    st = topics.stats(Database(db_path()))
    table = Table(title=f"topics per pillar (target: {st['target']} kept per pillar)")
    table.add_column("pillar")
    for status in topics.STATUSES:
        table.add_column(status, justify="right")
    table.add_column("kept (whitelist, ok/flagged)", justify="right")
    table.add_column("")
    for pillar, v in st["pillars"].items():
        table.add_row(
            pillar,
            *[str(v["counts"].get(status, 0)) for status in topics.STATUSES],
            str(v["kept_safe_whitelist"]),
            f"below {st['target']}" if v["below_target"] else "ok",
        )
    Console(width=None if sys.stdout.isatty() else 200).print(table)
