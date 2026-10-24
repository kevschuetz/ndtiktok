"""`ndc check FILE|--text ... --lang de|en`: exit 0 ok, 1 blocked, 2 needs_override."""

import sys
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.table import Table

from ndc.checks.engine import CheckResult, check

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
    res = check(body, lang_l, level_l)
    _render(res)
    raise typer.Exit(_EXIT[res.status])
