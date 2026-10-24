import os
import sqlite3
from pathlib import Path

from ndc.cli import app

FIXTURE = str(Path(__file__).parent / "fixtures" / "topic_seed_small.yaml")

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
    assert header == (
        "id,pillar,condition,domain,audience,angle,working_title,list_tag,safety_status,"
        "source_likely,status"
    )
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


def test_import_and_filter(runner):
    res = runner.invoke(app, ["topic", "import", FIXTURE])
    assert res.exit_code == 0, res.output
    assert "inserted 8" in res.output
    res = runner.invoke(app, ["topic", "import", FIXTURE])
    assert res.exit_code == 0, res.output
    assert "inserted 0" in res.output
    res = runner.invoke(
        app, ["topic", "list", "--pillar", "parents", "--condition", "adhd", "--format", "csv"]
    )
    assert res.exit_code == 0, res.output
    lines = res.output.splitlines()
    assert len(lines) == 2
    assert "Morgenroutine mit Bildkarten" in lines[1]
    assert ",whitelist,ok," in lines[1]
    for flag, value, n in [
        ("--domain", "sleep", 1),
        ("--audience", "partners", 1),
        ("--angle", "mechanism_why", 2),
        ("--tag", "blacklist", 2),
        ("--status", "proposed", 8),
    ]:
        res = runner.invoke(app, ["topic", "list", flag, value, "--format", "csv"])
        assert res.exit_code == 0, res.output
        assert len(res.output.splitlines()) == n + 1, (flag, res.output)


def test_list_table_shows_tag_and_safety(runner):
    runner.invoke(app, ["topic", "import", FIXTURE])
    res = runner.invoke(app, ["topic", "list", "--domain", "sleep"])
    assert res.exit_code == 0, res.output
    assert "whitelist" in res.output and "blocked" in res.output


def test_list_unknown_filter_value(runner):
    res = runner.invoke(app, ["topic", "list", "--pillar", "foo"])
    assert res.exit_code != 0
    assert "challenge_science_help" in res.output


def test_import_bad_vocab_exits_nonzero(runner, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        Path(FIXTURE).read_text(encoding="utf-8").replace("condition: dyslexia", "condition: adhs"),
        encoding="utf-8",
    )
    res = runner.invoke(app, ["topic", "import", str(bad)])
    assert res.exit_code != 0
    assert "adhs" in res.output
    res = runner.invoke(app, ["topic", "list", "--format", "csv"])
    assert len(res.output.splitlines()) == 1


def test_add_rejects_unknown_vocab(runner):
    args = [a if a != "adhd" else "adhs" for a in ADD_ARGS]
    res = runner.invoke(app, [*args, "--tag", "whitelist"])
    assert res.exit_code != 0
    assert "adhs" in res.output


def _csv_status(runner, topic_id):
    res = runner.invoke(app, ["topic", "list", "--format", "csv"])
    for line in res.output.splitlines()[1:]:
        if line.split(",")[0] == str(topic_id):
            return line.rsplit(",", 1)[1]
    return None


def test_keep_kill_select_cli(runner):
    runner.invoke(app, ["topic", "import", FIXTURE])
    res = runner.invoke(app, ["topic", "keep", "3", "5"])
    assert res.exit_code == 0, res.output
    assert _csv_status(runner, 3) == "backlog"
    assert runner.invoke(app, ["topic", "keep", "3"]).exit_code != 0
    res = runner.invoke(app, ["topic", "kill", "4", "--reason", "zu nah an Diagnosefrage"])
    assert res.exit_code == 0, res.output
    assert _csv_status(runner, 4) == "rejected"
    assert runner.invoke(app, ["topic", "kill", "1", "--reason", "kurz"]).exit_code != 0
    assert _csv_status(runner, 1) == "proposed"
    res = runner.invoke(app, ["topic", "select", "3"])
    assert res.exit_code == 0, res.output
    assert _csv_status(runner, 3) == "selected"
    runner.invoke(app, ["topic", "keep", "2"])
    res = runner.invoke(app, ["topic", "select", "2"])
    assert res.exit_code != 0
    assert "blocked" in res.output
    assert _csv_status(runner, 2) == "backlog"


def test_review_interactive(runner):
    runner.invoke(app, ["topic", "import", FIXTURE])
    res = runner.invoke(app, ["topic", "review"], input="k\nx\nzu nah an Diagnosefrage\ns\nq\n")
    assert res.exit_code == 0, res.output
    assert "time_perception" in res.output  # all five dimensions are shown
    assert "any.medication_names" in res.output  # safety hits are shown
    assert _csv_status(runner, 1) == "backlog"
    assert _csv_status(runner, 2) == "rejected"
    assert _csv_status(runner, 3) == "proposed"
    assert _csv_status(runner, 4) == "proposed"


def test_stats_cli(runner):
    runner.invoke(app, ["topic", "import", FIXTURE])
    runner.invoke(app, ["topic", "keep", "1"])
    res = runner.invoke(app, ["topic", "stats"])
    assert res.exit_code == 0, res.output
    for pillar in ("challenge_science_help", "strengths", "parents", "men_dads_partners"):
        assert pillar in res.output
    assert "below 7" in res.output


def test_stats_cli_empty_db(runner):
    res = runner.invoke(app, ["topic", "stats"])
    assert res.exit_code == 0, res.output
