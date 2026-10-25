"""Automated discovery (D-04, D-16): ytsearch YouTube channels and Modash public pages."""

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from ndc.cli import app
from ndc.db import Database
from ndc.scan import discover, quiet_hours

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "scan"
REPO_CFG = Path(__file__).resolve().parents[2] / "config"
# Discovery knobs and queries are pinned here, not read from the tunable live config/scan.yaml
# (LO-03: plan 01-07 retuned ytsearch_results/min_niche_shorts and broke these tests).
DE_QUERIES = ["ADHS", "Autismus", "ADHS Eltern", "ADHS Männer", "ADHS Papa", "Neurodivergenz"]
EN_QUERIES = ["ADHD", "autism", "ADHD parenting", "ADHD men"]
SEARCH = json.loads((FIX / "ytsearch.json").read_text(encoding="utf-8"))

MODASH_HTML = (
    '<p>For example, <a href="https://tiktok.com/@itsmiriamjolien" class="x">@itsmiriamjolien</a>,'
    ' <a href="https://tiktok.com/@holzbible" target="_blank">@holzbible</a> and'
    ' <a href="https://www.tiktok.com/@itsmiriamjolien/video/1">again</a>'
    ' <a href="https://tiktok.com/@bad;handle">x</a></p>'
)


@pytest.fixture(autouse=True)
def _noon(monkeypatch):
    monkeypatch.setattr(quiet_hours, "utcnow", lambda: datetime(2026, 10, 24, 12, 0, tzinfo=UTC))


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    """Repo config (rule lock etc.) with a pinned discovery section in scan.yaml."""
    c = tmp_path / "config"
    shutil.copytree(REPO_CFG, c)
    scan = yaml.safe_load((c / "scan.yaml").read_text(encoding="utf-8"))
    scan["discovery"] = {"ytsearch_results": 30, "min_niche_shorts": 3}
    scan["queries"] = {"de": DE_QUERIES, "en": EN_QUERIES}
    (c / "scan.yaml").write_text(yaml.safe_dump(scan, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("NDC_CONFIG_DIR", str(c))
    return c


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


class Sleeps(list):
    def __call__(self, s):
        self.append(s)


def _search(query, n):
    assert n == 30
    return SEARCH.get(query, {"entries": []})


def test_parse_search_drops_long_videos():
    hits = discover.parse_search(SEARCH["ADHS"])
    assert len(hits) == 5
    assert hits[0] == {
        "video_id": "aaaaaaaaa01",
        "channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa",
        "uploader_id": "@adhsalltag",
        "channel": "ADHS Alltag",
    }


def test_aggregate_keeps_channels_with_three_shorts():
    res = {q: discover.parse_search(v) for q, v in SEARCH.items()}
    chans = discover.aggregate_channels(res, 3)
    by = {c["channel_id"]: c for c in chans}
    # A: 3 distinct Shorts (the duplicate and the 900 s video do not count); B: 3; C: 3; D: 1
    assert set(by) == {
        "UCaaaaaaaaaaaaaaaaaaaaaa",
        "UCbbbbbbbbbbbbbbbbbbbbbb",
        "UCcccccccccccccccccccccc",
    }
    assert by["UCaaaaaaaaaaaaaaaaaaaaaa"]["handle"] == "@adhsalltag"
    assert by["UCcccccccccccccccccccccc"]["handle"] == "UCcccccccccccccccccccccc"  # id fallback
    assert by["UCaaaaaaaaaaaaaaaaaaaaaa"]["queries"] == ["ADHS", "Autismus", "ADHS Eltern"]


def test_discover_youtube_inserts_candidates(db):
    sleeps = Sleeps()
    rep = discover.discover_youtube(db, "de", sleep=sleeps, search=_search)
    assert rep.requests == len(DE_QUERIES)  # one request per DE query in the pinned scan.yaml
    assert len(sleeps) == len(DE_QUERIES) - 1 and all(3 <= s <= 6 for s in sleeps)
    assert sorted(rep.inserted) == ["@adhsalltag", "@autismuswissen", "UCcccccccccccccccccccccc"]
    conn = db.connect()
    rows = conn.execute("SELECT * FROM competitor_candidate ORDER BY handle").fetchall()
    assert {r["discovery_source"] for r in rows} == {"ytsearch"}
    assert {r["language"] for r in rows} == {"de"} and {r["platform"] for r in rows} == {"youtube"}
    run = conn.execute("SELECT stage, rule_sha256, notes FROM scan_run").fetchone()
    assert run["stage"] == "discover" and run["rule_sha256"] and "3 new candidates" in run["notes"]
    rep2 = discover.discover_youtube(db, "de", sleep=Sleeps(), search=_search)
    assert rep2.inserted == [] and len(rep2.existing) == 3


def test_discover_youtube_refused_in_quiet_hours(db, monkeypatch, runner):
    monkeypatch.setattr(quiet_hours, "utcnow", lambda: datetime(2026, 10, 24, 3, 0, tzinfo=UTC))
    monkeypatch.setattr(discover, "search_youtube", lambda q, n: pytest.fail("network call"))
    res = runner.invoke(app, ["scan", "discover", "youtube", "--lang", "de"])
    assert res.exit_code == 4


def test_parse_modash():
    assert discover.parse_modash(MODASH_HTML) == ["itsmiriamjolien", "holzbible"]


def test_modash_path_validation():
    assert discover.modash_url("tiktok/germany") == (
        "https://www.modash.io/find-influencers/tiktok/germany"
    )
    for bad in ("../etc", "tiktok/germany?x=1", "https://evil.example", "youtube/x"):
        with pytest.raises(ValueError):
            discover.modash_url(bad)


def test_discover_modash(db):
    rep = discover.discover_modash(
        db, "de", ["tiktok/germany"], sleep=Sleeps(), get=lambda p: MODASH_HTML
    )
    assert rep.inserted == ["itsmiriamjolien", "holzbible"]
    conn = db.connect()
    srcs = {r[0] for r in conn.execute("SELECT discovery_source FROM competitor_candidate")}
    assert srcs == {"modash"}


def test_import_keeps_operator_discovery_source(db, tmp_path):
    from ndc.scan import fetch

    p = tmp_path / "c.csv"
    p.write_text(
        "handle,platform,language,discovery_source,query,seed_named,operator_decision,notes\n"
        "someadhs,tiktok,de,creative_center,ADHS,0,,exported from Creative Center\n"
        "otheradhs,tiktok,de,exolyt,ADHS Eltern,0,,\n",
        encoding="utf-8",
    )
    fetch.import_candidates(db, p)
    conn = db.connect()
    got = dict(conn.execute("SELECT handle, discovery_source FROM competitor_candidate"))
    assert got == {"someadhs": "creative_center", "otheradhs": "exolyt"}


def test_other_language_match_is_flagged(db):
    discover.discover_youtube(db, "de", sleep=Sleeps(), search=_search)
    en_search = {
        "ADHD": SEARCH["ADHS"],
        "autism": SEARCH["Autismus"],
        "ADHD parenting": SEARCH["ADHS Eltern"],
    }
    rep = discover.discover_youtube(
        db, "en", sleep=Sleeps(), search=lambda q, n: en_search.get(q, {"entries": []})
    )
    assert rep.inserted == [] and sorted(rep.conflicts) == sorted(rep.existing)
    conn = db.connect()
    row = conn.execute(
        "SELECT language, notes FROM competitor_candidate WHERE handle='@adhsalltag'"
    ).fetchone()
    assert row["language"] == "de"
    assert "also found by en ytsearch queries: check language" in row["notes"]


def test_discover_stops_cleanly_when_quiet_hours_begin(db, monkeypatch):
    """HI-04: discovery re-checks quiet hours before each query and stops (resumable)."""
    clock = {"t": datetime(2026, 10, 24, 0, 14, tzinfo=UTC)}
    monkeypatch.setattr(quiet_hours, "utcnow", lambda: clock["t"])
    asked = []

    def search(query, n):
        asked.append(query)
        clock["t"] = datetime(2026, 10, 24, 0, 16, tzinfo=UTC)
        return SEARCH.get(query, {"entries": []})

    rep = discover.discover_youtube(db, "de", sleep=Sleeps(), search=search)
    assert asked == ["ADHS"] and rep.stopped_quiet_hours
    conn = db.connect()
    notes = conn.execute("SELECT notes FROM scan_run").fetchone()[0]
    conn.close()
    assert "stopped_quiet_hours" in notes
