"""Competitor scan collection: candidate import, polite gated resumable fetch, manual entry.

Gate (D-20): assert_rule_approved() + quiet-hours check before the first request, then one
scan_run row under the rule sha256. Politeness (D-16): single-threaded, uniform(3, 6) s between
every request, tenacity backoff on 429/403/5xx, stop a platform after 3 consecutive failures.
DB writes happen only after each network call has returned (no transaction is held across one).
"""

import csv
import random
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from ndc.config import config_dir as _config_dir
from ndc.db import Database
from ndc.scan import handles, prereg, quiet_hours, tiktok, youtube
from ndc.scan.decide import load_rule

SCAN_CONFIG = "scan.yaml"
CANDIDATE_COLUMNS = (
    "handle",
    "platform",
    "language",
    "discovery_source",
    "query",
    "seed_named",
    "operator_decision",
    "notes",
)


class PlatformStopped(Exception):
    pass


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_scan_config(cfg: str | Path | None = None) -> dict:
    path = Path(cfg or _config_dir()) / SCAN_CONFIG
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def tier_for(followers: int | None, cfg: str | Path | None = None) -> str | None:
    if followers is None:
        return None
    rule = load_rule(prereg.rule_path(cfg))
    if followers < rule.sample_min_followers:
        return "below_min"
    for name, t in rule.tiers.items():
        if followers >= t.min and (t.max is None or followers <= t.max):
            return name
    return None


# --- gate -----------------------------------------------------------------------------------------


def gate(db: Database, stage: str, force: bool, cfg: str | Path | None = None) -> int:
    """Rule lock (RuleNotApproved) -> quiet hours (QuietHours) -> scan_run row. Returns its id."""
    prereg.assert_rule_approved(cfg)
    note = quiet_hours.check(load_scan_config(cfg), force)
    run_id = prereg.record_scan_run(db, stage, cfg)
    if note:
        add_run_note(db, run_id, note)
    return run_id


def add_run_note(db: Database, run_id: int, note: str) -> None:
    conn = db.connect()
    try:
        row = conn.execute("SELECT notes FROM scan_run WHERE id = ?", (run_id,)).fetchone()
        notes = "; ".join(x for x in ((row["notes"] if row else None), note) if x)
        conn.execute("UPDATE scan_run SET notes = ? WHERE id = ?", (notes, run_id))
    finally:
        conn.close()


def finish_run(db: Database, run_id: int) -> None:
    conn = db.connect()
    try:
        conn.execute("UPDATE scan_run SET finished_at = ? WHERE id = ?", (now_iso(), run_id))
    finally:
        conn.close()


# --- politeness -----------------------------------------------------------------------------------


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (403, 429) or code >= 500
    msg = str(exc)
    return any(f"HTTP Error {c}" in msg for c in ("403", "429", "500", "502", "503", "504"))


@dataclass
class Polite:
    sleep: Callable[[float], None] = time.sleep
    rng: random.Random = field(default_factory=random.Random)
    sleep_min: float = 3.0
    sleep_max: float = 6.0
    max_failures: int = 3
    backoff_attempts: int = 3
    backoff_sleep: Callable[[float], None] = time.sleep
    requests: int = 0
    failures: dict = field(default_factory=dict)

    def stopped(self, platform: str) -> bool:
        return self.failures.get(platform, 0) >= self.max_failures

    def call(self, platform: str, fn: Callable, *args):
        if self.stopped(platform):
            raise PlatformStopped(platform)
        if self.requests:
            self.sleep(self.rng.uniform(self.sleep_min, self.sleep_max))
        self.requests += 1
        retrying = Retrying(
            retry=retry_if_exception(_retryable),
            stop=stop_after_attempt(self.backoff_attempts),
            wait=wait_exponential(multiplier=15, min=15, max=120),
            sleep=self.backoff_sleep,
            reraise=True,
        )
        return retrying(fn, *args)

    def record(self, platform: str, ok: bool) -> None:
        self.failures[platform] = 0 if ok else self.failures.get(platform, 0) + 1


def polite_from_config(scfg: dict, **kw) -> Polite:
    p = scfg.get("politeness") or {}
    return Polite(
        sleep_min=float(p.get("sleep_min", 3)),
        sleep_max=float(p.get("sleep_max", 6)),
        max_failures=int(p.get("max_consecutive_failures", 3)),
        backoff_attempts=int(p.get("backoff_attempts", 3)),
        **kw,
    )


