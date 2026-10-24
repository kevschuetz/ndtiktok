from pathlib import Path

from ndc.cli import app

FIX = Path(__file__).resolve().parent / "fixtures"


def test_sample_de_blocks_and_lists_findings(runner):
    res = runner.invoke(
        app, ["check", str(FIX / "sample_script_de.txt"), "--lang", "de", "--level", "script"]
    )
    assert res.exit_code == 1, res.output
    for rid in ("de.leiden_an", "de.hochfunktional", "any.asperger"):
        assert rid in res.output
    assert "autistische Menschen" in res.output  # suggestion printed


def test_clean_text_exits_zero(runner):
    res = runner.invoke(
        app,
        [
            "check",
            "--text",
            "Manche Menschen mit ADHS erleben Zeit anders.",
            "--lang",
            "de",
            "--level",
            "script",
        ],
    )
    assert res.exit_code == 0, res.output


def test_safety_topic_exits_one(runner):
    res = runner.invoke(
        app, ["check", "--text", "Ist mein Kind autistisch?", "--lang", "de", "--level", "topic"]
    )
    assert res.exit_code == 1, res.output


def test_warn_only_exits_two(runner):
    res = runner.invoke(app, ["check", "--text", "Er leidet an ADHS.", "--lang", "de"])
    assert res.exit_code == 2, res.output
    assert "de.leiden_an" in res.output


def test_requires_file_or_text(runner):
    res = runner.invoke(app, ["check", "--lang", "de"])
    assert res.exit_code != 0
