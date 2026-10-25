"""`ndc scan decide` reading the sample straight from the DB (plan 01-13, MKT-02, D-20)."""

import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from scan_seed import add_obs, seed_account

from ndc.cli import app
from ndc.scan import prereg, sheet
from ndc.scan.decide import AccountRow, current_language, decide, load_rule

REPO_RULE = Path(__file__).resolve().parents[2] / "config" / "decision_rule.yaml"


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    d = tmp_path / "config"
    d.mkdir()
    shutil.copy(REPO_RULE, d / "decision_rule.yaml")
    sha = hashlib.sha256((d / "decision_rule.yaml").read_bytes()).hexdigest()
    (d / "decision_rule.lock").write_text(
        json.dumps({"sha256": sha, "approved_by": "operator", "approved_at": "2026-10-24T12:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("NDC_CONFIG_DIR", str(d))
    return d


def _set_reach(db, aid, median, n=15):
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE competitor_account SET reach_median = ?, n_reach_posts = ? WHERE id = ?",
            (median, n, aid),
        )
    finally:
        conn.close()


def _seed(db):
    for i in range(9):
        _set_reach(db, seed_account(db, f"de{i}", lang="de", followers=50_000), 1000 + i)
        _set_reach(db, seed_account(db, f"en{i}", lang="en", followers=50_000), 4000 + i)
    src = seed_account(db, "dsrc", lang="de", followers=5_000)
    add_obs(db, src, "source_text_level", "3", "llm_session", "high")
    add_obs(db, src, "face", "faceless", "llm_session", "high")
    add_obs(db, src, "voice_gender", "male", "auto", "high")
    # llm_session says 2, the operator says 0: the operator value must win
    over = seed_account(db, "repost", lang="en", followers=60_000)
    add_obs(db, over, "source_text_level", "2", "llm_session", "low")
    add_obs(db, over, "source_citing_score", "0", "operator_verified", "high", "operator")
    yt = seed_account(db, "ytbig", platform="youtube", lang="en", followers=60_000)
    _set_reach(db, yt, 900_000)


def test_account_rows_match_exported_csv(cfg, db, tmp_path):
    _seed(db)
    rows = sheet.account_rows(db)
    p = tmp_path / "acc.csv"
    sheet.export_accounts(db, p)
    with p.open(encoding="utf-8") as fh:
        from_csv = [
            AccountRow.model_validate({k: (v if v != "" else None) for k, v in r.items()})
            for r in csv.DictReader(fh)
        ]
    rule = load_rule(prereg.rule_path(cfg))
    assert decide(rows, rule) == decide(from_csv, rule)


def test_operator_score_overrides_llm_levels(cfg, db):
    _seed(db)
    by = {r.handle: r for r in sheet.account_rows(db)}
    assert by["repost"].source_citing_score == 0
    assert by["dsrc"].source_citing_score == 3


def test_decide_from_db_writes_log_and_row(cfg, db, runner, tmp_path):
    _seed(db)
    prereg.record_scan_run(db, "fetch")
    log = tmp_path / "decision.md"
    res = runner.invoke(
        app,
        [
            "scan",
            "decide",
            "--log-path",
            str(log),
            "--rule-committed-at",
            "2026-10-24T11:00:00+00:00",
        ],
    )
    assert res.exit_code == 0, res.output
    assert "verdict: de" in res.output and "matched row: R1" in res.output
    text = log.read_text(encoding="utf-8")
    assert "Validation week 1" in text
    assert "sourced, male, faceless German account" in text and "tiktok:dsrc" in text
    assert "precedes the first scan_run: yes" in text
    assert "one language only" in text
    assert "de tiktok mid" in text
    assert current_language(db) == "de"
    assert "input: db:selected sample" in text and "rule lock ok" in text


def test_decide_from_db_refuses_changed_rule(cfg, db, runner, tmp_path):
    _seed(db)
    prereg.record_scan_run(db, "fetch")
    p = cfg / "decision_rule.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    log = tmp_path / "decision.md"
    res = runner.invoke(app, ["scan", "decide", "--log-path", str(log)])
    assert res.exit_code == 3, res.output  # HI-03: lock no longer matches -> refused first
    assert "refused: rule lock" in res.output
    assert not log.exists()
    assert current_language(db) is None


def test_verify_accept_clears_queue_without_changing_values(db, runner):
    aid = seed_account(db, "carousel", lang="en")
    add_obs(db, aid, "face", "unknown", "llm_session", "low")
    from ndc.scan import queue

    queue.recompute(db, aid)
    res = runner.invoke(
        app,
        ["scan", "verify", "carousel", "--platform", "tiktok", "--accept", "--note", "ok"],
    )
    assert res.exit_code == 0, res.output
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT face, face_provenance, needs_operator_check FROM v_competitor_sheet"
            " WHERE account_id = ?",
            (aid,),
        ).fetchone()
    finally:
        conn.close()
    assert row["face"] == "unknown" and row["face_provenance"] == "llm_session"
    assert row["needs_operator_check"] == "false"
