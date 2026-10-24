"""`ndc scan prepare-judging`: per-account judging bundles in fixed batches (D-21).

Each language's accounts (sorted by account id) are split into `batches_per_language` batches
(de-1, de-2, en-1, en-2), so one batch fits one executor session. Per account the bundle holds
data only: captions.json (bio, newest 15 post captions, YouTube uploader pinned comments) and
transcripts.json (video_id -> transcript). The contact sheet path and the rubric/output paths sit
in the batch manifest. The executor writes /data/judging/<batch>/judgments.json by
config/judging_rubric.md and imports it with `ndc scan import-judgments`.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from ndc.db import Database
from ndc.scan.analyze import account_key, key_dirname

POSTS_PER_ACCOUNT = 15


@dataclass
class BundleReport:
    manifests: dict = field(default_factory=dict)  # batch -> manifest path
    counts: dict = field(default_factory=dict)  # batch -> n accounts


def _accounts(conn) -> list:
    sql = (
        "SELECT a.id, a.handle, a.platform, a.language, a.bio FROM competitor_account a"
        " LEFT JOIN competitor_candidate c ON c.handle = a.handle AND c.platform = a.platform"
    )
    rows = conn.execute(sql + " WHERE c.status = 'selected' ORDER BY a.id").fetchall()
    if not rows:  # nothing selected yet: every fetched account
        rows = conn.execute(sql + " WHERE a.fetch_status = 'ok' ORDER BY a.id").fetchall()
    return rows


def _posts(conn, aid: int) -> list:
    rows = conn.execute(
        "SELECT post_id, description, pinned_comment FROM competitor_post WHERE account_id = ?"
        " AND in_reach_window = 1 ORDER BY posted_at DESC LIMIT ?",
        (aid, POSTS_PER_ACCOUNT),
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT post_id, description, pinned_comment FROM competitor_post WHERE account_id = ?"
            " AND pinned = 0 ORDER BY posted_at DESC LIMIT ?",
            (aid, POSTS_PER_ACCOUNT),
        ).fetchall()
    return rows


def split(items: list, k: int) -> list[list]:
    k = max(1, k)
    size = -(-len(items) // k) if items else 0
    return [items[i * size : (i + 1) * size] for i in range(k)]


def prepare_judging(
    db: Database, judging_dir: str | Path, batches_per_language: int = 2
) -> BundleReport:
    judging_dir = Path(judging_dir)
    rep = BundleReport()
    conn = db.connect()
    try:
        accounts = _accounts(conn)
        for lang in ("de", "en"):
            chunks = split([a for a in accounts if a["language"] == lang], batches_per_language)
            for i, chunk in enumerate(chunks, start=1):
                batch = f"{lang}-{i}"
                bdir = judging_dir / batch
                bdir.mkdir(parents=True, exist_ok=True)
                keys, files = [], {}
                for a in chunk:
                    key = account_key(a["platform"], a["handle"])
                    adir = bdir / key_dirname(a["platform"], a["handle"])
                    adir.mkdir(parents=True, exist_ok=True)
                    posts = []
                    for p in _posts(conn, a["id"]):
                        entry = {"post_id": p["post_id"], "description": p["description"]}
                        if a["platform"] == "youtube" and p["pinned_comment"]:
                            entry["pinned_comment"] = p["pinned_comment"]
                        posts.append(entry)
                    captions = {
                        "account_key": key,
                        "language": a["language"],
                        "bio": a["bio"],
                        "posts": posts,
                    }
                    transcripts = {
                        r["platform_video_id"]: r["transcript"]
                        for r in conn.execute(
                            "SELECT platform_video_id, transcript FROM competitor_video"
                            " WHERE account_id = ? AND download_status = 'ok' ORDER BY id",
                            (a["id"],),
                        )
                    }
                    sheet = conn.execute(
                        "SELECT contact_sheet_path FROM competitor_video WHERE account_id = ?"
                        " AND contact_sheet_path IS NOT NULL ORDER BY id DESC LIMIT 1",
                        (a["id"],),
                    ).fetchone()
                    _write(adir / "captions.json", captions)
                    _write(adir / "transcripts.json", transcripts)
                    keys.append(key)
                    files[key] = {
                        "captions": str(adir / "captions.json"),
                        "transcripts": str(adir / "transcripts.json"),
                        "contact_sheet": sheet[0] if sheet else None,
                        "n_posts": len(posts),
                        "n_transcripts": len(transcripts),
                    }
                manifest = {
                    "batch": batch,
                    "accounts": keys,
                    "rubric": "config/judging_rubric.md",
                    "output": str(bdir / "judgments.json"),
                    "provenance": "llm_session",
                    "files": files,
                }
                _write(bdir / "manifest.json", manifest)
                rep.manifests[batch] = str(bdir / "manifest.json")
                rep.counts[batch] = len(keys)
    finally:
        conn.close()
    return rep


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