# --- candidates -----------------------------------------------------------------------------------


@dataclass
class ImportReport:
    inserted: int = 0
    updated: int = 0
    rejected: list = field(default_factory=list)


def _blank(v):
    v = (v or "").strip()
    return v or None


def import_candidates(db: Database, path: Path) -> ImportReport:
    rep = ImportReport()
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for lineno, raw in enumerate(csv.DictReader(fh), start=2):
            platform = (raw.get("platform") or "").strip().lower()
            language = (raw.get("language") or "").strip().lower()
            handle = handles.normalize(platform, raw.get("handle") or "")
            decision = (_blank(raw.get("operator_decision")) or "").lower() or None
            try:
                handles.validate(platform, handle)
                if language not in ("de", "en"):
                    raise ValueError(f"invalid language {language!r}")
                if decision not in (None, "include", "exclude"):
                    raise ValueError(f"invalid operator_decision {decision!r}")
            except ValueError as exc:
                rep.rejected.append(f"row {lineno}: {exc}")
                continue
            seed = (raw.get("seed_named") or "").strip().lower() in ("1", "true", "yes")
            rows.append((handle, platform, language, raw, decision, seed))
    conn = db.connect()
    try:
        conn.execute("BEGIN")
        for handle, platform, language, raw, decision, seed in rows:
            status = "excluded" if decision == "exclude" else None
            existing = conn.execute(
                "SELECT id, status FROM competitor_candidate WHERE handle = ? AND platform = ?",
                (handle, platform),
            ).fetchone()
            if existing:
                if status is None and existing["status"] == "excluded":
                    status = "candidate"  # exclude lifted by the operator
                conn.execute(
                    "UPDATE competitor_candidate SET language = ?,"
                    " discovery_source = COALESCE(?, discovery_source),"
                    " query = COALESCE(?, query), seed_named = MAX(seed_named, ?),"
                    " operator_decision = ?, notes = COALESCE(?, notes),"
                    " status = COALESCE(?, status) WHERE id = ?",
                    (
                        language,
                        _blank(raw.get("discovery_source")),
                        _blank(raw.get("query")),
                        int(seed),
                        decision,
                        _blank(raw.get("notes")),
                        status,
                        existing["id"],
                    ),
                )
                rep.updated += 1
            else:
                conn.execute(
                    "INSERT INTO competitor_candidate (handle, platform, language,"
                    " discovery_source, query, seed_named, operator_decision, notes, status,"
                    " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        handle,
                        platform,
                        language,
                        _blank(raw.get("discovery_source")) or "operator",
                        _blank(raw.get("query")),
                        int(seed),
                        decision,
                        _blank(raw.get("notes")),
                        status or "candidate",
                        now_iso(),
                    ),
                )
                rep.inserted += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return rep


def upsert_candidate(
    db: Database,
    handle: str,
    platform: str,
    language: str,
    discovery_source: str,
    query: str | None = None,
    notes: str | None = None,
) -> bool:
    """Insert a discovered candidate if new. Returns True when inserted."""
    handles.validate(platform, handle)
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO competitor_candidate (handle, platform, language,"
            " discovery_source, query, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (handle, platform, language, discovery_source, query, notes, now_iso()),
        )
        return cur.rowcount == 1
    finally:
        conn.close()


# --- account writes -------------------------------------------------------------------------------


def _obs(conn, account_id, fieldname, value, provenance, method, run_id, confidence=None):
    conn.execute(
        "INSERT INTO competitor_field_obs (account_id, field, value, provenance, confidence,"
        " method, scan_run_id, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            account_id,
            fieldname,
            None if value is None else str(value),
            provenance,
            confidence,
            method,
            run_id,
            now_iso(),
        ),
    )


def _ensure_account(conn, cand) -> int:
    row = conn.execute(
        "SELECT id FROM competitor_account WHERE handle = ? AND platform = ?",
        (cand["handle"], cand["platform"]),
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO competitor_account (candidate_id, handle, platform, language)"
        " VALUES (?, ?, ?, ?)",
        (cand["id"], cand["handle"], cand["platform"], cand["language"]),
    )
    return cur.lastrowid


def _write(db: Database, fn: Callable) -> None:
    conn = db.connect()
    try:
        conn.execute("BEGIN")
        fn(conn)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _set_status(db: Database, cand, column: str, status: str, error: str | None = None) -> None:
    def w(conn):
        aid = _ensure_account(conn, cand)
        conn.execute(
            f"UPDATE competitor_account SET {column} = ?, fetch_error = ?, attempted_at = ?"
            " WHERE id = ?",
            (status, error, now_iso(), aid),
        )

    _write(db, w)


