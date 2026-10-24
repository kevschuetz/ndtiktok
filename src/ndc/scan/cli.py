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


@app.command("select")
def select_cmd(
    lang: str | None = typer.Option(None, "--lang", help="de | en (default both)"),
) -> None:
    """Tier-stratified ~40-per-language sample (D-02); prints counts and any shortfall."""
    from ndc.scan import select as scan_select

    db = Database(db_path())
    for language in [lang] if lang else ["de", "en"]:
        if language not in ("de", "en"):
            typer.echo("--lang must be de or en", err=True)
            raise typer.Exit(2)
        res = scan_select.select(db, language, config_dir())
        typer.echo(f"{language}: " + ", ".join(f"{k} {v}" for k, v in res.counts.items()))
        for note in res.notes:
            typer.echo(f"  {note}")


@app.command("export")
def export_cmd(
    csv_path: Path | None = typer.Option(None, "--csv", help="Full competitor sheet."),
    accounts_csv: Path | None = typer.Option(None, "--accounts-csv", help="AccountRow CSV."),
    all_accounts: bool = typer.Option(False, "--all", help="Accounts CSV: all, not just selected."),
) -> None:
    """Write the competitor sheet and/or the AccountRow CSV for `scan decide`."""
    from ndc.scan import sheet

    if not csv_path and not accounts_csv:
        typer.echo("give --csv PATH and/or --accounts-csv PATH", err=True)
        raise typer.Exit(2)
    db = Database(db_path())
    if csv_path:
        typer.echo(f"sheet: {sheet.export_sheet(db, csv_path)} rows -> {csv_path}")
    if accounts_csv:
        n = sheet.export_accounts(db, accounts_csv, selected_only=not all_accounts)
        typer.echo(f"accounts: {n} rows -> {accounts_csv}")


discover_app = typer.Typer(help="Automated candidate discovery (D-04, D-16).")
app.add_typer(discover_app, name="discover")


def _print_discover(rep) -> None:
    typer.echo(
        f"scan_run {rep.run_id} discover {rep.source} {rep.language}: {rep.requests} requests, "
        f"{rep.seen} seen, {len(rep.inserted)} new, {len(rep.existing)} already listed"
    )
    for h in rep.inserted:
        typer.echo(f"  + {h}")
    for h in getattr(rep, "conflicts", []):
        typer.echo(f"  ? {h}: already listed under the other language (flagged in notes)")
    for e in rep.errors:
        typer.echo(f"  ! {e}", err=True)


@discover_app.command("youtube")
def discover_youtube_cmd(
    lang: str = typer.Option(..., "--lang", help="de | en"),
    force: bool = typer.Option(False, "--force", help="Override quiet hours (logged)."),
) -> None:
    """ytsearch per config query; channels with >= 3 niche Shorts become candidates."""
    from ndc.scan import discover

    if lang not in ("de", "en"):
        typer.echo("--lang must be de or en", err=True)
        raise typer.Exit(2)
    try:
        rep = discover.discover_youtube(Database(db_path()), lang, force=force, cfg=config_dir())
    except (prereg.RuleNotApproved, quiet_hours.QuietHours) as exc:
        _gate_errors(exc)
        return
    _print_discover(rep)


@discover_app.command("modash")
def discover_modash_cmd(
    lang: str = typer.Option(..., "--lang", help="de | en (language of the candidates)"),
    path: list[str] = typer.Option(..., "--path", help="Public page path, e.g. tiktok/germany"),
    force: bool = typer.Option(False, "--force", help="Override quiet hours (logged)."),
) -> None:
    """TikTok handles from Modash public find-influencers pages (plain HTML, no login)."""
    from ndc.scan import discover

    if lang not in ("de", "en"):
        typer.echo("--lang must be de or en", err=True)
        raise typer.Exit(2)
    try:
        rep = discover.discover_modash(
            Database(db_path()), lang, path, force=force, cfg=config_dir()
        )
    except ValueError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    except (prereg.RuleNotApproved, quiet_hours.QuietHours) as exc:
        _gate_errors(exc)
        return
    _print_discover(rep)


# --- judgments, operator queue and spot-check (plan 01-06, D-01, D-17, D-21) -----------------


