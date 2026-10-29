"""`ndc readout` sub-app (plan 03-01 Task 1). `ndc publish` / `ndc metrics` follow in Tasks 2-3."""

import typer

from ndc import readout
from ndc.config import db_path
from ndc.db import Database

readout_app = typer.Typer(
    help="Readout rule: show, lock, amend (pre-registration).", no_args_is_help=True
)


def _fail(exc: Exception, code: int = 1) -> typer.Exit:
    typer.echo(f"error: {exc}", err=True)
    return typer.Exit(code=code)


@readout_app.command("show")
def readout_show() -> None:
    """Lock state of config/readout_rule.yaml; exit 1 when the file drifted from the lock."""
    conn = Database(db_path()).connect()
    try:
        st = readout.status(conn)
    finally:
        conn.close()
    if not st["locked"]:
        typer.echo(f"not locked · file sha {st['file_sha256'][:12]} (ndc readout lock)")
        raise typer.Exit(code=1)
    state = "locked" if st["matches_file"] else "geändert — Datei passt nicht zur Sperre"
    typer.echo(
        f"{state} · sha {st['sha256'][:12]} · committed_at {st['committed_at']}"
        + (" · amended" if st["amended"] else "")
    )
    if not st["matches_file"]:
        raise typer.Exit(code=1)


@readout_app.command("lock")
def readout_lock(
    lock_out: str = typer.Option(
        None,
        "--lock-out",
        help="Directory for the lock file when config/ is read-only (e.g. /data)",
    ),
) -> None:
    """Commit the rule: write readout_rule.lock and the readout_rule DB row."""
    try:
        data = readout.lock(Database(db_path()), lock_out=lock_out)
    except (readout.ReadoutChanged, ValueError, OSError) as e:
        raise _fail(e) from e
    typer.echo(f"locked · sha {data['sha256'][:12]} · committed_at {data['committed_at']}")


@readout_app.command("amend")
def readout_amend(
    reason: str = typer.Option(..., "--reason", help="Why the rule changed (>= 5 chars)"),
    lock_out: str = typer.Option(None, "--lock-out", help="Directory for the lock file"),
) -> None:
    """Log a rule change with a reason and re-lock."""
    try:
        data = readout.amend(Database(db_path()), reason, lock_out=lock_out)
    except (readout.ReadoutChanged, readout.ReadoutNotLocked, ValueError) as e:
        raise _fail(e) from e
    typer.echo(f"amended · sha {data['sha256'][:12]} · committed_at {data['committed_at']}")
