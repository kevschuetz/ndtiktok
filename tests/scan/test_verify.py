"""Operator spot-check CLI (plan 01-06 Task 2, D-01, D-17)."""

from scan_seed import add_obs, seed_account, sheet_row

from ndc.cli import app
from ndc.scan import queue


def _queued(db, handle="kirmes", lang="de", platform="tiktok"):
    aid = seed_account(db, handle, platform=platform, lang=lang)
    add_obs(db, aid, "source_text_level", "2", "llm_session", "low")
    add_obs(db, aid, "face", "face", "llm_session", "low")
    add_obs(db, aid, "voice_gender", "female", "auto", "low", "pitch_estimate")
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO competitor_post_citing (account_id, post_id, source, level, evidence,"
            " guard_result, created_at) VALUES (?, 'p1', 'caption', 2, 'laut Leitlinie',"
            " 'kept', 'x')",
            (aid,),
        )
    finally:
        conn.close()
    queue.recompute(db, aid)
    return aid


def test_queue_listing_dach_first(db, runner):
    _queued(db, "english_one", lang="en")
    _queued(db, "deutsch_one", lang="de")
    res = runner.invoke(app, ["scan", "verify", "--queue"])
    assert res.exit_code == 0, res.output
    out = res.output
    assert out.index("deutsch_one") < out.index("english_one")
    assert "llm_session" in out and "low" in out and "laut Leitlinie" in out


def test_verify_sets_operator_values_and_clears_queue(db, runner):
    aid = _queued(db)
    assert sheet_row(db, aid)["needs_operator_check"] == "true"
    res = runner.invoke(
        app,
        [
            "scan",
            "verify",
            "kirmes",
            "--platform",
            "tiktok",
            "--set",
            "face=faceless",
            "--set",
            "voice_gender=male",
            "--set",
            "source_citing_score=2",
            "--note",
            "watched 2 videos",
        ],
    )
    assert res.exit_code == 0, res.output
    row = sheet_row(db, aid)
    assert row["face"] == "faceless" and row["face_provenance"] == "operator_verified"
    assert row["voice_gender"] == "male"
    assert row["source_citing_score"] == 2
    assert row["source_citing_provenance"] == "operator_verified"
    assert row["needs_operator_check"] == "false"


def test_verify_invalid_value_fails(db, runner):
    _queued(db)
    res = runner.invoke(
        app, ["scan", "verify", "kirmes", "--platform", "tiktok", "--set", "face=maybe"]
    )
    assert res.exit_code != 0
    res = runner.invoke(
        app, ["scan", "verify", "kirmes", "--platform", "tiktok", "--set", "source_citing_score=7"]
    )
    assert res.exit_code != 0


def test_verify_unknown_account_fails(db, runner):
    res = runner.invoke(
        app, ["scan", "verify", "nobody", "--platform", "tiktok", "--set", "face=faceless"]
    )
    assert res.exit_code != 0


def test_reimport_after_verify_requeues_only_if_new_judgment(db, runner):
    aid = _queued(db)
    runner.invoke(
        app, ["scan", "verify", "kirmes", "--platform", "tiktok", "--set", "face=faceless"]
    )
    assert sheet_row(db, aid)["needs_operator_check"] == "false"
    add_obs(db, aid, "format", "skit", "llm_session", "low")  # a newer machine judgment
    flag, _ = queue.recompute(db, aid)
    assert flag is True
