"""`ndc scan` sub-app: `rule show`, `decide` (plan 01-03); fetch etc. follow in plan 01-04."""

import csv
from pathlib import Path

import typer
from pydantic import ValidationError

from ndc.config import config_dir, db_path
from ndc.db import Database
from ndc.scan import prereg
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
