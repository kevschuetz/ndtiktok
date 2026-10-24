"""Gated, polite, resumable fetch orchestration + candidate import + manual entry (Task 2)."""

import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ndc.cli import app
from ndc.db import Database
from ndc.scan import fetch, prereg, quiet_hours, tiktok, youtube

REPO_CFG = Path(__file__).resolve().parents[2] / "config"
REPO_ROOT = REPO_CFG.parent
NOW = 1792800000
HDR = "handle,platform,language,discovery_source,query,seed_named,operator_decision,notes\n"


@pytest.fixture(autouse=True)
def _noon(monkeypatch):
    monkeypatch.setattr(quiet_hours, "utcnow", lambda: datetime(2026, 10, 24, 12, 0, tzinfo=UTC))


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


def _csv(tmp_path, rows):
    p = tmp_path / "cands.csv"
    p.write_text(HDR + "".join(r + "\n" for r in rows), encoding="utf-8")
    return p


def _posts(n=20):
    return [
        {
            "id": str(i),
            "timestamp": NOW - (100 + 24 * i) * 3600,
            "view_count": 1000 * (i + 1),
            "like_count": 10,
            "comment_count": 1,
            "repost_count": 2,
            "save_count": 5,
            "duration": 30,
            "description": f"p{i}",
            "pinned": False,
        }
        for i in range(n)
    ]


class Sleeps(list):
    def __call__(self, s):
        self.append(s)


def _seed(db, tmp_path, rows):
    fetch.import_candidates(db, _csv(tmp_path, rows))


def _no_writer_lock():
    conn = sqlite3.connect(os.environ["NDC_DB"], timeout=0)
    try:
        conn.execute("BEGIN IMMEDIATE")  # raises 'database is locked' if a writer is open
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def test_import_rejects_invalid_handles(db, tmp_path, runner):
    p = _csv(
        tmp_path,
        [
            "kirmesimkopf,tiktok,de,seed_d04,,1,,seed",
            "x; rm -rf,tiktok,de,seed_d04,,0,,bad",
            "@HowtoADHD,youtube,en,seed_d04,,1,include,",
            "someone,tiktok,fr,ops,,0,,bad language",
        ],
    )
    res = runner.invoke(app, ["scan", "import-candidates", str(p)])
    assert res.exit_code == 0, res.output
    assert "inserted 2" in res.output and "rejected 2" in res.output
    conn = db.connect()
    rows = {r["handle"]: dict(r) for r in conn.execute("SELECT * FROM competitor_candidate")}
    assert set(rows) == {"kirmesimkopf", "@HowtoADHD"}
    assert rows["kirmesimkopf"]["seed_named"] == 1
    assert rows["@HowtoADHD"]["operator_decision"] == "include"


def test_repo_candidates_csv_imports(db):
    rep = fetch.import_candidates(db, REPO_ROOT / "scan" / "candidates.csv")
    assert rep.rejected == []
    assert rep.inserted >= 9


def test_fetch_refuses_without_rule_lock(tmp_path, monkeypatch, runner):
    cfg = tmp_path / "config"
    cfg.mkdir()
    for f in ("decision_rule.yaml", "scan.yaml"):
        shutil.copy(REPO_CFG / f, cfg / f)
    monkeypatch.setenv("NDC_CONFIG_DIR", str(cfg))
    called = []
    monkeypatch.setattr(tiktok, "fetch_profile", lambda h: called.append(h))
    res = runner.invoke(app, ["scan", "fetch", "--stage", "profile"])
    assert res.exit_code == 3
    assert called == []


