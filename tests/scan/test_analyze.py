"""`ndc scan analyze` orchestration (plan 01-06 Task 4, D-17). Download + Whisper mocked."""

import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scan_seed import make_video, obs_rows, seed_account, sheet_row

from ndc.cli import app
from ndc.scan import analyze, fetch, media, quiet_hours
from ndc.scan.transcribe import Transcript

REPO_CFG = Path(__file__).resolve().parents[2] / "config"
NOW = time.time()


@pytest.fixture(autouse=True)
def _noon(monkeypatch):
    monkeypatch.setattr(quiet_hours, "utcnow", lambda: datetime(2026, 10, 24, 12, 0, tzinfo=UTC))


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Repo config with media/judging dirs redirected into tmp."""
    import yaml

    c = tmp_path / "config"
    shutil.copytree(REPO_CFG, c)
    scan = yaml.safe_load((c / "scan.yaml").read_text())
    scan["analysis"]["media_dir"] = str(tmp_path / "media")
    scan["analysis"]["judging_dir"] = str(tmp_path / "judging")
    (c / "scan.yaml").write_text(yaml.safe_dump(scan))
    monkeypatch.setenv("NDC_CONFIG_DIR", str(c))
    return c


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe(self, audio):
        assert hasattr(audio, "dtype")  # decoded once, array handed to whisper
        self.calls.append(len(audio))
        return Transcript(text=f"laut Leitlinie {len(self.calls)}", language="de", duration_s=2.0)


def _polite():
    return fetch.Polite(sleep=lambda s: None, backoff_sleep=lambda s: None)


def _seed(db, n=3):
    posts = [(f"7{i:05d}", f"caption {i}", None) for i in range(n)]
    aid = seed_account(db, "alpha_adhs", posts=posts)
    conn = db.connect()
    try:  # all posts >= 72 h old
        conn.execute(
            "UPDATE competitor_post SET posted_at = ? - 4 * 86400 - id WHERE account_id = ?",
            (int(NOW), aid),
        )
    finally:
        conn.close()
    return aid


def test_analyze_writes_rows_and_deletes_videos(db, cfg, tmp_path):
    aid = _seed(db)
    seen_dirs, urls = [], []

    def downloader(url, out_dir, max_mb):
        urls.append(url)
        seen_dirs.append(out_dir)
        return make_video(out_dir / f"{url.rsplit('/', 1)[-1]}.mp4", hz=120)

    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=downloader, polite=_polite()
    )
    assert rep.results[0].status == "analyzed"
    assert all("tiktok.com/@alpha_adhs/video/" in u for u in urls) and len(urls) == 3
    conn = db.connect()
    try:
        vids = conn.execute(
            "SELECT * FROM competitor_video WHERE account_id = ? ORDER BY id", (aid,)
        ).fetchall()
    finally:
        conn.close()
    assert len(vids) == 3
    assert all(v["download_status"] == "ok" and v["transcript"].startswith("laut") for v in vids)
    assert all(v["pitch_hz_median"] == pytest.approx(120, rel=0.08) for v in vids)
    sheet = Path(vids[0]["contact_sheet_path"])
    assert sheet.is_file() and sheet.suffix == ".jpg"
    assert not seen_dirs[0].exists()  # per-account media dir removed
    assert not any((tmp_path / "media").rglob("*.mp4"))
    voice = obs_rows(db, aid, "voice_gender")[-1]
    assert voice["value"] == "male" and voice["provenance"] == "auto"
    assert voice["method"].startswith("pitch_estimate") and voice["confidence"] in (
        "medium",
        "high",
    )
    assert sheet_row(db, aid)["voice_gender"] == "male"
    assert sheet_row(db, aid)["needs_operator_check"] in ("true", "false")


def test_videos_deleted_on_error(db, cfg, tmp_path):
    _seed(db, n=1)

    class Boom:
        def transcribe(self, path):
            raise RuntimeError("decoder crashed")

    def downloader(url, out_dir, max_mb):
        return make_video(out_dir / "x.mp4")

    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=Boom(), downloader=downloader, polite=_polite()
    )
    assert rep.results[0].status == "unavailable"
    assert not any((tmp_path / "media").rglob("*.mp4"))


def test_all_downloads_fail_unavailable_no_retry(db, cfg):
    aid = _seed(db)
    calls = []

    def downloader(url, out_dir, max_mb):
        calls.append(url)
        raise media.DownloadUnavailable("login required")

    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=downloader, polite=_polite()
    )
    assert rep.results[0].status == "unavailable"
    assert len(calls) == 3  # one attempt per video, no retries
    conn = db.connect()
    try:
        st = [
            r[0]
            for r in conn.execute(
                "SELECT download_status FROM competitor_video WHERE account_id = ?", (aid,)
            )
        ]
    finally:
        conn.close()
    assert st == ["unavailable"] * 3
    assert obs_rows(db, aid, "voice_gender") == []
    assert sheet_row(db, aid)["needs_operator_check"] == "true"


def test_download_opts_have_no_login():
    opts = media._ydl_opts(Path("/tmp/x"), 60)
    for bad in ("cookiefile", "cookiesfrombrowser", "username", "password", "impersonate"):
        assert bad not in opts
    assert opts["format"] == "b[height<=720]/b"


def test_resumable_skip(db, cfg):
    _seed(db, n=1)

    def downloader(url, out_dir, max_mb):
        return make_video(out_dir / "x.mp4")

    analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=downloader, polite=_polite()
    )
    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=downloader, polite=_polite()
    )
    assert rep.results == [] and rep.skipped == ["tiktok:alpha_adhs"]


def test_analyze_cli_quiet_hours(db, cfg, runner, monkeypatch):
    monkeypatch.setattr(quiet_hours, "utcnow", lambda: datetime(2026, 10, 24, 2, 0, tzinfo=UTC))
    res = runner.invoke(app, ["scan", "analyze"])
    assert res.exit_code == 4


def test_analyze_cli_needs_rule_lock(db, tmp_path, runner, monkeypatch):
    c = tmp_path / "nolock"
    c.mkdir()
    for f in ("decision_rule.yaml", "scan.yaml"):
        shutil.copy(REPO_CFG / f, c / f)
    monkeypatch.setenv("NDC_CONFIG_DIR", str(c))
    res = runner.invoke(app, ["scan", "analyze"])
    assert res.exit_code == 3


def test_split_fallback_when_no_progressive(monkeypatch, tmp_path):
    calls = []

    def fake_one(url, out_dir, mb, fmt, tag):
        calls.append(fmt)
        if fmt == media.FORMAT:
            raise media.DownloadUnavailable("ERROR: Requested format is not available.")
        p = out_dir / f"v{tag}.bin"
        out_dir.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(media, "_download_one", fake_one)
    files = media.download_video("u", tmp_path)
    assert calls == [media.FORMAT, media.AUDIO_FORMAT, media.FRAMES_FORMAT]
    assert files.audio.name == "v.audio.bin" and files.frames.name == "v.frames.bin"


def test_login_wall_not_retried_with_fallback(monkeypatch, tmp_path):
    calls = []

    def fake_one(url, out_dir, mb, fmt, tag):
        calls.append(fmt)
        raise media.DownloadUnavailable("ERROR: login required")

    monkeypatch.setattr(media, "_download_one", fake_one)
    with pytest.raises(media.DownloadUnavailable):
        media.download_video("u", tmp_path)
    assert calls == [media.FORMAT]


def test_analyze_with_separate_audio_and_frames(db, cfg, tmp_path):
    aid = _seed(db, n=1)

    def downloader(url, out_dir, max_mb):
        a = make_video(out_dir / "x.audio.mp4", hz=220)
        v = make_video(out_dir / "x.frames.mp4", hz=220)
        return media.MediaFiles(a, v)

    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=downloader, polite=_polite()
    )
    assert rep.results[0].status == "analyzed" and rep.results[0].contact_sheet
    assert obs_rows(db, aid, "voice_gender")[-1]["value"] == "female"
    assert not any((tmp_path / "media").rglob("*.mp4"))


def test_analyze_stops_between_accounts_when_quiet_hours_begin(db, cfg, monkeypatch):
    """HI-04: a long analyze run re-checks quiet hours before each account and stops cleanly."""
    for handle in ("alpha_adhs", "beta_adhs"):
        aid = seed_account(db, handle, posts=[(f"7{handle.startswith('b'):05d}9", "c", None)])
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE competitor_post SET posted_at = ? WHERE account_id = ?",
                (int(NOW) - 5 * 86400, aid),
            )
        finally:
            conn.close()
    clock = {"t": datetime(2026, 10, 24, 23, 59, tzinfo=UTC)}
    monkeypatch.setattr(quiet_hours, "utcnow", lambda: clock["t"])

    def downloader(url, out_dir, max_mb):
        clock["t"] = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
        return make_video(out_dir / "x.mp4")

    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=downloader, polite=_polite()
    )
    assert len(rep.results) == 1 and rep.stopped_quiet_hours
    assert any("entered quiet hours" in line for line in rep.lines)
    clock["t"] = datetime(2026, 10, 25, 7, 0, tzinfo=UTC)
    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=downloader, polite=_polite()
    )
    assert len(rep.results) == 1 and len(rep.skipped) == 1  # resumed with the other account


def test_platform_stop_does_not_mark_unattempted_accounts_analyzed(db, cfg):
    """HI-05: after Polite stops the platform, later accounts are not stored as analyzed and are
    picked up again by the next run; attempted-but-failed accounts are retried too."""
    ids = {}
    for i, handle in enumerate(("alpha_adhs", "beta_adhs")):
        posts = [(f"7{i}{j:04d}", "c", None) for j in range(3)]
        ids[handle] = seed_account(db, handle, posts=posts)
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE competitor_post SET posted_at = ? - id WHERE account_id = ?",
                (int(NOW) - 5 * 86400, ids[handle]),
            )
        finally:
            conn.close()
    calls = []

    def failing(url, out_dir, max_mb):
        calls.append(url)
        raise media.DownloadUnavailable("blocked")

    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=failing, polite=_polite()
    )
    by = {r.key: r for r in rep.results}
    assert len(calls) == 3  # three consecutive failures stop the platform
    assert by["tiktok:beta_adhs"].status == "not_attempted"
    conn = db.connect()
    try:
        beta_rows = conn.execute(
            "SELECT COUNT(*) FROM competitor_video WHERE account_id = ?", (ids["beta_adhs"],)
        ).fetchone()[0]
    finally:
        conn.close()
    assert beta_rows == 0
    todo, done = analyze.target_accounts(db, None, None, False)
    assert {a["handle"] for a in todo} == {"alpha_adhs", "beta_adhs"} and done == []

    def ok(url, out_dir, max_mb):
        return make_video(out_dir / "x.mp4")

    rep = analyze.run_analyze(
        db, cfg=cfg, transcriber=FakeTranscriber(), downloader=ok, polite=_polite()
    )
    assert {r.key: r.status for r in rep.results} == {
        "tiktok:alpha_adhs": "analyzed",
        "tiktok:beta_adhs": "analyzed",
    }
