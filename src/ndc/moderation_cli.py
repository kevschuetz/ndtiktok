"""`ndc moderation` sub-app: check (validate + safety check replies) and render (write the playbook)."""

from pathlib import Path

import typer

from ndc import moderation
from ndc.config import db_path
from ndc.db import Database

app = typer.Typer(help="Moderation playbook: check, render.", no_args_is_help=True)


@app.command("check")
def mod_check() -> None:
    """Validate config/moderation.yaml and run the safety/terminology check on every reply."""
    try:
        mod = moderation.load_moderation()
        rows = moderation.validate_replies(mod, Database(db_path()))
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e
    for key, status, rules in rows:
        typer.echo(f"{key:<20} {status:<14} {', '.join(rules) if rules else ''}")
    sync = moderation.crisis_numbers_in_sync(mod)
    typer.echo(f"crisis numbers in sync with crisis_lines.yaml: {'yes' if sync else 'NO'}")
    typer.echo(f"approved_at: {mod.approved_at or 'not yet'}")
    if not sync:
        raise typer.Exit(code=1)


@app.command("render")
def mod_render(out: str = typer.Option("docs/moderation-playbook.md", "--out")) -> None:
    """Write the playbook document from the config."""
    try:
        mod = moderation.load_moderation()
        moderation.validate_replies(mod, Database(db_path()))
        text = moderation.render_playbook(mod)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e
    Path(out).write_text(text, encoding="utf-8")
    typer.echo(f"written {out} ({len(text.splitlines())} lines)")
