import os
import sqlite3

from ndc.cli import app

ADD_ARGS = [
    "topic",
    "add",
    "--pillar",
    "parents",
    "--condition",
    "adhd",
    "--domain",
    "routines_household",
    "--audience",
    "parents",
    "--angle",
    "try_this_strategy",
    "--title",
    "Morgenroutine",
    "--source-likely",
    "yes",
]


def test_add_then_list(runner):
    res = runner.invoke(app, [*ADD_ARGS, "--tag", "whitelist"])
    assert res.exit_code == 0, res.output
    assert "1" in res.output
    res = runner.invoke(app, ["topic", "list"])
    assert res.exit_code == 0, res.output
    assert "Morgenroutine" in res.output
    assert "whitelist" in res.output


def test_list_csv_header(runner):
    runner.invoke(app, [*ADD_ARGS, "--tag", "whitelist"])
    res = runner.invoke(app, ["topic", "list", "--format", "csv"])
    assert res.exit_code == 0, res.output
    header = res.output.splitlines()[0]
    assert header == ("id,pillar,condition,domain,audience,angle,working_title,list_tag,status")
    assert "Morgenroutine" in res.output


def test_add_rejects_bad_tag(runner):
    res = runner.invoke(app, [*ADD_ARGS, "--tag", "maybe"])
    assert res.exit_code != 0
    conn = sqlite3.connect(os.environ["NDC_DB"])
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='topic'"
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM topic").fetchone()[0] if has_table else 0
    finally:
        conn.close()
    assert count == 0


def test_doctor_never_prints_key(runner, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret")
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0, res.output
    assert "sk-test-secret" not in res.output
    assert "ANTHROPIC_API_KEY: present" in res.output
    assert os.environ["NDC_DB"] in res.output
    assert "001_core.sql" in res.output


def test_doctor_reports_missing_key(runner):
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0, res.output
    assert "ANTHROPIC_API_KEY: missing" in res.output
