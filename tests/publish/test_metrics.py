from datetime import UTC, datetime

import pytest

from ndc.publish import metrics as pm
from ndc.publish import store as ps

TT = "https://www.tiktok.com/@quellenkopf/video/7301234567890123456"
YT = "https://youtube.com/shorts/AbCdEfGhIjk"
POSTED = "2026-11-03T17:00:00Z"


@pytest.fixture
def pubs(db, approved_sha, locked):
    t = ps.log_publication(
        db, platform="tiktok", script_sha=approved_sha, post_url=TT, posted_at=POSTED
    )
    y = ps.log_publication(
        db, platform="youtube", script_sha=approved_sha, post_url=YT, posted_at=POSTED
    )
    return t, y


def _at(hours):
    return datetime(2026, 11, 3, 17, 0, tzinfo=UTC).replace() + __import__("datetime").timedelta(
        hours=hours
    )


def test_label_windows():
    assert (
        pm.label_for_age(24) == "24h"
        and pm.label_for_age(20) == "24h"
        and pm.label_for_age(30) == "24h"
    )
    assert (
        pm.label_for_age(31) == "adhoc"
        and pm.label_for_age(70) == "72h"
        and pm.label_for_age(170) == "7d"
    )


def test_add_snapshot_manual_and_append_only(db, pubs):
    t, _ = pubs
    sid = pm.add_snapshot(
        db,
        t,
        None,
        {"views": "1.234", "saves": 12, "watched_full_pct": "41,5"},
        "manual",
        captured_at="2026-11-04T18:00:00Z",
        fyf_status="no",
        fyf_reason="unavailable to some audiences",
    )
    conn = db.connect()
    r = conn.execute("SELECT * FROM metric_snapshot WHERE id=?", (sid,)).fetchone()
    assert r["age_label"] == "24h" and r["post_age_hours"] == 25.0
    assert (
        r["views"] == 1234
        and r["saves"] == 12
        and r["watched_full_pct"] == 41.5
        and r["fyf_status"] == "no"
    )
    with pytest.raises(Exception, match="append-only"):
        conn.execute("UPDATE metric_snapshot SET views=1")
    conn.close()
    with pytest.raises(pm.MetricsError, match="fyf_status"):
        pm.add_snapshot(db, t, "24h", {}, "manual", fyf_status="maybe")


def test_due_windows_and_platform_scope(db, pubs):
    t, y = pubs
    conn = db.connect()
    d25 = pm.due(conn, _at(25))
    assert [(i["publication_id"], i["age"]) for i in d25] == [(t, "24h")]
    pm.add_snapshot(db, t, "24h", {"views": 10}, "manual", captured_at="2026-11-04T18:00:00Z")
    assert pm.due(db.connect(), _at(26)) == []
    d170 = pm.due(conn, _at(170))
    assert sorted((i["publication_id"], i["age"]) for i in d170) == sorted([(t, "7d"), (y, "7d")])
    assert [i for i in d170 if i["publication_id"] == y][0]["fields"] == "views"
    assert pm.due(conn, _at(40)) == []  # between windows
    conn.close()


def test_write_due_only_under_data(tmp_path, monkeypatch):
    with pytest.raises(pm.MetricsError, match="/data"):
        pm.write_due(tmp_path / "due.json", [])
    monkeypatch.setattr(pm, "DUE_ROOT", tmp_path)
    p = pm.write_due(
        tmp_path / "due.json", [{"publication_id": 1}], datetime(2026, 11, 4, tzinfo=UTC)
    )
    assert p.exists() and '"due"' in p.read_text() and not (tmp_path / "due.json.tmp").exists()


def test_import_csv_german_headers_unknown_column_kept(db, pubs, tmp_path):
    t, _ = pubs
    csv_path = tmp_path / "export.csv"
    csv_path.write_text(
        "\ufeffVideo-Link;Videoaufrufe;Likes;Kommentare;Geteilt;Favoriten;"
        "Durchschnittliche Wiedergabezeit;Vollständig angesehen;Traffic-Quelle\n"
        f"{TT};2.345;120;7;15;33;24,8;38,2%;Für dich\n"
        "https://www.tiktok.com/@quellenkopf/video/999;5;0;0;0;0;1;1%;Profil\n",
        encoding="utf-8",
    )
    rep = pm.import_csv(db, csv_path, captured_at="2026-11-06T18:00:00Z")
    assert (
        rep["mapped"]["views"] == "Videoaufrufe"
        and len(rep["matched"]) == 1
        and len(rep["unmatched"]) == 1
    )
    conn = db.connect()
    r = pm.snapshots(conn, t)[0]
    assert r["age_label"] == "72h" and r["views"] == 2345 and r["shares"] == 15 and r["saves"] == 33
    assert r["avg_watch_s"] == 24.8 and r["watched_full_pct"] == 38.2 and r["source"] == "csv"
    assert "Traffic-Quelle" in r["raw_json"]
    conn.close()


def test_import_csv_without_id_column_fails_clearly(db, pubs, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Spalte A,Spalte B\n1,2\n", encoding="utf-8")
    with pytest.raises(pm.MetricsError, match="csv_columns"):
        pm.import_csv(db, p)


def test_cli_add_due_show(runner, db, pubs):
    from ndc.cli import app

    t, _ = pubs
    r = runner.invoke(app, ["metrics", "due", "--now", "2026-11-04T18:00:00Z"])
    assert r.exit_code == 0 and f"publication {t}" in r.output and "24h" in r.output
    r = runner.invoke(
        app,
        [
            "metrics",
            "add",
            str(t),
            "--age",
            "24h",
            "--views",
            "500",
            "--saves",
            "9",
            "--fyf",
            "yes",
            "--captured-at",
            "2026-11-04T18:00:00Z",
        ],
    )
    assert r.exit_code == 0 and "gespeichert" in r.output
    r = runner.invoke(app, ["metrics", "show", str(t)])
    assert r.exit_code == 0 and "views=500" in r.output and "fyf=yes" in r.output
    r = runner.invoke(app, ["metrics", "due", "--now", "2026-11-04T19:00:00Z"])
    assert "nichts fällig" in r.output
