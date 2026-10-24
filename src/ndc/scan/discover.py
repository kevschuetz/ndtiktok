"""Automated candidate discovery (D-04, D-16).

- YouTube: ytsearchN:"<query> #shorts" per config query via the yt-dlp Python API (flat); channels
  with >= min_niche_shorts results across the language's queries become candidates.
- Modash public find-influencers pages (plain HTML, no login, verified 2026-10-24): TikTok handles
  linked as tiktok.com/@handle. Optional; the operator names the page path.
Sources that need JS, an account or a bot check are operator-browser only (see
docs/scan-discovery-sources.md); nothing here works around a login wall or a bot check.
"""

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from ndc.db import Database
from ndc.scan import fetch, handles
from ndc.scan.tiktok import MAX_BYTES, TIMEOUT_S, USER_AGENT

MAX_SHORT_SECONDS = 180
_MODASH_PATH = re.compile(r"tiktok(?:/[a-z0-9-]{2,40}){0,2}")
_TT_LINK = re.compile(r"tiktok\.com/@([A-Za-z0-9._]{2,24})(?=[\"'/?\s<])")


@dataclass
class DiscoverReport:
    run_id: int
    source: str
    language: str
    requests: int = 0
    seen: int = 0
    inserted: list = field(default_factory=list)
    existing: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    errors: list = field(default_factory=list)


# --- YouTube ytsearch ------------------------------------------------------------


def parse_search(info: dict) -> list[dict]:
    out = []
    for e in (info or {}).get("entries") or []:
        if not isinstance(e, dict) or not e.get("channel_id"):
            continue
        if e.get("duration") and e["duration"] > MAX_SHORT_SECONDS:
            continue  # not a Short
        out.append(
            {
                "video_id": e.get("id"),
                "channel_id": e["channel_id"],
                "uploader_id": e.get("uploader_id"),
                "channel": e.get("channel") or e.get("uploader"),
            }
        )
    return out


def youtube_handle(hit: dict) -> str | None:
    for cand in (hit.get("uploader_id"), hit.get("channel_id")):
        if cand:
            try:
                return handles.validate("youtube", cand)
            except handles.InvalidHandle:
                continue
    return None


def aggregate_channels(results: dict[str, list[dict]], min_hits: int) -> list[dict]:
    """results: query -> parsed hits. Returns channels with >= min_hits distinct Shorts."""
    chans: dict[str, dict] = {}
    for query, hits in results.items():
        for h in hits:
            c = chans.setdefault(
                h["channel_id"],
                {
                    "channel_id": h["channel_id"],
                    "handle": youtube_handle(h),
                    "name": h["channel"],
                    "videos": set(),
                    "queries": [],
                },
            )
            c["videos"].add(h["video_id"])
            if query not in c["queries"]:
                c["queries"].append(query)
    keep = [c for c in chans.values() if len(c["videos"]) >= min_hits and c["handle"]]
    return sorted(keep, key=lambda c: (-len(c["videos"]), c["channel_id"]))


def search_youtube(query: str, n: int = 30) -> dict:
    from yt_dlp import YoutubeDL  # scan extra; imported lazily

    term = f"ytsearch{int(n)}:{query} #shorts"
    with YoutubeDL(
        {"extract_flat": True, "quiet": True, "no_warnings": True, "skip_download": True}
    ) as ydl:
        return ydl.extract_info(term, download=False) or {}