def _upsert_posts(conn, account_id: int, posts: list[dict], window_ids: set, provenance: str):
    ts = now_iso()
    for p in posts:
        conn.execute(
            "INSERT INTO competitor_post (account_id, post_id, posted_at, views, likes, comments,"
            " shares, saves, duration_s, description, pinned_comment, pinned, in_reach_window,"
            " provenance, captured_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(account_id, post_id) DO UPDATE SET"
            " posted_at = COALESCE(excluded.posted_at, posted_at),"
            " views = COALESCE(excluded.views, views), likes = COALESCE(excluded.likes, likes),"
            " comments = COALESCE(excluded.comments, comments),"
            " shares = COALESCE(excluded.shares, shares), saves = COALESCE(excluded.saves, saves),"
            " duration_s = COALESCE(excluded.duration_s, duration_s),"
            " description = COALESCE(excluded.description, description),"
            " pinned_comment = COALESCE(excluded.pinned_comment, pinned_comment),"
            " pinned = excluded.pinned, in_reach_window = excluded.in_reach_window,"
            " provenance = excluded.provenance, captured_at = excluded.captured_at",
            (
                account_id,
                str(p["id"]),
                p.get("timestamp"),
                p.get("view_count"),
                p.get("like_count"),
                p.get("comment_count"),
                p.get("repost_count"),
                p.get("save_count"),
                p.get("duration"),
                p.get("description"),
                p.get("pinned_comment"),
                int(bool(p.get("pinned"))),
                int(str(p["id"]) in window_ids),
                provenance,
                ts,
            ),
        )


# --- fetch orchestration --------------------------------------------------------------------------


@dataclass
class FetchReport:
    run_id: int
    stage: str
    ok: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    stopped: list = field(default_factory=list)
    lines: list = field(default_factory=list)


def _fresh(ts: str | None, fresh_hours: float, now_ts: float) -> bool:
    if not ts:
        return False
    try:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()
    except ValueError:
        return False
    return now_ts - t < fresh_hours * 3600


def _targets(db: Database, stage: str, lang: str | None, only: str | None) -> list:
    sql = (
        "SELECT c.id, c.handle, c.platform, c.language, c.status,"
        " a.id AS account_id, a.captured_at, a.posts_captured_at, a.followers"
        " FROM competitor_candidate c LEFT JOIN competitor_account a"
        " ON a.handle = c.handle AND a.platform = c.platform WHERE c.status != 'excluded'"
    )
    args: list = []
    if lang:
        sql += " AND c.language = ?"
        args.append(lang)
    if only:
        sql += " AND lower(c.handle) IN (?, ?)"
        args.extend([only.lower(), ("@" + only.lstrip("@")).lower()])
    elif stage == "posts":
        sql += " AND c.status = 'selected'"
    sql += " ORDER BY c.seed_named DESC, c.id"
    conn = db.connect()
    try:
        return list(conn.execute(sql, args).fetchall())
    finally:
        conn.close()


