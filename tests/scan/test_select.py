"""Stratified per-language selection (D-02) and operator include/exclude (Task 3)."""

import os

import pytest

from ndc.cli import app
from ndc.db import Database
from ndc.scan import fetch, select

HDR = "handle,platform,language,discovery_source,query,seed_named,operator_decision,notes\n"


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


def _add(conn, handle, platform, followers, lang="de", seed=0, decision=None, status="ok"):
    cid = conn.execute(
        "INSERT INTO competitor_candidate (handle, platform, language, discovery_source,"
        " seed_named, operator_decision, created_at) VALUES (?, ?, ?, 'test', ?, ?, 'x')",
        (handle, platform, lang, seed, decision),
    ).lastrowid
    tier = fetch.tier_for(followers)
    conn.execute(
        "INSERT INTO competitor_account (candidate_id, handle, platform, language, followers, tier,"
        " fetch_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cid, handle, platform, lang, followers, tier, status),
    )


def _pool(db, n_mid=40):
    """120 DE candidates: 10 sub-1k, 30 micro, n_mid mid, 30 macro, 10 mega; 70% TikTok."""
    conn = db.connect()
    spec = [
        ("sub", 10, 500),
        ("mic", 30, 5000),
        ("mid", n_mid, 50000),
        ("mac", 30, 500000),
        ("meg", 10, 5000000),
    ]
    for prefix, n, f in spec:
        for i in range(n):
            plat = "tiktok" if i % 10 < 7 else "youtube"
            h = f"{prefix}{i}" if plat == "tiktok" else f"@{prefix}{i}xx"
            _add(conn, h, plat, f + i)
    return conn


def _selected(conn, lang="de"):
    return conn.execute(
        "SELECT c.handle, c.platform, a.tier, a.followers FROM competitor_candidate c"
        " JOIN competitor_account a ON a.candidate_id = c.id"
        " WHERE c.status = 'selected' AND c.language = ?",
        (lang,),
    ).fetchall()


def test_stratified_quotas(db):
    conn = _pool(db)
    _add(conn, "seedmicro", "tiktok", 2000, seed=1)
    _add(conn, "@seedmega", "youtube", 3000000, seed=1)
    res = select.select(db, "de")
    rows = _selected(conn)
    tiers = [r["tier"] for r in rows]
    handles = {r["handle"] for r in rows}
    assert {"seedmicro", "@seedmega"} <= handles
    assert 38 <= len(rows) <= 42
    assert tiers.count("mid") >= 12
    assert tiers.count("mega") <= 5
    assert 8 <= tiers.count("micro") <= 12
    assert 8 <= tiers.count("macro") <= 12
    n_tt = sum(r["platform"] == "tiktok" for r in rows)
    assert 25 <= n_tt <= 31
    assert all(r["followers"] >= 1000 for r in rows)
    assert res.shortfall is None


def test_selection_is_deterministic(db):
    _pool(db)
    a = select.select(db, "de").selected
    b = select.select(db, "de").selected
    assert a == b


def test_mid_shortfall_recorded(db, runner):
    conn = _pool(db, n_mid=7)
    res = runner.invoke(app, ["scan", "select", "--lang", "de"])
    assert res.exit_code == 0, res.output
    assert "mid tier shortfall: 7 of 12" in res.output
    rows = _selected(conn)
    assert [r["tier"] for r in rows].count("mid") == 7
    assert len(rows) >= 38
    notes = conn.execute("SELECT notes FROM scan_run WHERE stage = 'select'").fetchone()[0]
    assert "mid tier shortfall: 7 of 12" in notes


def test_operator_decisions_override_quotas(db):
    conn = _pool(db)
    _add(conn, "tiny", "tiktok", 1500, decision="include")
    _add(conn, "@megaextra", "youtube", 9000000, decision="include")
    conn.execute("UPDATE competitor_candidate SET operator_decision='exclude' WHERE handle='mid0'")
    for i in range(10):  # include more mega accounts than the mega cap
        conn.execute(
            "UPDATE competitor_candidate SET operator_decision='include' WHERE handle=?",
            (f"meg{i}" if i % 10 < 7 else f"@meg{i}xx",),
        )
    select.select(db, "de")
    rows = {r["handle"]: r for r in _selected(conn)}
    assert "tiny" in rows and "@megaextra" in rows
    assert "mid0" not in rows
    assert sum(r["tier"] == "mega" for r in rows.values()) == 11
    st = conn.execute("SELECT status FROM competitor_candidate WHERE handle='mid0'").fetchone()[0]
    assert st == "excluded"


def test_seed_not_on_platform_recorded(db):
    conn = _pool(db)
    _add(conn, "ghostseed", "tiktok", None, seed=1, status="no_data")
    res = select.select(db, "de")
    assert any("ghostseed" in n and "not on platform" in n for n in res.notes)
    assert "ghostseed" not in {r["handle"] for r in _selected(conn)}


def test_reimport_updates_operator_decision(db, tmp_path):
    p = tmp_path / "c.csv"
    p.write_text(HDR + "abc,tiktok,de,ops,,0,,\n", encoding="utf-8")
    fetch.import_candidates(db, p)
    p.write_text(HDR + "abc,tiktok,de,ops,,0,exclude,\n", encoding="utf-8")
    fetch.import_candidates(db, p)
    conn = db.connect()
    row = conn.execute("SELECT operator_decision, status FROM competitor_candidate").fetchone()
    assert tuple(row) == ("exclude", "excluded")
    p.write_text(HDR + "abc,tiktok,de,ops,,0,include,\n", encoding="utf-8")
    fetch.import_candidates(db, p)
    row = conn.execute("SELECT operator_decision, status FROM competitor_candidate").fetchone()
    assert tuple(row) == ("include", "candidate")