def discover_youtube(
    db: Database,
    language: str,
    *,
    force: bool = False,
    cfg=None,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    search: Callable[[str, int], dict] | None = None,
) -> DiscoverReport:
    run_id = fetch.gate(db, "discover", force, cfg)
    scfg = fetch.load_scan_config(cfg)
    disc = scfg.get("discovery") or {}
    n = int(disc.get("ytsearch_results", 30))
    min_hits = int(disc.get("min_niche_shorts", 3))
    polite = fetch.polite_from_config(scfg, sleep=sleep, rng=rng or random.Random())
    search = search or search_youtube
    rep = DiscoverReport(run_id=run_id, source="ytsearch", language=language)
    results: dict[str, list[dict]] = {}
    for query in (scfg.get("queries") or {}).get(language) or []:
        if polite.stopped("youtube"):
            rep.errors.append(f"{query}: skipped (3 consecutive failures)")
            continue
        try:
            info = polite.call("youtube", search, query, n)
            polite.record("youtube", True)
        except fetch.PlatformStopped:
            continue
        except Exception as exc:
            polite.record("youtube", False)
            rep.errors.append(f"{query}: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        rep.requests += 1
        results[query] = parse_search(info)
    channels = aggregate_channels(results, min_hits)
    rep.seen = len({h["channel_id"] for hits in results.values() for h in hits})
    for c in channels:
        note = f"{c['name']}; {len(c['videos'])} Shorts in search; channel_id {c['channel_id']}"
        if fetch.upsert_candidate(
            db, c["handle"], "youtube", language, "ytsearch", "; ".join(c["queries"]), note
        ):
            rep.inserted.append(c["handle"])
        else:
            rep.existing.append(c["handle"])
            if fetch.note_language_conflict(db, c["handle"], "youtube", language, "ytsearch"):
                rep.conflicts.append(c["handle"])
    fetch.add_run_note(
        db,
        run_id,
        f"discover ytsearch {language}: {rep.requests} queries, {rep.seen} channels seen, "
        f"{len(rep.inserted)} new candidates",
    )
    fetch.finish_run(db, run_id)
    return rep


# --- Modash public pages ------------------------------------------------------------


def modash_url(path: str) -> str:
    path = path.strip().strip("/")
    if not _MODASH_PATH.fullmatch(path):
        raise ValueError(f"invalid Modash page path {path!r} (e.g. tiktok/germany)")
    return f"https://www.modash.io/find-influencers/{path}"


def parse_modash(html: str) -> list[str]:
    seen, out = set(), []
    for h in _TT_LINK.findall(html or ""):
        if h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out


def fetch_modash(path: str) -> str:
    url = modash_url(path)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S) as client:
        with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            buf = bytearray()
            for chunk in resp.iter_bytes():
                buf.extend(chunk)
                if len(buf) > MAX_BYTES * 2:  # these pages are ~1.5 MB of inline assets
                    break
            return bytes(buf).decode(resp.encoding or "utf-8", errors="replace")


def discover_modash(
    db: Database,
    language: str,
    paths: list[str],
    *,
    force: bool = False,
    cfg=None,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    get: Callable[[str], str] | None = None,
) -> DiscoverReport:
    for p in paths:
        modash_url(p)  # validate all paths before the gate / any request
    run_id = fetch.gate(db, "discover", force, cfg)
    scfg = fetch.load_scan_config(cfg)
    polite = fetch.polite_from_config(scfg, sleep=sleep, rng=rng or random.Random())
    get = get or fetch_modash
    rep = DiscoverReport(run_id=run_id, source="modash", language=language)
    for p in paths:
        try:
            html = polite.call("modash", get, p)
            polite.record("modash", True)
        except fetch.PlatformStopped:
            break
        except Exception as exc:
            polite.record("modash", False)
            rep.errors.append(f"{p}: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        rep.requests += 1
        found = parse_modash(html)
        rep.seen += len(found)
        for h in found:
            if fetch.upsert_candidate(db, h, "tiktok", language, "modash", p, "Modash public page"):
                rep.inserted.append(h)
            else:
                rep.existing.append(h)
    fetch.add_run_note(
        db,
        run_id,
        f"discover modash {language}: {rep.requests} pages, {rep.seen} handles, "
        f"{len(rep.inserted)} new candidates",
    )
    fetch.finish_run(db, run_id)
    return rep