def run_fetch(
    db: Database,
    stage: str,
    *,
    lang: str | None = None,
    only: str | None = None,
    force: bool = False,
    refresh: bool = False,
    cfg: str | Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    now: Callable[[], float] = time.time,
    backoff_sleep: Callable[[float], None] = time.sleep,
) -> FetchReport:
    if stage not in ("profile", "posts"):
        raise ValueError("stage must be profile or posts")
    run_id = gate(db, f"fetch_{stage}", force, cfg)
    scfg = load_scan_config(cfg)
    pol_cfg = scfg.get("politeness") or {}
    polite = polite_from_config(
        scfg, sleep=sleep, rng=rng or random.Random(), backoff_sleep=backoff_sleep
    )
    fresh_hours = float(pol_cfg.get("fresh_hours", 72))
    playlistend = int(pol_cfg.get("playlistend", 30))
    yt_calls = int(pol_cfg.get("youtube_video_calls", 18))
    rep = FetchReport(run_id=run_id, stage=stage)
    ts_col = "captured_at" if stage == "profile" else "posts_captured_at"
    status_col = "fetch_status" if stage == "profile" else "posts_fetch_status"

    for cand in _targets(db, stage, lang, only):
        label = f"{cand['platform']}:{cand['handle']}"
        if not refresh and _fresh(cand[ts_col], fresh_hours, now()):
            rep.skipped.append(label)
            continue
        if polite.stopped(cand["platform"]):
            _set_status(db, cand, status_col, "stopped_failures")
            rep.stopped.append(label)
            continue
        try:
            if stage == "profile":
                line = _fetch_profile(db, cand, polite, run_id, playlistend, cfg)
            else:
                line = _fetch_posts(db, cand, polite, run_id, playlistend, yt_calls, now())
        except PlatformStopped:
            _set_status(db, cand, status_col, "stopped_failures")
            rep.stopped.append(label)
            continue
        except Exception as exc:  # one account failing never aborts the run
            polite.record(cand["platform"], False)
            _set_status(db, cand, status_col, "failed", f"{type(exc).__name__}: {exc}"[:500])
            rep.failed.append(label)
            rep.lines.append(f"{label}: failed ({type(exc).__name__}: {str(exc)[:160]})")
            continue
        if line is None:
            polite.record(cand["platform"], False)
            _set_status(db, cand, status_col, "no_data")
            rep.failed.append(label)
            rep.lines.append(f"{label}: no data (operator entry fallback: ndc scan add-manual)")
        else:
            polite.record(cand["platform"], True)
            rep.ok.append(label)
            rep.lines.append(f"{label}: {line}")
    finish_run(db, run_id)
    return rep


def _fetch_profile(db, cand, polite: Polite, run_id, playlistend, cfg) -> str | None:
    platform, handle = cand["platform"], cand["handle"]
    if platform == "tiktok":
        prof = polite.call(platform, tiktok.fetch_profile, handle)
        if not prof:
            return None
        method, posts = "tiktok_profile_html", None
    else:
        shorts = polite.call(platform, youtube.fetch_shorts, handle, playlistend)
        if not shorts or (shorts.get("subscribers") is None and not shorts.get("entries")):
            return None
        prof = {
            "followers": shorts.get("subscribers"),
            "video_count": None,
            "bio": shorts.get("description"),
            "bio_link": None,
            "channel_id": shorts.get("channel_id"),
        }
        method = "yt_shorts_flat"
        posts = [
            {"id": e["id"], "view_count": e.get("view_count"), "description": e.get("title")}
            for e in shorts.get("entries") or []
        ]
    tier = tier_for(prof.get("followers"), cfg)

    def w(conn):
        aid = _ensure_account(conn, cand)
        conn.execute(
            "UPDATE competitor_account SET followers = ?, tier = ?, video_count = ?, bio = ?,"
            " bio_link = ?, channel_id = COALESCE(?, channel_id), fetch_status = 'ok',"
            " fetch_error = NULL, attempted_at = ?, captured_at = ? WHERE id = ?",
            (
                prof.get("followers"),
                tier,
                prof.get("video_count"),
                prof.get("bio"),
                prof.get("bio_link"),
                prof.get("channel_id"),
                now_iso(),
                now_iso(),
                aid,
            ),
        )
        for f in ("followers", "video_count", "bio", "bio_link"):
            if prof.get(f) is not None:
                _obs(conn, aid, f, prof[f], "scraped", method, run_id)
        if posts:
            _upsert_posts(conn, aid, posts, set(), "scraped")

    _write(db, w)
    return f"followers {prof.get('followers')} tier {tier}"


def _reach_write(conn, aid, posts, eligible, run_id, method, median, n):
    window = {str(p["id"]) for p in eligible}
    conn.execute("UPDATE competitor_post SET in_reach_window = 0 WHERE account_id = ?", (aid,))
    _upsert_posts(conn, aid, posts, window, "scraped")
    conn.execute(
        "UPDATE competitor_account SET posts_fetch_status = 'ok', fetch_error = NULL,"
        " attempted_at = ?, posts_captured_at = ?, reach_median = ?, n_reach_posts = ?"
        " WHERE id = ?",
        (now_iso(), now_iso(), median, n, aid),
    )
    _obs(conn, aid, "reach_median", median, "scraped", method, run_id)
    _obs(conn, aid, "n_reach_posts", n, "scraped", method, run_id)


def _per_1k(posts: list[dict], key: str) -> float | None:
    pairs = [
        (p[key], p["view_count"]) for p in posts if p.get(key) is not None and p.get("view_count")
    ]
    views = sum(v for _, v in pairs)
    return round(1000 * sum(k for k, _ in pairs) / views, 2) if views else None


