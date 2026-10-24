"""`ndc scan` sub-app: `rule show`, `decide` (plan 01-03); collection commands (plan 01-04).

Exit codes for network commands: 3 rule lock not approved (D-20), 4 quiet hours (D-16).
"""

import csv
from pathlib import Path

import typer
from pydantic import ValidationError

from ndc.config import config_dir, db_path
from ndc.db import Database
from ndc.scan import fetch as scan_fetch
from ndc.scan import prereg, quiet_hours
from ndc.scan.decide import AccountRow, decide, fmt_metric, load_rule, write_decision_log

app = typer.Typer(help="Competitor scan and language decision (plans 01-03+).")
rule_app = typer.Typer(help="The pre-registered language decision rule.")
app.add_typer(rule_app, name="rule")

_INT_FIELDS = ("followers", "n_reach_posts", "source_citing_score")
_FLOAT_FIELDS = ("reach_median",)


@rule_app.command("show")
def rule_show() -> None:
    """Print thresholds, the current rule sha256 and the lock status."""
    cfg = config_dir()
    rule = load_rule(prereg.rule_path(cfg))
    typer.echo(f"rule: {prereg.rule_path(cfg)} (version {rule.version})")
    typer.echo(f"sha256: {rule.sha256}")
    typer.echo(f"lock: {prereg.lock_status(cfg)}")
    tiers = ", ".join(
        f"{name} {t.min}-{t.max if t.max is not None else '...'}" for name, t in rule.tiers.items()
    )
    typer.echo(f"tiers: {tiers} (under {rule.sample_min_followers} excluded)")
    typer.echo(
        f"reach: {rule.reach_platform} {rule.reach_tier}-tier, min {rule.min_posts_for_reach} "
        f"posts; Q = R_EN / R_DE; validity floor {rule.validity_min_mid_accounts} per language"
    )
    typer.echo(
        f"sourcing: score >= {rule.source_score_threshold}; slot = "
        f"{rule.slot_face} + {rule.slot_voice_gender}"
    )
    typer.echo("rules (first match wins):")
    for r in rule.rules:
        flag = " (inconclusive)" if r.inconclusive else ""
        typer.echo(f"  {r.id}: {r.when} -> {r.verdict}{flag}")


