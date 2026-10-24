"""Handle validation (T-04-01). Every URL builder calls validate() before building a URL.

TikTok: ^[A-Za-z0-9._]{2,24}$ (a leading @ is stripped by normalize()).
YouTube: a channel id (UC + 22 chars) or an @handle of 3-30 chars [A-Za-z0-9._-].
"""

import re

PLATFORMS = ("tiktok", "youtube")

_TIKTOK = re.compile(r"[A-Za-z0-9._]{2,24}")
_YT_CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")
_YT_HANDLE = re.compile(r"@[A-Za-z0-9._-]{3,30}")
_YT_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


class InvalidHandle(ValueError):
    pass


def normalize(platform: str, handle: str) -> str:
    """Trim whitespace; strip a leading @ for TikTok. Does not validate."""
    h = (handle or "").strip()
    if platform == "tiktok" and h.startswith("@"):
        h = h[1:]
    return h


def is_youtube_channel_id(handle: str) -> bool:
    return bool(_YT_CHANNEL_ID.fullmatch(handle))


def validate(platform: str, handle: str) -> str:
    if platform == "tiktok":
        ok = bool(_TIKTOK.fullmatch(handle or ""))
    elif platform == "youtube":
        ok = bool(_YT_CHANNEL_ID.fullmatch(handle or "") or _YT_HANDLE.fullmatch(handle or ""))
    else:
        raise InvalidHandle(f"unsupported platform {platform!r} (tiktok|youtube only)")
    if not ok:
        raise InvalidHandle(f"invalid {platform} handle {handle!r}")
    return handle


def validate_video_id(video_id: str) -> str:
    if not _YT_VIDEO_ID.fullmatch(video_id or ""):
        raise InvalidHandle(f"invalid youtube video id {video_id!r}")
    return video_id
