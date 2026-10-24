"""`ndc check FILE|--text ... --lang de|en`: exit 0 ok, 1 blocked, 2 needs_override."""

import sys
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.table import Table

from ndc.checks.engine import CheckResult, check, record_override, rule_tier
from ndc.config import db_path
from ndc.db import Database

app = typer.Typer(
    help="Terminology and safety checks.",
    context_settings={"allow_interspersed_args": True},
)

_EXIT = {"ok": 0, "blocked": 1, "needs_override": 2}


def _console() -> Console:
    return Console(width=None if sys.stdout.isatty() else 200)


def _render(res: CheckResult) -> None:
    con = _console()
    if res.findings:
        table = Table(show_lines=False)
        for col in ("tier", "rule_id", "matched", "suggest", "message"):
            table.add_column(col)
        for f in res.findings:
            tier = f.tier
            if f.tier == "warn" and f.rule_id in res.overridden_rule_ids:
                tier = "warn (overridden)"
            table.add_row(tier, f.rule_id, f.matched_text, f.suggest or "", f.message)
        con.print(table)
    con.print(
        f"status: {res.status}  sha256: {res.text_sha256[:12]}  "
        f"terminology v{res.terminology_version}"
    )


@app.callback(invoke_without_command=True)
def run(
    file: Path | None = typer.Argument(
        None, help="Text file to check.", exists=True, dir_okay=False
    ),
    text: str | None = typer.Option(None, "--text", help="Check this text instead of a file."),
    lang: str = typer.Option(..., "--lang", help="de or en."),
    level: str = typer.Option("script", "--level", help="topic, script or claim."),
    override: list[str] | None = typer.Option(
        None,
        "--override",
        help='Record a warn override for this exact text: RULE_ID="reason" (repeatable).',
    ),
) -> None:
    """Check text for terminology findings (block/warn) and blacklisted subjects."""
    if (file is None) == (text is None):
        raise typer.BadParameter("pass exactly one of FILE or --text")
    if lang not in ("de", "en"):
        raise typer.BadParameter("--lang must be de or en")
    if level not in ("topic", "script", "claim"):
        raise typer.BadParameter("--level must be topic, script or claim")
    body = text if text is not None else file.read_text(encoding="utf-8")
    lang_l: Literal["de", "en"] = lang  # type: ignore[assignment]
    level_l: Literal["topic", "script", "claim"] = level  # type: ignore[assignment]
    pairs = [_parse_override(o) for o in override or []]
    for rule_id, _reason in pairs:
        tier = rule_tier(rule_id)
        if tier == "block":
            _console().print(f"{rule_id}: block findings cannot be overridden (D-12).")
            raise typer.Exit(1)
        if tier is None:
            raise typer.BadParameter(f"unknown rule_id {rule_id!r}", param_hint="--override")
    db = Database(db_path())
    for rule_id, reason in pairs:
        try:
            record_override(db, body, rule_id, level_l, reason)
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint="--override") from exc
        _console().print(f"override recorded: {rule_id} ({reason})")
    res = check(body, lang_l, level_l, db=db)
    _render(res)
    raise typer.Exit(_EXIT[res.status])


def _parse_override(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise typer.BadParameter(f'expected RULE_ID="reason", got {raw!r}', param_hint="--override")
    rule_id, reason = raw.split("=", 1)
    reason = reason.strip()
    if len(reason) >= 2 and reason[0] == reason[-1] and reason[0] in "\"'":
        reason = reason[1:-1]
    return rule_id.strip(), reason.strip()
