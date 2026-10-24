"""`ndc scan analyze`: local video analysis per selected account (D-17, D-21).

Per account: download ~3 recent videos without login into a per-account directory, transcribe
(faster-whisper), estimate voice from pitch, sample frames into one contact sheet, then delete
the videos (always, also on error). Writes competitor_video rows and a voice_gender field obs
(provenance auto, method pitch_estimate), then recomputes needs_operator_check.

Gate: decision-rule lock (exit 3) and quiet hours (exit 4) before anything runs. Network and CPU
work finish before the DB write for that account; no transaction is held across them. Runs in
the capped `ndc-heavy` service only.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ndc.config import config_dir as _config_dir
from ndc.db import Database
from ndc.scan import fetch, frames, media, pitch, queue
from ndc.scan.fetch import PlatformStopped, now_iso


def account_key(platform: str, handle: str) -> str:
    return f"{platform}:{handle}"


def key_dirname(platform: str, handle: str) -> str:
    return f"{platform}_{handle.lstrip('@')}"


@dataclass
class VideoResult:
    video_id: str
    posted_at: int | None
    status: str  # ok | unavailable
    error: str | None = None
    transcript: str | None = None
    language: str | None = None
    duration_s: float | None = None
    pitch_hz: float | None = None
    estimate: pitch.PitchEstimate | None = None


@dataclass
class AccountResult:
    account_id: int
    key: str
    status: str  # analyzed | unavailable | no_posts
    videos: list = field(default_factory=list)
    voice: pitch.PitchEstimate | None = None
    contact_sheet: str | None = None


@dataclass
class AnalyzeReport:
    run_id: int | None = None
    results: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    lines: list = field(default_factory=list)


def analysis_config(cfg: str | Path | None = None) -> dict:
    return fetch.load_scan_config(cfg).get("analysis") or {}


def target_accounts(
    db: Database, only: str | None, lang: str | None, reanalyze: bool
) -> tuple[list, list]:
    conn = db.connect()
    try:
        sql = (
            "SELECT a.id, a.handle, a.platform, a.language FROM competitor_account a"
            " LEFT JOIN competitor_candidate c ON c.handle = a.handle AND c.platform = a.platform"
            " WHERE 1 = 1"
        )
        args: list = []
        if only:
            sql += " AND lower(a.handle) = lower(?)"
            args.append(only)
        else:
            sql += " AND c.status = 'selected'"
        if lang:
            sql += " AND a.language = ?"
            args.append(lang)
        rows = conn.execute(sql + " ORDER BY a.language, a.platform, a.handle", args).fetchall()
        todo, done = [], []
        for r in rows:
            analyzed = conn.execute(
                "SELECT 1 FROM competitor_video WHERE account_id = ? AND analyzed_at IS NOT NULL"
                " LIMIT 1",
                (r["id"],),
            ).fetchone()
            (done if analyzed and not reanalyze else todo).append(dict(r))
        return todo, done
    finally:
        conn.close()


def analyze_account(
    db: Database,
    acc: dict,
    acfg: dict,
    transcriber,
    polite: fetch.Polite,
    downloader: Callable = media.download_video,
    now_ts: float | None = None,
) -> AccountResult:
    platform, handle, aid = acc["platform"], acc["handle"], acc["id"]
    key = account_key(platform, handle)
    conn = db.connect()
    try:
        posts = media.eligible_posts(
            conn,
            aid,
            int(acfg.get("videos_per_account", 3)),
            float(acfg.get("max_video_seconds", 180)),
            now_ts,
        )
    finally:
        conn.close()
    res = AccountResult(aid, key, "no_posts")
    if not posts:
        return res
    male_max = float((acfg.get("pitch") or {}).get("male_max_hz", 160))
    female_min = float((acfg.get("pitch") or {}).get("female_min_hz", 185))
    max_mb = float(acfg.get("max_filesize_mb", 60))
    n_frames = int(acfg.get("frames_per_video", 2))
    sheet_frames = []

    def _try(url, out_dir):
        try:
            return "ok", downloader(url, out_dir, max_mb)
        except media.DownloadUnavailable as exc:
            return "unavailable", str(exc)

    with media.downloaded_media(acfg.get("media_dir", "/data/media"), aid) as tmp:
        for p in posts:
            vr = VideoResult(p.post_id, p.posted_at, "unavailable", duration_s=p.duration_s)
            try:
                url = media.video_url(platform, handle, p.post_id)
                status, got = polite.call(platform, _try, url, tmp)
            except PlatformStopped:
                vr.error = "not attempted: platform stopped after consecutive download failures"
                res.videos.append(vr)
                continue
            except ValueError as exc:
                vr.error = str(exc)
                res.videos.append(vr)
                continue
            polite.record(platform, status == "ok")
            if status != "ok":
                vr.error = got
                res.videos.append(vr)
                continue
            path = Path(got)
            try:
                t = transcriber.transcribe(path)
                vr.transcript, vr.language = t.text, t.language
                vr.duration_s = t.duration_s or vr.duration_s
                vr.estimate = pitch.estimate_from_file(
                    path, male_max, female_min, float(acfg.get("max_video_seconds", 180))
                )
                vr.pitch_hz = vr.estimate.median_hz
                for img in frames.sample_frames(path, n_frames):
                    sheet_frames.append((p.post_id, img))
                vr.status = "ok"
            except Exception as exc:  # a corrupt file must not stop the account
                vr.status, vr.error = "unavailable", f"analysis failed: {exc}"[:300]
            finally:
                path.unlink(missing_ok=True)  # delete each video as soon as it is analyzed
            res.videos.append(vr)
    ok = [v for v in res.videos if v.status == "ok"]
    res.status = "analyzed" if ok else "unavailable"
    if ok:
        res.voice = pitch.combine([v.estimate for v in ok if v.estimate], male_max, female_min)
        sheet = frames.compose_contact_sheet(
            sheet_frames,
            Path(acfg.get("judging_dir", "/data/judging"))
            / key_dirname(platform, handle)
            / "contact_sheet.jpg",
            int(acfg.get("contact_sheet_width_px", 1024)),
        )
        res.contact_sheet = str(sheet) if sheet else None
    return res


def store_result(db: Database, res: AccountResult, run_id: int | None) -> None:
    now = now_iso()
    conn = db.connect()
    try:
        conn.execute("BEGIN")
        try:
            for v in res.videos:
                conn.execute(
                    "INSERT INTO competitor_video (account_id, platform_video_id, posted_at,"
                    " duration_s, download_status, download_error, transcript, transcript_lang,"
                    " pitch_hz_median, contact_sheet_path, analyzed_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(account_id, platform_video_id) DO UPDATE SET"
                    " posted_at = excluded.posted_at, duration_s = excluded.duration_s,"
                    " download_status = excluded.download_status,"
                    " download_error = excluded.download_error, transcript = excluded.transcript,"
                    " transcript_lang = excluded.transcript_lang,"
                    " pitch_hz_median = excluded.pitch_hz_median,"
                    " contact_sheet_path = excluded.contact_sheet_path,"
                    " analyzed_at = excluded.analyzed_at",
                    (
                        res.account_id,
                        v.video_id,
                        v.posted_at,
                        v.duration_s,
                        v.status,
                        v.error,
                        v.transcript,
                        v.language,
                        v.pitch_hz,
                        res.contact_sheet if v.status == "ok" else None,
                        now,
                    ),
                )
            if res.voice is not None:
                e = res.voice
                conn.execute(
                    "INSERT INTO competitor_field_obs (account_id, field, value, provenance,"
                    " confidence, method, scan_run_id, observed_at)"
                    " VALUES (?, 'voice_gender', ?, 'auto', ?, ?, ?, ?)",
                    (
                        res.account_id,
                        e.gender,
                        e.confidence,
                        f"{pitch.METHOD} (median {e.median_hz} Hz, voiced share {e.voiced_share})",
                        run_id,
                        now,
                    ),
                )
            queue.recompute_conn(conn, res.account_id, now)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def run_analyze(
    db: Database,
    *,
    only: str | None = None,
    lang: str | None = None,
    force: bool = False,
    reanalyze: bool = False,
    cfg: str | Path | None = None,
    transcriber=None,
    downloader: Callable | None = None,
    polite: fetch.Polite | None = None,
    now_ts: float | None = None,
) -> AnalyzeReport:
    cfg = cfg or _config_dir()
    run_id = fetch.gate(db, "analyze", force, cfg)
    scfg = fetch.load_scan_config(cfg)
    acfg = scfg.get("analysis") or {}
    if transcriber is None:
        from ndc.scan.transcribe import Transcriber

        transcriber = Transcriber.from_config(acfg)
    polite = polite or fetch.polite_from_config(scfg)
    rep = AnalyzeReport(run_id=run_id)
    todo, done = target_accounts(db, only, lang, reanalyze)
    rep.skipped = [account_key(a["platform"], a["handle"]) for a in done]
    for acc in todo:
        res = analyze_account(
            db, acc, acfg, transcriber, polite, downloader or media.download_video, now_ts
        )
        if res.status != "no_posts":
            store_result(db, res, run_id)
        rep.results.append(res)
        ok = sum(v.status == "ok" for v in res.videos)
        voice = f", voice {res.voice.gender} ({res.voice.confidence})" if res.voice else ""
        rep.lines.append(f"{res.key}: {res.status}, {ok}/{len(res.videos)} videos{voice}")
    fetch.finish_run(db, run_id)
    return rep


def probe(db: Database, cfg: str | Path | None = None, force: bool = False) -> list[str]:
    """D-17 verify-first: one no-login download per platform from already-fetched accounts."""
    cfg = cfg or _config_dir()
    run_id = fetch.gate(db, "analyze_probe", force, cfg)
    acfg = analysis_config(cfg)
    lines = []
    conn = db.connect()
    try:
        picks = {}
        for platform in ("tiktok", "youtube"):
            r = conn.execute(
                "SELECT a.handle, p.post_id FROM competitor_post p"
                " JOIN competitor_account a ON a.id = p.account_id"
                " WHERE a.platform = ? AND p.pinned = 0 AND p.posted_at IS NOT NULL"
                " AND (p.duration_s IS NULL OR p.duration_s <= ?)"
                " ORDER BY p.posted_at DESC LIMIT 1",
                (platform, float(acfg.get("max_video_seconds", 180))),
            ).fetchone()
            picks[platform] = r
    finally:
        conn.close()
    for platform, r in picks.items():
        if r is None:
            lines.append(f"{platform}: no fetched post to probe")
            continue
        verdict, detail = media.probe_download(
            platform,
            r["handle"],
            r["post_id"],
            acfg.get("media_dir", "/data/media"),
            float(acfg.get("max_filesize_mb", 60)),
        )
        lines.append(f"{platform}: {verdict} ({r['handle']} {r['post_id']}): {detail}")
    fetch.add_run_note(db, run_id, " | ".join(lines))
    fetch.finish_run(db, run_id)
    return lines
