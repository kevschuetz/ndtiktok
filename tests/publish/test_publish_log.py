import pytest

from ndc.publish import store as ps

TT = "https://www.tiktok.com/@quellenkopf/video/7301234567890123456"
YT = "https://youtube.com/shorts/AbCdEfGhIjk"
IG = "https://www.instagram.com/reel/C9abcDEFghi/"


def test_parse_post_url_hosts_and_ids():
    assert ps.parse_post_url("tiktok", TT) == "7301234567890123456"
    assert ps.parse_post_url("youtube", YT) == "AbCdEfGhIjk"
    assert (
        ps.parse_post_url("youtube", "https://www.youtube.com/watch?v=AbCdEfGhIjk") == "AbCdEfGhIjk"
    )
    assert ps.parse_post_url("instagram", IG) == "C9abcDEFghi"
    with pytest.raises(ps.PublishRefused, match="nicht erlaubt"):
        ps.parse_post_url("tiktok", "https://evil.example/video/1")
    with pytest.raises(ps.PublishRefused, match="nicht erlaubt"):
        ps.parse_post_url("tiktok", YT)


def test_refused_without_approval(db, version, locked):
    from review_helpers import sha_of

    with pytest.raises(ps.PublishRefused, match="nicht freigegeben"):
        ps.log_publication(db, platform="tiktok", script_sha=sha_of(db, version), post_url=TT)


def test_refused_without_readout_lock(db, approved_sha):
    with pytest.raises(ps.PublishRefused, match="nicht gesperrt"):
        ps.log_publication(db, platform="tiktok", script_sha=approved_sha, post_url=TT)


def test_gate_hook_blocks(db, approved_sha, locked, monkeypatch):
    from ndc.review.gate import Issue

    monkeypatch.setattr(
        ps,
        "PUBLISH_GATES",
        [lambda conn, s, r: [Issue("block_recording", None, "Aufnahme nicht freigegeben")]],
    )
    with pytest.raises(ps.PublishRefused, match="Aufnahme nicht freigegeben"):
        ps.log_publication(db, platform="tiktok", script_sha=approved_sha, post_url=TT)


def test_cross_post_requires_tiktok_first_and_rows_are_append_only(db, approved_sha, locked):
    with pytest.raises(ps.PublishRefused, match="zuerst die TikTok"):
        ps.log_publication(db, platform="youtube", script_sha=approved_sha, post_url=YT)
    pid = ps.log_publication(
        db,
        platform="tiktok",
        script_sha=approved_sha[:12],
        post_url=TT,
        posted_at="2026-11-03T17:00:00Z",
        hook_tactic="du_scene",
        caption_text="c",
        pinned_text="p",
    )
    ps.log_publication(db, platform="youtube", script_sha=approved_sha, post_url=YT)
    ps.log_publication(db, platform="instagram", script_sha=approved_sha, post_url=IG)
    conn = db.connect()
    rows = ps.list_publications(conn)
    assert [r["platform"] for r in rows] == ["instagram", "youtube", "tiktok"]
    tt = [r for r in rows if r["id"] == pid][0]
    assert tt["post_id"] == "7301234567890123456" and tt["pillar"] == "challenge_science_help"
    assert tt["caption_sha256"] and tt["posted_at"] == "2026-11-03T17:00:00Z"
    with pytest.raises(Exception, match="append-only"):
        conn.execute("UPDATE publication SET post_url='x'")
    with pytest.raises(Exception, match="UNIQUE"):
        ps.log_publication(db, platform="tiktok", script_sha=approved_sha, post_url=TT)
    conn.close()


def test_caption_and_pinned_from_db_and_config(db, approved_sha):
    cap = ps.render_caption(db, approved_sha)
    assert cap.startswith("Quellen:") and "doi:10.1371/journal.pone.0280131" in cap
    tags = [t for t in cap.split("\n")[-1].split() if t.startswith("#")]
    assert (
        3 <= len(tags) <= 5
        and tags[0] == "#ADHS"
        and any(t.startswith("#Wissenschaft") for t in tags)
    )
    pinned = ps.render_pinned(db, approved_sha)
    assert pinned[0].startswith("Quellen") and "PMID 36608036" in pinned[0]
    assert "142" in pinned[-1]  # crisis short form for emotion_regulation


def test_caption_refused_when_not_approved(db, version):
    from review_helpers import sha_of

    with pytest.raises(Exception, match="nicht freigegeben"):
        ps.render_caption(db, sha_of(db, version))


def test_cli_log_and_caption(runner, db, approved_sha, locked):
    from ndc.cli import app

    r = runner.invoke(app, ["publish", "caption", approved_sha[:12]])
    assert r.exit_code == 0 and "---" in r.output and "#ADHS" in r.output
    r = runner.invoke(
        app,
        ["publish", "log", "--platform", "tiktok", "--script", approved_sha[:12], "--post-url", TT],
    )
    assert r.exit_code == 0 and "geloggt" in r.output
    r = runner.invoke(app, ["publish", "list"])
    assert r.exit_code == 0 and "tiktok" in r.output
