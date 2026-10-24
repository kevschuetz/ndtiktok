"""Fixture-pinned TikTok/YouTube parsers and handle validation (plan 01-04, Task 1)."""

import json
from pathlib import Path

import pytest

from ndc.scan import handles, tiktok, youtube

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "scan"
NOW = 1792800000


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# --- TikTok listing / median rule -------------------------------------------------------------


def test_parse_listing_keeps_documented_fields():
    posts = tiktok.parse_listing(_load("tt_flat.json"))
    assert len(posts) == 23
    first = posts[0]
    for k in ("id", "timestamp", "view_count", "like_count", "comment_count", "repost_count",
              "save_count", "duration", "description", "pinned"):
        assert k in first
    assert first["pinned"] is True
    assert posts[1]["pinned"] is False


def test_newest_eligible_excludes_pinned_and_young_and_sorts():
    posts = tiktok.parse_listing(_load("tt_flat.json"))
    eligible = tiktok.eligible_posts(posts, NOW)
    assert len(eligible) == 15
    ts = [p["timestamp"] for p in eligible]
    assert ts == sorted(ts, reverse=True)
    assert all(NOW - t >= 72 * 3600 for t in ts)
    assert not any(p["pinned"] for p in eligible)
    assert "7000000000000000001" not in {p["id"] for p in eligible}


def test_median_last15():
    posts = tiktok.parse_listing(_load("tt_flat.json"))
    median, n = tiktok.median_last15(posts, NOW)
    # newest 15 eligible posts have views 1000..15000 -> median 8000
    assert (median, n) == (8000, 15)


def test_pinned_recent_post_is_still_excluded():
    posts = [
        {"id": str(i), "timestamp": NOW - (100 + i) * 3600, "view_count": 100 + i, "pinned": False}
        for i in range(10)
    ]
    posts[0]["pinned"] = True
    posts[0]["view_count"] = 10**7
    median, n = tiktok.median_last15(posts, NOW)
    assert n == 9
    assert median == 105


def test_median_none_below_eight_eligible():
    posts = [
        {"id": str(i), "timestamp": NOW - 100 * 3600 - i, "view_count": 10, "pinned": False}
        for i in range(7)
    ]
    median, n = tiktok.median_last15(posts, NOW)
    assert median is None and n == 7


def test_posts_without_timestamp_are_not_eligible():
    posts = [{"id": str(i), "timestamp": None, "view_count": 10, "pinned": False} for i in range(9)]
    assert tiktok.median_last15(posts, NOW) == (None, 0)


# --- TikTok profile page -----------------------------------------------------------------------


def test_parse_profile_html():
    html = (FIX / "tt_profile.html").read_text(encoding="utf-8")
    prof = tiktok.parse_profile_html(html)
    assert prof == {
        "followers": 5046,
        "video_count": 212,
        "bio": "ADHS im Alltag | Links unten",
        "bio_link": "linktr.ee/kirmesimkopf",
    }


def test_parse_profile_html_without_script_is_none():
    assert tiktok.parse_profile_html("<html><body>Please verify</body></html>") is None


def test_parse_profile_html_with_empty_user_detail_is_none():
    html = (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        '{"__DEFAULT_SCOPE__": {}}</script>'
    )
    assert tiktok.parse_profile_html(html) is None


# --- YouTube ------------------------------------------------------------------------------------


def test_parse_shorts_flat():
    out = youtube.parse_shorts_flat(_load("yt_shorts_flat.json"))
    assert out["subscribers"] == 1750000
    assert out["channel_id"] == "UCabcdefghijklmnopqrstuv"
    assert len(out["entries"]) == 18
    assert out["entries"][0] == {"id": "abcdefghi00", "view_count": 10000, "title": "Short 0"}


def test_parse_video():
    v = youtube.parse_video(_load("yt_video.json"))
    assert v["id"] == "abcdefghi00"
    assert v["timestamp"] == 1790841600
    assert v["upload_date"] == "20261001"
    assert v["view_count"] == 10123
    assert v["like_count"] == 812
    assert v["comment_count"] == 44
    assert v["pinned_comment"] == "Sources: Barkley 2015; NICE NG87"
    assert "Faraone" in v["description"]


def test_parse_video_timestamp_from_upload_date():
    data = _load("yt_video.json")
    del data["timestamp"]
    data["comments"] = None
    v = youtube.parse_video(data)
    assert v["timestamp"] == 1790812800  # 2026-10-01T00:00:00Z
    assert v["pinned_comment"] is None


# --- handle validation --------------------------------------------------------------------------


@pytest.mark.parametrize("h", ["kirmesimkopf", "hey_mamaleben", "a.b", "X9"])
def test_tiktok_handles_ok(h):
    assert handles.validate("tiktok", h) == h


@pytest.mark.parametrize("h", ["x; rm -rf", "a", "a" * 25, "bad/handle", "@lead", "", "h\nx"])
def test_tiktok_handles_rejected(h):
    with pytest.raises(handles.InvalidHandle):
        handles.validate("tiktok", h)


def test_tiktok_handle_leading_at_is_stripped():
    assert handles.normalize("tiktok", "@kirmesimkopf") == "kirmesimkopf"


@pytest.mark.parametrize("h", ["@HowtoADHD", "UCabcdefghijklmnopqrstuv", "@ADHD-Dude", "@a.b_c"])
def test_youtube_handles_ok(h):
    assert handles.validate("youtube", h) == h


@pytest.mark.parametrize("h", ["x; rm -rf", "@x y", "HowtoADHD", "@ab", "../etc", "@a?b=c"])
def test_youtube_handles_rejected(h):
    with pytest.raises(handles.InvalidHandle):
        handles.validate("youtube", h)


def test_unknown_platform_rejected():
    with pytest.raises(handles.InvalidHandle):
        handles.validate("insta" + "gram", "abc")


def test_url_builders_validate_first():
    assert tiktok.profile_url("kirmesimkopf") == "https://www.tiktok.com/@kirmesimkopf"
    assert youtube.shorts_url("@HowtoADHD") == "https://www.youtube.com/@HowtoADHD/shorts"
    assert (
        youtube.shorts_url("UCabcdefghijklmnopqrstuv")
        == "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv/shorts"
    )
    assert youtube.video_url("abcdefghi00") == "https://www.youtube.com/shorts/abcdefghi00"
    with pytest.raises(handles.InvalidHandle):
        tiktok.profile_url("x; rm -rf")
    with pytest.raises(handles.InvalidHandle):
        youtube.shorts_url("x; rm -rf")
    with pytest.raises(handles.InvalidHandle):
        youtube.video_url("not a video id")
