"""Competitor sheet view + CSV exports (Task 3)."""

import csv
import os

import pytest

from ndc.cli import app
from ndc.db import Database
from ndc.scan import sheet
from ndc.scan.cli import _read_accounts

COLUMNS = [
    "handle", "platform", "language", "followers", "tier", "median_views_15", "n_reach_posts",
    "source_citing_score", "source_citing_provenance", "face", "face_provenance", "voice_gender",
    "voice_gender_provenance", "format", "cadence_posts_per_week", "pillars", "audiences",
    "monetization_signals", "saves_per_1k", "shares_per_1k", "needs_operator_check", "seed_named",
    "discovery_source",
]
DAY = 86400


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


def _account(conn, handle="kirmesimkopf", platform="tiktok", lang="de", followers=25000):
    cid = conn.execute(
        "INSERT INTO competitor_candidate (handle, platform, language, discovery_source,"
        " seed_named, status, created_at) VALUES (?, ?, ?, 'seed_d04', 1, 'selected', 'x')",
        (handle, platform, lang),
    ).lastrowid
    return conn.execute(
        "INSERT INTO competitor_account (candidate_id, handle, platform, language, followers,"
        " tier, fetch_status, reach_median, n_reach_posts) VALUES (?, ?, ?, ?, ?, 'mid', 'ok',"
        " 8000, 15)",
        (cid, handle, platform, lang, followers),
    ).lastrowid


def _obs(conn, aid, field, value, prov, at="2026-10-24T10:00:00Z"):
    conn.execute(
        "INSERT INTO competitor_field_obs (account_id, field, value, provenance, observed_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (aid, field, value, prov, at),
    )


def _posts(conn, aid, dated=True, n=15):
    for i in range(n):
        conn.execute(
            "INSERT INTO competitor_post (account_id, post_id, posted_at, views, saves, shares,"
            " in_reach_window, captured_at) VALUES (?, ?, ?, 1000, ?, 2, 1, 'x')",
            (aid, str(i), (1792000000 - i * 2 * DAY) if dated else None, 10 if i < 10 else None),
        )


def test_view_columns(db):
    conn = db.connect()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(v_competitor_sheet)")]
    for c in COLUMNS:
        assert c in cols, c


def test_operator_verified_wins(db):
    conn = db.connect()
    aid = _account(conn)
    _obs(conn, aid, "face", "face", "auto", at="2026-10-24T12:00:00Z")
    _obs(conn, aid, "face", "faceless", "operator_verified", at="2026-10-24T09:00:00Z")
    _obs(conn, aid, "voice_gender", "male", "auto")
    row = conn.execute("SELECT * FROM v_competitor_sheet").fetchone()
    assert row["face"] == "faceless" and row["face_provenance"] == "operator_verified"
    assert row["voice_gender"] == "male" and row["voice_gender_provenance"] == "auto"
    assert row["format"] is None and row["pillars"] is None  # filled by later plans


def test_source_score_rule(db):
    conn = db.connect()
    aid = _account(conn)
    _obs(conn, aid, "source_text_level", "1", "llm_session")
    _obs(conn, aid, "source_video_level", "2", "auto")
    row = conn.execute("SELECT * FROM v_competitor_sheet").fetchone()
    assert row["source_citing_score"] == 2 and row["source_citing_provenance"] == "auto"
    _obs(conn, aid, "source_citing_score", "3", "operator_verified")
    row = conn.execute("SELECT * FROM v_competitor_sheet").fetchone()
    assert row["source_citing_score"] == 3
    assert row["source_citing_provenance"] == "operator_verified"


def test_cadence_and_per_1k(db):
    conn = db.connect()
    aid = _account(conn)
    _posts(conn, aid)
    row = conn.execute("SELECT * FROM v_competitor_sheet").fetchone()
    # 15 posts, one every 2 days -> 14 gaps over 28 days -> 3.5 posts/week
    assert row["cadence_posts_per_week"] == pytest.approx(3.5)
    assert row["saves_per_1k"] == pytest.approx(10.0)  # only posts with saves counted
    assert row["shares_per_1k"] == pytest.approx(2.0)


def test_cadence_null_without_dates(db):
    conn = db.connect()
    aid = _account(conn, "@HowtoADHD", "youtube", "en")
    _posts(conn, aid, dated=False)
    row = conn.execute("SELECT * FROM v_competitor_sheet").fetchone()
    assert row["cadence_posts_per_week"] is None


def test_export_csv(db, tmp_path, runner):
    conn = db.connect()
    _account(conn)
    out = tmp_path / "sheet.csv"
    res = runner.invoke(app, ["scan", "export", "--csv", str(out)])
    assert res.exit_code == 0, res.output
    with out.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert set(COLUMNS) <= set(reader.fieldnames)
    assert rows[0]["handle"] == "kirmesimkopf" and rows[0]["followers"] == "25000"


def test_export_accounts_csv_loads_through_accountrow(db, tmp_path, runner):
    conn = db.connect()
    aid = _account(conn)
    _obs(conn, aid, "face", "faceless", "operator_verified")
    _obs(conn, aid, "voice_gender", "weird-value", "auto")  # invalid -> unknown
    _obs(conn, aid, "source_text_level", "2", "llm_session")
    _account(conn, "@HowtoADHD", "youtube", "en", 1750000)
    out = tmp_path / "accounts.csv"
    res = runner.invoke(app, ["scan", "export", "--accounts-csv", str(out)])
    assert res.exit_code == 0, res.output
    header = out.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == list(sheet.ACCOUNT_COLUMNS)
    rows = _read_accounts(out)
    assert len(rows) == 2
    k = next(r for r in rows if r.handle == "kirmesimkopf")
    assert k.face == "faceless" and k.voice_gender == "unknown"
    assert k.source_citing_score == 2 and k.reach_median == 8000 and k.n_reach_posts == 15