def _read_accounts(path: Path) -> list[AccountRow]:
    rows: list[AccountRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for lineno, raw in enumerate(csv.DictReader(fh), start=2):
            data: dict = {k.strip(): (v.strip() if v is not None else "") for k, v in raw.items()}
            for k in list(data):
                if data[k] == "":
                    data[k] = None
            if data.get("n_reach_posts") is None:
                data["n_reach_posts"] = 0
            for k in ("face", "voice_gender"):
                if data.get(k) is None:
                    data[k] = "unknown"
            try:
                for k in _INT_FIELDS:
                    if data.get(k) is not None:
                        data[k] = int(float(data[k]))
                for k in _FLOAT_FIELDS:
                    if data.get(k) is not None:
                        data[k] = float(data[k])
                rows.append(AccountRow.model_validate(data))
            except (ValueError, ValidationError) as exc:
                typer.echo(f"invalid account CSV, row {lineno}: {exc}", err=True)
                raise typer.Exit(1) from exc
    return rows


@app.command("decide")
def decide_cmd(
    accounts_csv: Path = typer.Option(..., "--accounts-csv", exists=True, dir_okay=False),
    log_path: Path = typer.Option(Path("docs/language-decision.md"), "--log-path"),
    amend: str | None = typer.Option(None, "--amend", help="Reason for a rule change (logged)."),
) -> None:
    """Apply the pre-registered rule to account rows; print metrics, matched row and verdict."""
    cfg = config_dir()
    db = Database(db_path())
    try:
        prereg.check_rule_unchanged(db, amend, cfg)
    except prereg.RuleChanged as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    except ValueError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    status = prereg.lock_status(cfg)
    if status != "ok":
        typer.echo(f"warning: rule lock {status} (rule not operator-approved)")
    rule = load_rule(prereg.rule_path(cfg))
    res = decide(_read_accounts(accounts_csv), rule)
    m = res.metrics
    for k in ("R_DE", "R_EN", "Q", "n_mid_de", "n_mid_en", "N_DE", "N_EN", "S_DE", "S_EN"):
        typer.echo(f"{k}: {fmt_metric(m[k])}")
    typer.echo(
        f"youtube_R_DE: {fmt_metric(m['youtube_R_DE'])}  "
        f"youtube_R_EN: {fmt_metric(m['youtube_R_EN'])}"
        "  (reported only, not in Q)"
    )
    typer.echo(f"matched row: {res.matched_row}{' (inconclusive)' if res.inconclusive else ''}")
    typer.echo(f"verdict: {res.verdict}")
    typer.echo(f"rule sha256: {res.rule_sha256}")
    write_decision_log(db, res, log_path)
    typer.echo(f"logged to {log_path}")


# --- collection (plan 01-04) -----------------------------------------------------------------


@app.command("import-candidates")
def import_candidates_cmd(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Load a candidate CSV (handle,platform,language,discovery_source,query,seed_named,
    operator_decision,notes); invalid handles are rejected."""
    rep = scan_fetch.import_candidates(Database(db_path()), path)
    typer.echo(f"inserted {rep.inserted}, updated {rep.updated}, rejected {len(rep.rejected)}")
    for r in rep.rejected:
        typer.echo(f"  rejected {r}", err=True)


def _gate_errors(exc: Exception) -> None:
    if isinstance(exc, prereg.RuleNotApproved):
        typer.echo(f"refused: decision rule lock {exc} (approve the rule first)", err=True)
        raise typer.Exit(3) from exc
    if isinstance(exc, quiet_hours.QuietHours):
        typer.echo(str(exc), err=True)
        raise typer.Exit(4) from exc
    raise exc


@app.command("fetch")
def fetch_cmd(
    stage: str = typer.Option(..., "--stage", help="profile | posts"),
    only: str | None = typer.Option(None, "--only", help="Fetch just this handle."),
    lang: str | None = typer.Option(None, "--lang", help="de | en"),
    force: bool = typer.Option(False, "--force", help="Override quiet hours (logged)."),
    refresh: bool = typer.Option(False, "--refresh", help="Ignore fresh_hours (re-fetch)."),
) -> None:
    """Fetch public profile (followers/tier) or post stats, politely and resumably."""
    if stage not in ("profile", "posts"):
        typer.echo("--stage must be profile or posts", err=True)
        raise typer.Exit(2)
    if lang not in (None, "de", "en"):
        typer.echo("--lang must be de or en", err=True)
        raise typer.Exit(2)
    try:
        rep = scan_fetch.run_fetch(
            Database(db_path()),
            stage,
            lang=lang,
            only=only,
            force=force,
            refresh=refresh,
            cfg=config_dir(),
        )
    except (prereg.RuleNotApproved, quiet_hours.QuietHours) as exc:
        _gate_errors(exc)
        return
    for line in rep.lines:
        typer.echo(line)
    typer.echo(
        f"scan_run {rep.run_id} ({rep.stage}): ok {len(rep.ok)}, skipped fresh "
        f"{len(rep.skipped)}, failed {len(rep.failed)}, stopped {len(rep.stopped)}"
    )


@app.command("add-manual")
def add_manual_cmd(
    handle: str = typer.Option(..., "--handle"),
    platform: str = typer.Option(..., "--platform", help="tiktok | youtube"),
    followers: int | None = typer.Option(None, "--followers"),
    views: str = typer.Option("", "--views", help="Comma list, newest first, posts >= 72 h old."),
    lang: str | None = typer.Option(None, "--lang", help="Required for a handle not yet listed."),
) -> None:
    """Operator entry fallback: followers + up to 15 view counts typed from the app."""
    try:
        nums = [int(v.strip().replace("_", "")) for v in views.split(",") if v.strip()]
        res = scan_fetch.add_manual(
            Database(db_path()),
            handle,
            platform,
            followers,
            nums,
            language=lang,
            cfg=config_dir(),
        )
    except ValueError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        f"stored {platform}:{handle} (operator_entered): tier {res['tier']}, "
        f"{res['n']} views, median {res['reach_median']}"
    )
