"""Pre-registration guard: lock validation, scan_run hash, amendment logging, decide CLI."""

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from ndc.cli import app
from ndc.db import Database
from ndc.scan import prereg
from ndc.scan.decide import current_language

REPO_RULE = Path(__file__).resolve().parents[2] / "config" / "decision_rule.yaml"

CSV_HEADER = (
    "handle,language,platform,followers,reach_median,n_reach_posts,"
    "source_citing_score,face,voice_gender\n"
)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    d = tmp_path / "config"
    d.mkdir()
    shutil.copy(REPO_RULE, d / "decision_rule.yaml")
    monkeypatch.setenv("NDC_CONFIG_DIR", str(d))
    return d


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


def write_lock(cfg, *, sha=None, approved_at="2026-10-24T12:00:00Z"):
    data = {
        "sha256": sha or hashlib.sha256((cfg / "decision_rule.yaml").read_bytes()).hexdigest(),
        "approved_by": "operator",
        "rule_file": "config/decision_rule.yaml",
    }
    if approved_at is not None:
        data["approved_at"] = approved_at
    (cfg / "decision_rule.lock").write_text(json.dumps(data), encoding="utf-8")


def edit_rule(cfg):
    p = cfg / "decision_rule.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")


def test_lock_missing_raises(cfg):
    with pytest.raises(prereg.RuleNotApproved):
        prereg.assert_rule_approved(cfg)


def test_lock_sha_mismatch_raises(cfg):
    write_lock(cfg, sha="0" * 64)
    with pytest.raises(prereg.RuleNotApproved):
        prereg.assert_rule_approved(cfg)


def test_lock_without_approved_at_raises(cfg):
    write_lock(cfg, approved_at=None)
    with pytest.raises(prereg.RuleNotApproved):
        prereg.assert_rule_approved(cfg)


def test_valid_lock_returns_sha(cfg):
    write_lock(cfg)
    assert prereg.assert_rule_approved(cfg) == prereg.rule_sha256(cfg)


def test_scan_run_hash_and_amendment(cfg, db):
    run_id = prereg.record_scan_run(db, "fetch")
    conn = db.connect()
    try:
        sha = conn.execute("SELECT rule_sha256 FROM scan_run WHERE id=?", (run_id,)).fetchone()[0]
    finally:
        conn.close()
    assert sha == prereg.rule_sha256(cfg)
    prereg.check_rule_unchanged(db, None)  # unchanged -> ok

    edit_rule(cfg)
    with pytest.raises(prereg.RuleChanged):
        prereg.check_rule_unchanged(db, None)

    prereg.check_rule_unchanged(db, "typo fix")
    conn = db.connect()
    try:
        rows = conn.execute("SELECT old_sha256, new_sha256, reason FROM rule_amendment").fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["old_sha256"] == sha and rows[0]["reason"] == "typo fix"
    # the amended hash is now the reference: no second --amend needed
    prereg.check_rule_unchanged(db, None)


def test_amend_reason_too_short(cfg, db):
    prereg.record_scan_run(db, "fetch")
    edit_rule(cfg)
    with pytest.raises(ValueError):
        prereg.check_rule_unchanged(db, "ok")


def test_no_scan_run_means_nothing_to_compare(cfg, db):
    edit_rule(cfg)
    prereg.check_rule_unchanged(db, None)


def _csv(tmp_path):
    lines = [CSV_HEADER]
    for i in range(10):
        lines.append(f"de{i},de,tiktok,50000,1000,15,0,face,female\n")
        lines.append(f"en{i},en,tiktok,50000,8000,15,0,face,female\n")
    lines.append("dsrc,de,tiktok,5000,,3,3,faceless,male\n")
    lines.append("ytbig,en,youtube,60000,900000,15,,unknown,unknown\n")
    p = tmp_path / "accounts.csv"
    p.write_text("".join(lines), encoding="utf-8")
    return p


def test_cli_decide_ok_writes_log_and_row(cfg, db, runner, tmp_path):
    log = tmp_path / "decision.md"
    res = runner.invoke(
        app, ["scan", "decide", "--accounts-csv", str(_csv(tmp_path)), "--log-path", str(log)]
    )
    assert res.exit_code == 0, res.output
    assert "R1" in res.output and "verdict: de" in res.output and "Q" in res.output
    text = log.read_text(encoding="utf-8")
    assert "Validation week 1" in text and "R1" in text
    assert "sourced, male, faceless German account" in text
    assert current_language(db) == "de"


def test_cli_decide_exits_2_on_changed_rule(cfg, db, runner, tmp_path):
    prereg.record_scan_run(db, "fetch")
    edit_rule(cfg)
    args = ["scan", "decide", "--accounts-csv", str(_csv(tmp_path)), "--log-path",
            str(tmp_path / "d.md")]
    res = runner.invoke(app, args)
    assert res.exit_code == 2, res.output
    assert current_language(db) is None
    res = runner.invoke(app, [*args, "--amend", "clarified wording"])
    assert res.exit_code == 0, res.output


def test_cli_decide_bad_csv_row(cfg, runner, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(CSV_HEADER + "x,fr,tiktok,50000,1000,15,0,face,female\n", encoding="utf-8")
    res = runner.invoke(
        app, ["scan", "decide", "--accounts-csv", str(p), "--log-path", str(tmp_path / "d.md")]
    )
    assert res.exit_code == 1
    assert "row 2" in res.output


def test_cli_rule_show_lock_missing(cfg, runner):
    res = runner.invoke(app, ["scan", "rule", "show"])
    assert res.exit_code == 0, res.output
    assert "lock: missing" in res.output
    assert prereg.rule_sha256(cfg) in res.output
