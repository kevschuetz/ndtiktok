"""YouTube Shorts public metadata via the yt-dlp Python API (in-process only, no cookies).

The flat /shorts listing gives subscribers and per-entry views (no dates); one per-video call
(skip_download) gives upload date, likes, comments, description and the uploader's pinned comment.
"""

from datetime import UTC, datetime

from ndc.scan.handles import is_youtube_channel_id, validate, validate_video_id

MAX_COMMENTS = 10


def shorts_url(handle: str) -> str:
    h = validate("youtube", handle)
    if is_youtube_channel_id(h):
        return f"https://www.youtube.com/channel/{h}/shorts"
    return f"https://www.youtube.com/{h}/shorts"


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{validate_video_id(video_id)}"


# --- pure parsers ---------------------------------------------------------------------------------


def parse_shorts_flat(info: dict) -> dict:
    info = info or {}
    entries = []
    for e in info.get("entries") or []:
        if isinstance(e, dict) and e.get("id"):
            entries.append(
                {"id": e["id"], "view_count": e.get("view_count"), "title": e.get("title")}
            )
    return {
        "subscribers": info.get("channel_follower_count"),
        "channel_id": info.get("channel_id"),
        "channel": info.get("channel") or info.get("uploader"),
        "description": info.get("description"),
        "entries": entries,
    }


def _upload_ts(upload_date: str | None) -> int | None:
    if not upload_date:
        return None
    try:
        return int(datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=UTC).timestamp())
    except ValueError:
        return None


def parse_video(info: dict) -> dict:
    info = info or {}
    pinned = None
    for c in info.get("comments") or []:
        if isinstance(c, dict) and c.get("is_pinned") and c.get("author_is_uploader"):
            pinned = c.get("text")
            break
    ts = info.get("timestamp") or _upload_ts(info.get("upload_date"))
    return {
        "id": info.get("id"),
        "timestamp": ts,
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "duration": info.get("duration"),
        "description": info.get("description"),
        "pinned_comment": pinned,
    }


# --- network ------------------------------------------------------------------------------------


def _ydl(extra: dict | None = None):
    from yt_dlp import YoutubeDL  # scan extra; imported lazily

    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    opts.update(extra or {})
    return YoutubeDL(opts)


def fetch_shorts(handle: str, playlistend: int = 30) -> dict:
    url = shorts_url(handle)
    with _ydl({"extract_flat": True, "playlistend": int(playlistend)}) as ydl:
        return parse_shorts_flat(ydl.extract_info(url, download=False) or {})


def fetch_video(video_id: str) -> dict:
    url = video_url(video_id)
    extra = {
        "getcomments": True,
        "extractor_args": {
            "youtube": {"max_comments": [str(MAX_COMMENTS), str(MAX_COMMENTS), "0", "0"]}
        },
    }
    with _ydl(extra) as ydl:
        return parse_video(ydl.extract_info(url, download=False) or {})
