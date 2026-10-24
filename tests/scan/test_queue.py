"""needs_operator_check rules (plan 01-06 Task 2, D-17)."""

import pytest
from scan_seed import add_obs, obs_rows, seed_account, sheet_row

from ndc.scan import queue


def _base(db, lang="de", text="0", video="0", face="face", voice="female", conf="high"):
    aid = seed_account(db, f"acc_{lang}_{text}{video}{face}{voice}{conf}", lang=lang)
    add_obs(db, aid, "source_text_level", text, "llm_session", conf)
    add_obs(db, aid, "source_video_level", video, "llm_session", "high")
    add_obs(db, aid, "face", face, "llm_session", "high")
    add_obs(db, aid, "voice_gender", voice, "auto", "high", "pitch_estimate")
    return aid


def test_clean_account_not_queued(db):
    aid = _base(db)
    flag, reasons = queue.recompute(db, aid)
    assert flag is False and reasons == []
    assert sheet_row(db, aid)["needs_operator_check"] == "false"
    nc = obs_rows(db, aid, "needs_operator_check")[-1]
    assert nc["provenance"] == "auto"


def test_low_confidence_queued(db):
    aid = _base(db, conf="low")
    flag, reasons = queue.recompute(db, aid)
    assert flag and any("low confidence" in r for r in reasons)


def test_pitch_vs_visual_conflict(db):
    aid = _base(db, voice="female")
    add_obs(db, aid, "visible_speaker_gender", "male", "llm_session", "high")
    flag, reasons = queue.recompute(db, aid)
    assert flag and any("pitch" in r for r in reasons)


def test_all_downloads_unavailable(db):
    aid = seed_account(
        db, "nodl", videos=[("v1", None, "unavailable"), ("v2", None, "unavailable")]
    )
    flag, reasons = queue.recompute(db, aid)
    assert flag and any("download" in r for r in reasons)


def test_some_download_ok_not_queued_for_download(db):
    aid = seed_account(db, "somedl", videos=[("v1", "x", "ok"), ("v2", None, "unavailable")])
    _, reasons = queue.recompute(db, aid)
    assert not any("download" in r for r in reasons)


def test_de_video_lifts_score(db):
    aid = _base(db, lang="de", text="1", video="2")
    flag, reasons = queue.recompute(db, aid)
    assert flag and any("video" in r for r in reasons)


def test_de_onscreen_lifts_score(db):
    aid = _base(db, lang="de", text="0", video="1")
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO competitor_post_citing (account_id, video_id, source, level,"
            " guard_result, created_at) VALUES (?, 'v1', 'onscreen', 2, 'kept', 'x')",
            (aid,),
        )
    finally:
        conn.close()
    flag, reasons = queue.recompute(db, aid)
    assert flag and any("on-screen" in r for r in reasons)


def test_en_video_lift_not_queued(db):
    aid = _base(db, lang="en", text="1", video="2")
    flag, _ = queue.recompute(db, aid)
    assert flag is False


@pytest.mark.parametrize("lang", ["de", "en"])
def test_would_count_in_s(db, lang):
    aid = _base(db, lang=lang, text="2", video="0", face="faceless", voice="male")
    flag, reasons = queue.recompute(db, aid)
    assert flag and any("S_" in r for r in reasons)


def test_recompute_all_counts(db):
    _base(db)
    _base(db, conf="low")
    counts = queue.recompute_all(db)
    assert counts == {"queued": 1, "clear": 1}