def _fetch_posts(db, cand, polite: Polite, run_id, playlistend, yt_calls, now_ts):
    platform, handle = cand["platform"], cand["handle"]
    if platform == "tiktok":
        posts = polite.call(platform, tiktok.fetch_posts, handle, playlistend)
        if not posts:
            return None
        method = "tiktok_flat_listing"
    else:
        ids = _stored_youtube_ids(db, cand)
        if not ids:
            shorts = polite.call(platform, youtube.fetch_shorts, handle, playlistend)
            ids = [e["id"] for e in (shorts or {}).get("entries") or []]
        if not ids:
            return None
        posts = []
        for vid in ids[:yt_calls]:
            try:
                v = polite.call(platform, youtube.fetch_video, vid)
            except PlatformStopped:
                raise
            except Exception:
                polite.record(platform, False)
                continue
            polite.record(platform, True)
            posts.append({**v, "repost_count": None, "save_count": None, "pinned": False})
        if not posts:
            return None
        method = "yt_video_metadata"
    eligible = tiktok.eligible_posts(posts, now_ts)
    median, n = tiktok.median_last15(posts, now_ts)

    def w(conn):
        aid = _ensure_account(conn, cand)
        _reach_write(conn, aid, posts, eligible, run_id, method, median, n)

    _write(db, w)
    saves, shares = _per_1k(eligible, "save_count"), _per_1k(eligible, "repost_count")
    return (
        f"{len(posts)} posts, {n} in reach window, median {median}, "
        f"saves/1k {saves}, shares/1k {shares}"
    )


def _stored_youtube_ids(db: Database, cand) -> list[str]:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT p.post_id FROM competitor_post p JOIN competitor_account a"
            " ON a.id = p.account_id WHERE a.handle = ? AND a.platform = 'youtube'"
            " ORDER BY p.id",
            (cand["handle"],),
        ).fetchall()
        return [r["post_id"] for r in rows]
    finally:
        conn.close()


# --- manual entry (Pitfall 4 fallback) ------------------------------------------------------


def add_manual(
    db: Database,
    handle: str,
    platform: str,
    followers: int | None,
    views: list[int],
    language: str | None = None,
    cfg: str | Path | None = None,
) -> dict:
    """Store operator-typed followers + newest view counts (newest first, >= 72 h old)."""
    handle = handles.validate(platform, handles.normalize(platform, handle))
    views = views[:15]
    median = statistics.median(views) if len(views) >= 8 else None
    tier = tier_for(followers, cfg)
    result = {}

    def w(conn):
        cand = conn.execute(
            "SELECT id, handle, platform, language FROM competitor_candidate"
            " WHERE handle = ? AND platform = ?",
            (handle, platform),
        ).fetchone()
        if cand is None:
            if language not in ("de", "en"):
                raise ValueError("new handle: --lang de|en is required")
            cid = conn.execute(
                "INSERT INTO competitor_candidate (handle, platform, language, discovery_source,"
                " created_at) VALUES (?, ?, ?, 'operator', ?)",
                (handle, platform, language, now_iso()),
            ).lastrowid
            cand = {"id": cid, "handle": handle, "platform": platform, "language": language}
        aid = _ensure_account(conn, cand)
        conn.execute(
            "UPDATE competitor_account SET followers = COALESCE(?, followers),"
            " tier = COALESCE(?, tier), fetch_status = 'operator_entered',"
            " posts_fetch_status = 'operator_entered', captured_at = ?, posts_captured_at = ?,"
            " reach_median = ?, n_reach_posts = ? WHERE id = ?",
            (followers, tier, now_iso(), now_iso(), median, len(views), aid),
        )
        conn.execute("UPDATE competitor_post SET in_reach_window = 0 WHERE account_id = ?", (aid,))
        posts = [{"id": f"manual-{i + 1}", "view_count": v} for i, v in enumerate(views)]
        _upsert_posts(conn, aid, posts, {p["id"] for p in posts}, "operator_entered")
        if followers is not None:
            _obs(conn, aid, "followers", followers, "operator_entered", "add-manual", None)
        _obs(conn, aid, "reach_median", median, "operator_entered", "add-manual", None)
        _obs(conn, aid, "n_reach_posts", len(views), "operator_entered", "add-manual", None)
        result.update(account_id=aid, reach_median=median, n=len(views), tier=tier)

    _write(db, w)
    return result
