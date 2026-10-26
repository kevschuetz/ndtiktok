"""Root `ndc` Typer app. Later plans add commands inside the sub-app modules only."""

import os

import typer

from ndc import topics_cli
from ndc.checks import cli as checks_cli
from ndc.config import config_dir, db_path, load_env
from ndc.db import Database
from ndc.review import cli as review_cli
from ndc.scan import cli as scan_cli
from ndc.script import cli as script_cli
from ndc.sources import cli as sources_cli

app = typer.Typer(help="nd-content operator CLI.", no_args_is_help=True)
app.add_typer(topics_cli.app, name="topic")
app.add_typer(checks_cli.app, name="check")
app.add_typer(scan_cli.app, name="scan")
app.add_typer(sources_cli.app, name="source")
app.add_typer(sources_cli.corpus_app, name="corpus")
app.add_typer(script_cli.app, name="script")
app.add_typer(review_cli.app, name="review")


@app.callback()
def _main() -> None:
    load_env()


@app.command()
def doctor() -> None:
    """Show DB path, applied migrations, config dir and secret presence (never values)."""
    path = db_path()
    typer.echo(f"db: {path}")
    typer.echo(f"config_dir: {config_dir()}")
    migrations = Database(path).applied_migrations()
    typer.echo("migrations: " + (", ".join(migrations) if migrations else "(none)"))
    key_state = "present" if os.environ.get("ANTHROPIC_API_KEY") else "missing"
    typer.echo(f"ANTHROPIC_API_KEY: {key_state}")