def test_profile_run_records_scan_run_and_obs(db, tmp_path, monkeypatch):
    _seed(db, tmp_path, ["kirmesimkopf,tiktok,de,seed_d04,,1,,", "@HowtoADHD,youtube,en,s,,1,,"])

    def prof(h):
        _no_writer_lock()
        return {"followers": 5046, "video_count": 212, "bio": "b", "bio_link": "l"}

    monkeypatch.setattr(tiktok, "fetch_profile", prof)
    monkeypatch.setattr(
        youtube,
        "fetch_shorts",
        lambda h, n: {
            "subscribers": 1750000,
            "channel_id": "UCabcdefghijklmnopqrstuv",
            "description": "d",
            "entries": [{"id": "abcdefghi00", "view_count": 10, "title": "t"}],
        },
    )
    sleeps = Sleeps()
    rep = fetch.run_fetch(db, "profile", sleep=sleeps, now=lambda: NOW)
    assert len(rep.ok) == 2
    conn = db.connect()
    run = conn.execute("SELECT * FROM scan_run").fetchall()
    assert len(run) == 1 and run[0]["rule_sha256"] == prereg.rule_sha256()
    assert run[0]["stage"] == "fetch_profile" and run[0]["finished_at"]
    acc = {r["handle"]: dict(r) for r in conn.execute("SELECT * FROM competitor_account")}
    assert acc["kirmesimkopf"]["followers"] == 5046 and acc["kirmesimkopf"]["tier"] == "micro"
    assert acc["@HowtoADHD"]["tier"] == "mega"
    obs = conn.execute(
        "SELECT field, provenance, scan_run_id FROM competitor_field_obs WHERE field='followers'"
    ).fetchall()
    assert len(obs) == 2 and {o["provenance"] for o in obs} == {"scraped"}
    assert all(o["scan_run_id"] == run[0]["id"] for o in obs)
    assert len(sleeps) == 1 and all(3 <= s <= 6 for s in sleeps)


def test_fresh_accounts_are_skipped(db, tmp_path, monkeypatch):
    _seed(db, tmp_path, ["kirmesimkopf,tiktok,de,s,,1,,"])
    calls = []
    monkeypatch.setattr(
        tiktok, "fetch_profile", lambda h: calls.append(h) or {"followers": 2000, "video_count": 1}
    )
    fetch.run_fetch(db, "profile", sleep=Sleeps())
    rep = fetch.run_fetch(db, "profile", sleep=Sleeps())
    assert calls == ["kirmesimkopf"]
    assert rep.skipped == ["tiktok:kirmesimkopf"]
    fetch.run_fetch(db, "profile", sleep=Sleeps(), refresh=True)
    assert len(calls) == 2


def test_stop_after_three_consecutive_failures(db, tmp_path, monkeypatch):
    rows = [f"acct{i},tiktok,de,s,,0,," for i in range(6)] + ["@HowtoADHD,youtube,en,s,,0,,"]
    _seed(db, tmp_path, rows)
    calls = []

    def boom(h):
        calls.append(h)
        raise RuntimeError("extractor broke")

    monkeypatch.setattr(tiktok, "fetch_profile", boom)
    monkeypatch.setattr(
        youtube,
        "fetch_shorts",
        lambda h, n: {"subscribers": 5000, "entries": [], "channel_id": None},
    )
    sleeps = Sleeps()
    rep = fetch.run_fetch(db, "profile", sleep=sleeps)
    assert len(calls) == 3
    assert len(rep.stopped) == 3 and len(rep.failed) == 3
    assert rep.ok == ["youtube:@HowtoADHD"]  # another platform keeps going
    conn = db.connect()
    st = {r["handle"]: r["fetch_status"] for r in conn.execute("SELECT * FROM competitor_account")}
    assert [st[f"acct{i}"] for i in range(6)] == ["failed"] * 3 + ["stopped_failures"] * 3
    assert sleeps and all(3 <= s <= 6 for s in sleeps)


def test_none_profile_counts_as_failure(db, tmp_path, monkeypatch):
    _seed(db, tmp_path, ["a1,tiktok,de,s,,0,,"])
    monkeypatch.setattr(tiktok, "fetch_profile", lambda h: None)
    rep = fetch.run_fetch(db, "profile", sleep=Sleeps())
    assert rep.failed == ["tiktok:a1"]
    assert "add-manual" in rep.lines[0]


