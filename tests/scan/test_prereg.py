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
    write_lock(cfg)
    log = tmp_path / "decision.md"
    csv_path = _csv(tmp_path)
    res = runner.invoke(
        app, ["scan", "decide", "--accounts-csv", str(csv_path), "--log-path", str(log)]
    )
    assert res.exit_code == 0, res.output
    assert "R1" in res.output and "verdict: de" in res.output and "Q" in res.output
    text = log.read_text(encoding="utf-8")
    assert "Validation week 1" in text and "R1" in text
    assert "sourced, male, faceless German account" in text
    assert current_language(db) == "de"
    # HI-03 provenance: lock state, amendment and input source (with the CSV's hash)
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert f"input: csv:{csv_path} sha256:{digest}" in text
    assert "rule lock ok; amendment logged in this run: none" in text
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT lock_status, amendment_id, input_source FROM language_decision"
        ).fetchone()
    finally:
        conn.close()
    assert tuple(row) == ("ok", None, f"csv:{csv_path} sha256:{digest}")


@pytest.mark.parametrize("lock", ["missing", "mismatch", "no_approved_at"])
def test_cli_decide_refuses_without_valid_lock(cfg, db, runner, tmp_path, lock):
    """HI-03: no decision (exit 3, nothing logged) unless the rule lock is ok."""
    if lock == "mismatch":
        write_lock(cfg, sha="0" * 64)
    elif lock == "no_approved_at":
        write_lock(cfg, approved_at=None)
    log = tmp_path / "decision.md"
    res = runner.invoke(
        app, ["scan", "decide", "--accounts-csv", str(_csv(tmp_path)), "--log-path", str(log)]
    )
    assert res.exit_code == 3, res.output
    assert "refused: rule lock" in res.output
    assert not log.exists() and current_language(db) is None


def test_cli_decide_lock_checked_before_amendment_is_committed(cfg, db, runner, tmp_path):
    """A refused run must not leave a rule_amendment row behind."""
    write_lock(cfg)
    prereg.record_scan_run(db, "fetch")
    edit_rule(cfg)  # lock no longer matches
    res = runner.invoke(
        app,
        [
            "scan",
            "decide",
            "--accounts-csv",
            str(_csv(tmp_path)),
            "--log-path",
            str(tmp_path / "d"),
        ],
    )
    assert res.exit_code == 3, res.output
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM rule_amendment").fetchone()[0] == 0
    finally:
        conn.close()


def test_cli_decide_exits_2_on_changed_rule(cfg, db, runner, tmp_path):
    """Lock re-approved for the edited rule, but the rule differs from the first scan_run's:
    exit 2 without --amend; with --amend the amendment is logged and recorded with the row."""
    prereg.record_scan_run(db, "fetch")
    edit_rule(cfg)
    write_lock(cfg)
    args = [
        "scan",
        "decide",
        "--accounts-csv",
        str(_csv(tmp_path)),
        "--log-path",
        str(tmp_path / "d.md"),
    ]
    res = runner.invoke(app, args)
    assert res.exit_code == 2, res.output
    assert current_language(db) is None
    res = runner.invoke(app, [*args, "--amend", "clarified wording"])
    assert res.exit_code == 0, res.output
    text = (tmp_path / "d.md").read_text(encoding="utf-8")
    assert "rule lock ok; amendment logged in this run: #1 (clarified wording)" in text
    conn = db.connect()
    try:
        row = conn.execute("SELECT lock_status, amendment_id FROM language_decision").fetchone()
    finally:
        conn.close()
    assert tuple(row) == ("ok", 1)


def test_cli_decide_amendment_path_with_unapproved_lock_is_recorded(cfg, db, runner, tmp_path):
    prereg.record_scan_run(db, "fetch")
    write_lock(cfg)
    edit_rule(cfg)  # lock mismatched: only the explicit amendment path may proceed
    log = tmp_path / "d.md"
    res = runner.invoke(
        app,
        [
            "scan",
            "decide",
            "--accounts-csv",
            str(_csv(tmp_path)),
            "--log-path",
            str(log),
            "--amend",
            "operator-approved rewording",
        ],
    )
    assert res.exit_code == 0, res.output
    text = log.read_text(encoding="utf-8")
    assert "rule lock invalid: lock sha256 does not match" in text
    assert "#1 (operator-approved rewording)" in text


def test_cli_decide_bad_csv_row(cfg, runner, tmp_path):
    write_lock(cfg)
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
