"""No-login media download for local analysis (D-17, D-16).

yt-dlp Python API, single progressive file ("b[height<=720]/b", no merge), size cap, into
media_dir/<account_id>/. `downloaded_media()` deletes that directory afterwards, also on error.
No cookies, no login, no impersonation: if a platform needs a login the result is `unavailable`
and the operator fills the field via `ndc scan verify`. Videos are never re-uploaded.
"""

import re
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ndc.scan import youtube
from ndc.scan.handles import validate

_TIKTOK_VIDEO_ID = re.compile(r"^\d{5,25}$")
FORMAT = "b[height<=720]/b"
# Fallback when no single progressive file exists (YouTube Shorts usually): audio and a small
# video-only stream as two separate files, so no ffmpeg merge is needed. Heights are portrait.
AUDIO_FORMAT = "ba[ext=m4a]/ba"
FRAMES_FORMAT = "bv*[height<=854][vcodec^=avc1]/bv*[height<=854]/bv*"


class DownloadUnavailable(Exception):
    pass


@dataclass
class MediaFiles:
    """audio: file to transcribe / pitch; frames: file to sample frames from (may be the same)."""

    audio: Path
    frames: Path | None

    def paths(self) -> list[Path]:
        return [p for p in {self.audio, self.frames} if p is not None]


@dataclass
class EligiblePost:
    post_id: str
    posted_at: int | None
    duration_s: float | None


def video_url(platform: str, handle: str, video_id: str) -> str:
    if platform == "tiktok":
        if not _TIKTOK_VIDEO_ID.fullmatch(video_id or ""):
            raise ValueError(f"invalid tiktok video id {video_id!r}")
        return f"https://www.tiktok.com/@{validate('tiktok', handle)}/video/{video_id}"
    if platform == "youtube":
        return youtube.video_url(video_id)
    raise ValueError(f"unknown platform {platform!r}")


def eligible_posts(
    conn, account_id: int, n: int, max_seconds: float, now_ts: float | None = None
) -> list[EligiblePost]:
    """Newest n non-pinned posts >= 72 h old (the reach-window rule) not longer than max_seconds."""
    now_ts = now_ts if now_ts is not None else time.time()
    rows = conn.execute(
        "SELECT post_id, posted_at, duration_s FROM competitor_post WHERE account_id = ?"
        " AND pinned = 0 AND posted_at IS NOT NULL AND posted_at <= ?"
        " AND (duration_s IS NULL OR duration_s <= ?) ORDER BY posted_at DESC LIMIT ?",
        (account_id, int(now_ts - 72 * 3600), max_seconds, n),
    ).fetchall()
    return [EligiblePost(r["post_id"], r["posted_at"], r["duration_s"]) for r in rows]


def _ydl_opts(out_dir: Path, max_filesize_mb: float, fmt: str = FORMAT, tag: str = "") -> dict:
    # Deliberately no cookie, login or browser-mimicking options (D-16).
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "format": fmt,
        "max_filesize": int(max_filesize_mb * 1024 * 1024),
        "outtmpl": str(out_dir / f"%(id)s{tag}.%(ext)s"),
        "retries": 1,
        "socket_timeout": 30,
    }


def _download_one(url: str, out_dir: Path, max_filesize_mb: float, fmt: str, tag: str) -> Path:
    from yt_dlp import YoutubeDL  # scan extra; imported lazily
    from yt_dlp.utils import DownloadError

    out_dir.mkdir(parents=True, exist_ok=True)
    before = set(out_dir.iterdir())
    try:
        with YoutubeDL(_ydl_opts(out_dir, max_filesize_mb, fmt, tag)) as ydl:
            ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise DownloadUnavailable(str(exc).splitlines()[0][:300]) from exc
    new = [p for p in out_dir.iterdir() if p not in before and not p.name.endswith(".part")]
    if not new:
        raise DownloadUnavailable("no file written (size cap or format unavailable)")
    return max(new, key=lambda p: p.stat().st_size)


def download_video(url: str, out_dir: Path, max_filesize_mb: float = 60) -> MediaFiles:
    """One progressive file if offered, else separate audio + small video-only files.
    Raises DownloadUnavailable on any extractor/HTTP failure (never retried with a login)."""
    try:
        path = _download_one(url, out_dir, max_filesize_mb, FORMAT, "")
        return MediaFiles(path, path)
    except DownloadUnavailable as exc:
        if "format is not available" not in str(exc):
            raise
    audio = _download_one(url, out_dir, max_filesize_mb, AUDIO_FORMAT, ".audio")
    try:
        frames = _download_one(url, out_dir, max_filesize_mb, FRAMES_FORMAT, ".frames")
    except DownloadUnavailable:
        frames = None  # transcript + pitch still work; the contact sheet misses this video
    return MediaFiles(audio, frames)


@contextmanager
def downloaded_media(media_dir: str | Path, account_id: int | str) -> Iterator[Path]:
    """Per-account download directory that is always deleted afterwards."""
    path = Path(media_dir) / str(account_id)
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def probe_download(
    platform: str, handle: str, video_id: str, media_dir: str | Path, max_filesize_mb: float = 60
) -> tuple[str, str]:
    """Verify-first helper (D-17): one no-login download, deleted; returns (verdict, detail)."""
    url = video_url(platform, handle, video_id)
    with downloaded_media(media_dir, f"probe-{platform}") as tmp:
        try:
            files = download_video(url, tmp, max_filesize_mb)
        except DownloadUnavailable as exc:
            return "unavailable", str(exc)
        parts = ", ".join(f"{p.name} {p.stat().st_size // 1024} KiB" for p in files.paths())
        return "ok", f"{parts} from {url}"