def test_posts_stage_writes_reach_after_fetch(db, tmp_path, monkeypatch):
    _seed(db, tmp_path, ["kirmesimkopf,tiktok,de,s,,1,,"])

    def listing(h, n):
        _no_writer_lock()
        assert n == 30
        return _posts(20)

    monkeypatch.setattr(tiktok, "fetch_posts", listing)
    rep = fetch.run_fetch(db, "posts", only="kirmesimkopf", sleep=Sleeps(), now=lambda: NOW)
    assert rep.ok == ["tiktok:kirmesimkopf"], rep.lines
    conn = db.connect()
    a = conn.execute("SELECT * FROM competitor_account").fetchone()
    assert a["reach_median"] == 8000 and a["n_reach_posts"] == 15
    assert conn.execute("SELECT count(*) FROM competitor_post").fetchone()[0] == 20
    assert (
        conn.execute("SELECT count(*) FROM competitor_post WHERE in_reach_window=1").fetchone()[0]
        == 15
    )


def test_posts_stage_default_targets_selected_only(db, tmp_path, monkeypatch):
    _seed(db, tmp_path, ["a1,tiktok,de,s,,0,,"])
    calls = []
    monkeypatch.setattr(tiktok, "fetch_posts", lambda h, n: calls.append(h) or _posts())
    fetch.run_fetch(db, "posts", sleep=Sleeps(), now=lambda: NOW)
    assert calls == []


def test_youtube_posts_use_stored_ids(db, tmp_path, monkeypatch):
    _seed(db, tmp_path, ["@HowtoADHD,youtube,en,s,,1,,"])
    monkeypatch.setattr(
        youtube,
        "fetch_shorts",
        lambda h, n: {
            "subscribers": 2000,
            "channel_id": "UCabcdefghijklmnopqrstuv",
            "description": None,
            "entries": [
                {"id": f"abcdefghi{i:02d}", "view_count": 5, "title": "t"} for i in range(9)
            ],
        },
    )
    fetch.run_fetch(db, "profile", sleep=Sleeps())

    def video(vid):
        i = int(vid[-2:])
        return {
            "id": vid,
            "timestamp": NOW - (100 + i) * 3600,
            "view_count": 100 * (i + 1),
            "like_count": 1,
            "comment_count": 0,
            "description": "d",
            "pinned_comment": "refs" if i == 0 else None,
            "duration": 50,
        }

    monkeypatch.setattr(youtube, "fetch_video", video)
    sleeps = Sleeps()
    rep = fetch.run_fetch(db, "posts", only="@HowtoADHD", sleep=sleeps, now=lambda: NOW)
    assert rep.ok == ["youtube:@HowtoADHD"], rep.lines
    assert len(sleeps) == 8  # 9 per-video requests -> 8 gaps
    conn = db.connect()
    a = conn.execute("SELECT * FROM competitor_account").fetchone()
    assert a["reach_median"] == 500 and a["n_reach_posts"] == 9


def test_add_manual(db, runner):
    views = ",".join(str(1000 * (i + 1)) for i in range(15))
    res = runner.invoke(
        app,
        [
            "scan",
            "add-manual",
            "--handle",
            "nessadhs",
            "--platform",
            "tiktok",
            "--followers",
            "25000",
            "--views",
            views,
            "--lang",
            "de",
        ],
    )
    assert res.exit_code == 0, res.output
    conn = db.connect()
    a = conn.execute("SELECT * FROM competitor_account WHERE handle='nessadhs'").fetchone()
    assert a["tier"] == "mid" and a["reach_median"] == 8000 and a["n_reach_posts"] == 15
    prov = {r["provenance"] for r in conn.execute("SELECT provenance FROM competitor_field_obs")}
    assert prov == {"operator_entered"}
    assert {r["provenance"] for r in conn.execute("SELECT provenance FROM competitor_post")} == {
        "operator_entered"
    }


def test_add_manual_rejects_bad_handle(runner):
    res = runner.invoke(
        app,
        [
            "scan",
            "add-manual",
            "--handle",
            "x; rm -rf",
            "--platform",
            "tiktok",
            "--followers",
            "5",
            "--lang",
            "de",
        ],
    )
    assert res.exit_code == 2
