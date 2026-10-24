"""TikTok public metadata: flat listing via the yt-dlp Python API, profile via one plain GET.

Network calls (fetch_*) are separate from pure parsers (parse_*, eligible_posts, median_last15) so
the parsers are pinned by synthetic fixtures. No cookies, no login, no impersonation library (D-16).
"""

import json
import re
import statistics

import httpx

from ndc.scan.handles import validate

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 20

_HYDRATION = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', re.S
)
_KEEP = (
    "id",
    "timestamp",
    "view_count",
    "like_count",
    "comment_count",
    "repost_count",
    "save_count",
    "duration",
    "description",
)


def profile_url(handle: str) -> str:
    return f"https://www.tiktok.com/@{validate('tiktok', handle)}"


# --- pure parsers ---------------------------------------------------------------------------------


def parse_listing(info: dict) -> list[dict]:
    out = []
    for e in (info or {}).get("entries") or []:
        if not isinstance(e, dict):
            continue
        row = {k: e.get(k) for k in _KEEP}
        row["id"] = str(row["id"]) if row["id"] is not None else None
        row["pinned"] = bool(e.get("is_pinned") or e.get("pinned"))
        out.append(row)
    return out


def eligible_posts(
    posts: list[dict], now_ts: float, n: int = 15, min_age_hours: float = 72
) -> list[dict]:
    """Newest n posts that are >= min_age_hours old, sorted by timestamp desc; pinned excluded."""
    ok = [
        p
        for p in posts
        if p.get("timestamp")
        and not p.get("pinned")
        and now_ts - p["timestamp"] >= min_age_hours * 3600
    ]
    return sorted(ok, key=lambda p: p["timestamp"], reverse=True)[:n]


def median_last15(
    posts: list[dict], now_ts: float, n: int = 15, min_age_hours: float = 72, min_posts: int = 8
) -> tuple[float | None, int]:
    views = [
        p["view_count"]
        for p in eligible_posts(posts, now_ts, n, min_age_hours)
        if p.get("view_count") is not None
    ]
    if len(views) < min_posts:
        return None, len(views)
    return statistics.median(views), len(views)


def parse_profile_html(html: str) -> dict | None:
    m = _HYDRATION.search(html or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return None
    ui = (data.get("__DEFAULT_SCOPE__") or {}).get("webapp.user-detail", {}).get("userInfo") or {}
    stats, user = ui.get("stats") or {}, ui.get("user") or {}
    if stats.get("followerCount") is None:
        return None
    return {
        "followers": stats.get("followerCount"),
        "video_count": stats.get("videoCount"),
        "bio": user.get("signature"),
        "bio_link": (user.get("bioLink") or {}).get("link"),
    }


# --- network ------------------------------------------------------------------------------------


def fetch_listing_info(handle: str, playlistend: int = 30) -> dict:
    from yt_dlp import YoutubeDL  # scan extra; imported lazily

    url = profile_url(handle)
    opts = {
        "extract_flat": True,
        "playlistend": int(playlistend),
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False) or {}


def fetch_profile_html(handle: str) -> str:
    url = profile_url(handle)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S) as client:
        with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            buf = bytearray()
            for chunk in resp.iter_bytes():
                buf.extend(chunk)
                if len(buf) > MAX_BYTES:
                    break
            return bytes(buf[:MAX_BYTES]).decode(resp.encoding or "utf-8", errors="replace")


def fetch_profile(handle: str) -> dict | None:
    return parse_profile_html(fetch_profile_html(handle))


def fetch_posts(handle: str, playlistend: int = 30) -> list[dict]:
    return parse_listing(fetch_listing_info(handle, playlistend))
