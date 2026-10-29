import json
from pathlib import Path

import pytest

from ndc import readout
from ndc.db import Database

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def cfg(_cfg):
    """Writable config copy from tests/publish/conftest.py (autouse)."""
    return _cfg


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "t.db")


def test_rule_content_is_the_preregistered_design(cfg):
    r = readout.load_rule(cfg)
    assert r["primary_variable"] == "pillar" and len(r["arms"]) == 4
    assert r["snapshot_of_record"] == "7d" and r["min_exposure_views"] == 250
    assert r["winner"]["tie_break"] == "completion_pct" and r["otherwise"] == "inconclusive"
    assert r["composite"] == ["saves_per_1k", "shares_per_1k"]


def test_lock_writes_row_and_file(cfg, db):
    data = readout.lock(db, cfg)
    lock = json.loads((cfg / "readout_rule.lock").read_text())
    assert lock["sha256"] == data["sha256"] == readout.rule_sha(cfg)
    conn = db.connect()
    assert readout.check_locked(conn, cfg) == data["sha256"]
    assert readout.status(conn, cfg)["matches_file"] is True
    conn.close()
    with pytest.raises(readout.ReadoutChanged):
        readout.lock(db, cfg)


def test_unlocked_is_refused(cfg, db):
    conn = db.connect()
    with pytest.raises(readout.ReadoutNotLocked):
        readout.check_locked(conn, cfg)
    conn.close()


def test_changed_rule_refused_until_amended(cfg, db):
    readout.lock(db, cfg)
    p = cfg / "readout_rule.yaml"
    p.write_text(p.read_text().replace("min_exposure_views: 250", "min_exposure_views: 300"))
    conn = db.connect()
    with pytest.raises(readout.ReadoutChanged):
        readout.check_locked(conn, cfg)
    conn.close()
    with pytest.raises(ValueError):
        readout.amend(db, "x", cfg)
    data = readout.amend(db, "raise the exposure floor after week 1", cfg)
    conn = db.connect()
    assert readout.check_locked(conn, cfg) == data["sha256"]
    row = readout.latest_row(conn)
    assert row["amended_from"] is not None and row["reason"].startswith("raise")
    conn.close()


def test_rows_are_append_only(cfg, db):
    readout.lock(db, cfg)
    conn = db.connect()
    with pytest.raises(Exception, match="append-only"):
        conn.execute("UPDATE readout_rule SET sha256='x'")
    with pytest.raises(Exception, match="append-only"):
        conn.execute("DELETE FROM readout_rule")
    conn.close()


def test_cli_show_lock(cfg, db, runner, monkeypatch):
    from ndc.cli import app

    monkeypatch.setenv("NDC_DB", db.path)
    r = runner.invoke(app, ["readout", "show"])
    assert r.exit_code == 1 and "not locked" in r.output
    r = runner.invoke(app, ["readout", "lock"])
    assert r.exit_code == 0 and "locked" in r.output
    r = runner.invoke(app, ["readout", "show"])
    assert r.exit_code == 0 and "committed_at" in r.output
