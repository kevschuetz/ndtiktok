"""`ndc topic` sub-app."""

import csv
import sqlite3
import sys
from enum import StrEnum

import typer
from rich.console import Console
from rich.table import Table

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
