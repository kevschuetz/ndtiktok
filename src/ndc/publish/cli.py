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


# ---------------------------------------------------------------- ndc publish (Task 2)
from ndc.publish import store as pstore  # noqa: E402

publish_app = typer.Typer(help="Publish log: log, caption, list.", no_args_is_help=True)


@publish_app.command("log")
def publish_log(
    platform: str = typer.Option(..., "--platform", help="tiktok | youtube | instagram"),
    script: str = typer.Option(..., "--script", help="approved script version sha (prefix ok)"),
    post_url: str = typer.Option(..., "--post-url"),
    recording: str = typer.Option(None, "--recording", help="approved recording transcript sha"),
    posted_at: str = typer.Option(None, "--posted-at", help="ISO UTC, default now"),
    hook: str = typer.Option(None, "--hook", help="hook tactic label (exploratory)"),
) -> None:
    """Log a published post (append-only); refuses unapproved content or an unlocked readout."""
    try:
        pid = pstore.log_publication(
            Database(db_path()),
            platform=platform,
            script_sha=script,
            post_url=post_url,
            recording_sha=recording,
            posted_at=posted_at,
            hook_tactic=hook,
        )
    except (pstore.PublishRefused, ValueError) as e:
        raise _fail(e) from e
    typer.echo(f"publication {pid} · {platform} · geloggt")


@publish_app.command("caption")
def publish_caption(script: str) -> None:
    """Caption (source list + hashtags) and pinned comment(s), from DB rows and config only."""
    db = Database(db_path())
    try:
        cap = pstore.render_caption(db, script)
        pinned = pstore.render_pinned(db, script)
    except Exception as e:  # NotApproved / PublishRefused
        raise _fail(e) from e
    typer.echo(cap)
    typer.echo("---")
    for p in pinned:
        typer.echo(p)


@publish_app.command("list")
def publish_list() -> None:
    conn = Database(db_path()).connect()
    try:
        rows = pstore.list_publications(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("keine Veröffentlichungen")
    for r in rows:
        typer.echo(
            f"{r['id']}  {r['platform']:<9} {r['posted_at']}  {r['pillar']}  "
            f"{r['script_sha256'][:10]}  {r['post_url']}  — {r['working_title']}"
        )


# ---------------------------------------------------------------- ndc metrics (Task 3)
from datetime import datetime  # noqa: E402

from ndc.publish import metrics as pm  # noqa: E402

metrics_app = typer.Typer(help="Metric snapshots: add, import, due, show.", no_args_is_help=True)


@metrics_app.command("add")
def metrics_add(
    publication_id: int,
    age: str = typer.Option(None, "--age", help="24h | 72h | 7d | adhoc (default: from post age)"),
    views: int = typer.Option(None, "--views"),
    likes: int = typer.Option(None, "--likes"),
    comments: int = typer.Option(None, "--comments"),
    shares: int = typer.Option(None, "--shares"),
    saves: int = typer.Option(None, "--saves"),
    follows: int = typer.Option(None, "--follows"),
    avg_watch_s: float = typer.Option(None, "--avg-watch-s"),
    watched_full_pct: float = typer.Option(None, "--watched-full-pct"),
    fyf: str = typer.Option(
        "unknown", "--fyf", help="yes | no | unknown (For-You-Feed eligibility)"
    ),
    fyf_reason: str = typer.Option(None, "--fyf-reason"),
    captured_at: str = typer.Option(None, "--captured-at", help="ISO UTC, default now"),
) -> None:
    """Hand-entered snapshot (append-only)."""
    vals = {
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "follows": follows,
        "avg_watch_s": avg_watch_s,
        "watched_full_pct": watched_full_pct,
    }
    try:
        sid = pm.add_snapshot(
            Database(db_path()),
            publication_id,
            age,
            vals,
            "manual",
            captured_at=captured_at,
            fyf_status=fyf,
            fyf_reason=fyf_reason,
        )
    except (pm.MetricsError, ValueError) as e:
        raise _fail(e) from e
    typer.echo(f"snapshot {sid} gespeichert")


@metrics_app.command("import")
def metrics_import(
    csv_path: str,
    age: str = typer.Option(None, "--age"),
    captured_at: str = typer.Option(None, "--captured-at"),
) -> None:
    """Import a TikTok Studio CSV export (headers mapped via config/metrics.yaml)."""
    try:
        rep = pm.import_csv(Database(db_path()), csv_path, captured_at=captured_at, age_label=age)
    except (pm.MetricsError, OSError, ValueError) as e:
        raise _fail(e) from e
    typer.echo(f"Spalten erkannt: {rep['mapped']}")
    typer.echo(f"{len(rep['matched'])} Zeilen importiert · {len(rep['unmatched'])} ohne Treffer")
    for u in rep["unmatched"]:
        typer.echo(f"  ohne Treffer: {u}")


@metrics_app.command("due")
def metrics_due(
    write: str = typer.Option(None, "--write", help="write JSON here (must be under /data)"),
    now: str = typer.Option(None, "--now", help="ISO UTC (tests)"),
) -> None:
    """Publications whose snapshot window is open and still empty."""
    when = datetime.fromisoformat(now.replace("Z", "+00:00")) if now else None
    conn = Database(db_path()).connect()
    try:
        items = pm.due(conn, when)
    finally:
        conn.close()
    if write:
        try:
            pm.write_due(write, items, when)
        except pm.MetricsError as e:
            raise _fail(e) from e
    if not items:
        typer.echo("nichts fällig")
    for i in items:
        typer.echo(
            f"publication {i['publication_id']} · {i['platform']} · {i['age']} fällig "
            f"(Alter {i['post_age_hours']} h, Fenster schließt in "
            f"{i['window_closes_in_h']} h) — {i['title']}"
        )


@metrics_app.command("show")
def metrics_show(publication_id: int) -> None:
    conn = Database(db_path()).connect()
    try:
        rows = pm.snapshots(conn, publication_id)
    finally:
        conn.close()
    if not rows:
        typer.echo("keine Snapshots")
    for r in rows:
        typer.echo(
            f"{r['age_label']:<5} {r['post_age_hours']:>6} h  views={r['views']} "
            f"likes={r['likes']} comments={r['comments']} shares={r['shares']} "
            f"saves={r['saves']} follows={r['follows']} avg_watch={r['avg_watch_s']} "
            f"full%={r['watched_full_pct']} fyf={r['fyf_status']} ({r['source']})"
        )