@app.command("import-judgments")
def import_judgments_cmd(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Import an in-session judgment file (config/judging_rubric.md) as provenance llm_session.

    The whole file is validated first; any invalid account refuses the file (exit 2)."""
    from ndc.scan import judging

    db = Database(db_path())
    try:
        run_id = prereg.record_scan_run(db, "import_judgments", config_dir())
        rep = judging.import_judgments(db, path, config_dir(), run_id=run_id)
    except judging.JudgmentFileError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    scan_fetch.finish_run(db, run_id)
    typer.echo(
        f"imported {rep.accounts} accounts (scan_run {run_id}): {rep.downgraded} citation(s) "
        f"downgraded by the evidence guard, {len(rep.queued)} queued for the operator"
    )
    for key in rep.queued:
        typer.echo(f"  queued {key}")


@app.command("queue")
def queue_cmd() -> None:
    """Recompute needs_operator_check for every account and print the counts."""
    from ndc.scan import queue

    counts = queue.recompute_all(Database(db_path()))
    typer.echo(f"queued {counts['queued']}, clear {counts['clear']}")


@app.command("verify")
def verify_cmd(
    handle: str | None = typer.Argument(None, help="Account handle to set values for."),
    show_queue: bool = typer.Option(False, "--queue", help="List queued accounts (DACH first)."),
    platform: str | None = typer.Option(None, "--platform", help="tiktok | youtube"),
    sets: list[str] = typer.Option([], "--set", help="FIELD=VALUE (repeatable)."),
    note: str | None = typer.Option(None, "--note", help="What you checked (logged)."),
) -> None:
    """Operator spot-check: `--queue` lists what needs a look; HANDLE --set writes
    operator_verified values that win in the competitor sheet."""
    from ndc.scan import verify

    db = Database(db_path())
    if show_queue:
        entries = verify.list_queue(db)
        typer.echo(f"{len(entries)} account(s) queued")
        for e in entries:
            typer.echo(f"\n{e.key} [{e.language}]  why: {e.reasons}")
            for f, value, prov, conf, method in e.fields:
                typer.echo(f"  {f}: {value} ({prov}, {conf or '-'}, {method or '-'})")
            for source, level, claimed, guard, ev in e.evidence:
                extra = f" claimed {claimed}" if guard == "downgraded" else ""
                typer.echo(f"  cite {source} L{level}{extra} [{guard}]: {ev!r}")
    if handle is None:
        if not show_queue:
            typer.echo("give --queue or HANDLE --platform P --set FIELD=VALUE", err=True)
            raise typer.Exit(2)
        return
    if platform not in ("tiktok", "youtube"):
        typer.echo("--platform must be tiktok or youtube", err=True)
        raise typer.Exit(2)
    if not sets:
        typer.echo("give at least one --set FIELD=VALUE", err=True)
        raise typer.Exit(2)
    try:
        flag, reasons = verify.set_fields(db, handle, platform, sets, note)
    except verify.VerifyError as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        f"stored {len(sets)} operator_verified value(s) for {platform}:{handle}; "
        f"needs_operator_check {'true' if flag else 'false'}"
    )


# --- local video analysis + judging bundles (plan 01-06, D-17, D-21) --------------------------


@app.command("analyze")
def analyze_cmd(
    only: str | None = typer.Option(None, "--only", help="Analyze just this handle."),
    lang: str | None = typer.Option(None, "--lang", help="de | en"),
    probe: bool = typer.Option(False, "--probe", help="One no-login test download per platform."),
    force: bool = typer.Option(False, "--force", help="Override quiet hours (logged)."),
    reanalyze: bool = typer.Option(False, "--reanalyze", help="Redo already analyzed accounts."),
) -> None:
    """Download ~3 recent videos per selected account (no login), transcribe, estimate voice
    from pitch, build a contact sheet, delete the videos.

    Heavy: run it via `docker compose run --rm ndc-heavy scan analyze` (3g cap, nice 19)."""
    from ndc.scan import analyze

    if lang not in (None, "de", "en"):
        typer.echo("--lang must be de or en", err=True)
        raise typer.Exit(2)
    db = Database(db_path())
    try:
        if probe:
            for line in analyze.probe(db, config_dir(), force=force):
                typer.echo(line)
            return
        rep = analyze.run_analyze(
            db, only=only, lang=lang, force=force, reanalyze=reanalyze, cfg=config_dir()
        )
    except (prereg.RuleNotApproved, quiet_hours.QuietHours) as exc:
        _gate_errors(exc)
        return
    for line in rep.lines:
        typer.echo(line)
    typer.echo(
        f"scan_run {rep.run_id} analyze: {len(rep.results)} account(s) processed, "
        f"{len(rep.skipped)} already analyzed (use --reanalyze)"
    )


@app.command("prepare-judging")
def prepare_judging_cmd(
    batch: str | None = typer.Option(None, "--batch", help="Print this batch's manifest path."),
    judging_dir: Path | None = typer.Option(None, "--judging-dir", help="Default from config."),
) -> None:
    """Write per-account judging bundles in batches de-1, de-2, en-1, en-2 + manifests."""
    from ndc.scan import analyze, bundle

    acfg = analyze.analysis_config(config_dir())
    out = judging_dir or Path(acfg.get("judging_dir", "/data/judging"))
    rep = bundle.prepare_judging(Database(db_path()), out, int(acfg.get("batches_per_language", 2)))
    if batch:
        if batch not in rep.manifests:
            typer.echo(f"unknown batch {batch!r}; have {', '.join(rep.manifests)}", err=True)
            raise typer.Exit(2)
        typer.echo(rep.manifests[batch])
        return
    for name, path in rep.manifests.items():
        typer.echo(f"{name}: {rep.counts[name]} accounts -> {path}")
