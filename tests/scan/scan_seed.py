"""Shared seeding helpers for the plan 01-06 judgment/analysis tests."""


def seed_account(db, handle, platform="tiktok", lang="de", followers=25000, posts=(), videos=()):
    """posts: [(post_id, description, pinned_comment)], videos: [(video_id, transcript, status)]."""
    conn = db.connect()
    try:
        cid = conn.execute(
            "INSERT INTO competitor_candidate (handle, platform, language, discovery_source,"
            " seed_named, status, created_at) VALUES (?, ?, ?, 'test', 0, 'selected', 'x')",
            (handle, platform, lang),
        ).lastrowid
        aid = conn.execute(
            "INSERT INTO competitor_account (candidate_id, handle, platform, language, followers,"
            " tier, fetch_status, bio) VALUES (?, ?, ?, ?, ?, 'mid', 'ok', 'bio text')",
            (cid, handle, platform, lang, followers),
        ).lastrowid
        for i, (pid, desc, pinned) in enumerate(posts):
            conn.execute(
                "INSERT INTO competitor_post (account_id, post_id, posted_at, views, description,"
                " pinned_comment, in_reach_window, captured_at)"
                " VALUES (?, ?, ?, 100, ?, ?, 1, 'x')",
                (aid, pid, 1_700_000_000 - i * 86400, desc, pinned),
            )
        for vid, transcript, status in videos:
            conn.execute(
                "INSERT INTO competitor_video (account_id, platform_video_id, download_status,"
                " transcript) VALUES (?, ?, ?, ?)",
                (aid, vid, status, transcript),
            )
        return aid
    finally:
        conn.close()


def obs_rows(db, aid, field=None):
    conn = db.connect()
    try:
        sql = "SELECT * FROM competitor_field_obs WHERE account_id = ?"
        args = [aid]
        if field:
            sql += " AND field = ?"
            args.append(field)
        return [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]
    finally:
        conn.close()


def sheet_row(db, aid):
    conn = db.connect()
    try:
        return dict(
            conn.execute("SELECT * FROM v_competitor_sheet WHERE account_id = ?", (aid,)).fetchone()
        )
    finally:
        conn.close()


def add_obs(db, aid, field, value, provenance="auto", confidence="medium", method="test"):
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO competitor_field_obs (account_id, field, value, provenance, confidence,"
            " method, observed_at) VALUES (?, ?, ?, ?, ?, ?, '2026-10-24T10:00:00Z')",
            (aid, field, value, provenance, confidence, method),
        )
    finally:
        conn.close()


def make_video(path, hz=120, seconds=2.0, w=64, h=96, fps=10, sr=16000):
    """Tiny real mp4 (mpeg4 + aac) with a voice-like tone, for analysis tests."""
    import fractions

    import av
    import numpy as np

    with av.open(str(path), "w") as c:
        vs = c.add_stream("mpeg4", rate=fps)
        vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
        aus = c.add_stream("aac", rate=sr)
        aus.layout = "mono"
        for i in range(int(seconds * fps)):
            img = np.full((h, w, 3), (i * 10) % 255, dtype=np.uint8)
            for p in vs.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
                c.mux(p)
        t = np.arange(int(sr * seconds)) / sr
        y = (0.3 * np.sin(2 * np.pi * hz * t) + 0.15 * np.sin(4 * np.pi * hz * t)).astype(
            np.float32
        )
        for k in range(0, len(y), 1024):
            f = av.AudioFrame.from_ndarray(
                y[k : k + 1024].reshape(1, -1), format="fltp", layout="mono"
            )
            f.sample_rate, f.pts, f.time_base = sr, k, fractions.Fraction(1, sr)
            for p in aus.encode(f):
                c.mux(p)
        for p in vs.encode():
            c.mux(p)
        for p in aus.encode():
            c.mux(p)
    return path
