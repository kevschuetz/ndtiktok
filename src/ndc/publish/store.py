"""Publish log (MEAS-02) and caption / pinned-comment rendering (D-05).

A publication row can only exist for an APPROVED script version, after the readout rule is locked,
when every PUBLISH_GATES hook (plan 03-03 adds the recording approval) is silent, and for a post URL
on an allowed platform host. Rows are append-only; nothing here touches the network (D-16).
"""

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import yaml

from ndc import launch_sets, readout
from ndc.config import config_dir
from ndc.db import Database
from ndc.review.store import latest_decision
from ndc.script import sources_list

PLATFORMS = ("tiktok", "youtube", "instagram")
ALLOWED_HOSTS = {
    "tiktok": {"tiktok.com", "www.tiktok.com", "vm.tiktok.com", "m.tiktok.com"},
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
    "instagram": {"instagram.com", "www.instagram.com"},
}
# Hooks: (conn, script_sha, recording_sha) -> list[Issue]; kinds starting with "block" refuse.
PUBLISH_GATES: list[Callable] = []

_BROAD_BY_CONDITION = {"adhd": "#ADHS", "autism": "#Autismus", "audhd": "#ADHS"}


class PublishRefused(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_metrics_cfg() -> dict:
    return yaml.safe_load((config_dir() / "metrics.yaml").read_text(encoding="utf-8")) or {}


def resolve_script_sha(conn, ref: str) -> str:
    ref = (ref or "").strip().lower()
    if len(ref) < 8 or any(c not in "0123456789abcdef" for c in ref):
        raise PublishRefused("Skript-Sha: mindestens 8 Hex-Zeichen angeben")
    rows = conn.execute(
        "SELECT sha256 FROM script_version WHERE sha256 LIKE ?", (ref + "%",)
    ).fetchall()
    if len(rows) != 1:
        raise PublishRefused(f"Skriptversion {ref} nicht gefunden oder mehrdeutig")
    return rows[0][0]


def parse_post_url(platform: str, url: str) -> str:
    """Validate host against the platform allow-list and extract the post id. No network."""
    if platform not in PLATFORMS:
        raise PublishRefused(f"unbekannte Plattform {platform!r}")
    u = urlparse((url or "").strip())
    host = (u.hostname or "").lower()
    if u.scheme not in ("http", "https") or host not in ALLOWED_HOSTS[platform]:
        raise PublishRefused(f"URL-Host {host or '?'} ist für {platform} nicht erlaubt")
    path = u.path.rstrip("/")
    if platform == "tiktok":
        m = re.search(r"/(?:video|photo)/(\d+)$", path) or re.search(r"^/(\w+)$", path)
    elif platform == "youtube":
        m = re.search(r"/shorts/([\w-]+)$", path) or re.search(r"^/([\w-]{6,})$", path)
        if not m and "v" in parse_qs(u.query):
            return parse_qs(u.query)["v"][0]
    else:
        m = re.search(r"/(?:reel|reels|p)/([\w-]+)$", path)
    if not m:
        raise PublishRefused(f"keine Post-ID in der URL erkennbar: {url}")
    return m.group(1)


def _sha(text: str | None) -> str | None:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None


def log_publication(
    db: Database,
    *,
    platform: str,
    script_sha: str,
    post_url: str,
    recording_sha: str | None = None,
    posted_at: str | None = None,
    hook_tactic: str | None = None,
    caption_text: str | None = None,
    pinned_text: str | None = None,
    channel: str = "cli",
) -> int:
    post_id = parse_post_url(platform, post_url)
    posted_at = posted_at or _now()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            sha = resolve_script_sha(conn, script_sha)
            v = conn.execute("SELECT * FROM script_version WHERE sha256 = ?", (sha,)).fetchone()
            dec = latest_decision(conn, sha)
            if dec is None or dec["decision"] != "approved":
                raise PublishRefused("Skriptversion ist nicht freigegeben")
            try:
                readout.check_locked(conn)
            except (readout.ReadoutNotLocked, readout.ReadoutChanged) as e:
                raise PublishRefused(str(e)) from e
            issues = [i for hook in PUBLISH_GATES for i in hook(conn, sha, recording_sha)]
            blockers = [i.message_de for i in issues if i.kind.startswith("block")]
            if blockers:
                raise PublishRefused("; ".join(blockers))
            topic = conn.execute(
                "SELECT t.* FROM script s JOIN topic t ON t.id = s.topic_id WHERE s.id = ?",
                (v["script_id"],),
            ).fetchone()
            if platform != "tiktok":
                first = conn.execute(
                    "SELECT id FROM publication WHERE platform = 'tiktok' AND script_sha256 = ?",
                    (sha,),
                ).fetchone()
                if first is None:
                    raise PublishRefused(
                        "zuerst die TikTok-Veröffentlichung loggen (Cross-Posts replizieren sie)"
                    )
            rec_id = None
            if recording_sha and _table_exists(conn, "recording"):
                r = conn.execute(
                    "SELECT id FROM recording WHERE transcript_sha256 = ?", (recording_sha,)
                ).fetchone()
                rec_id = r["id"] if r else None
            pid = conn.execute(
                "INSERT INTO publication (script_version_id, script_sha256, recording_id, "
                "recording_sha256, topic_id, pillar, angle, hook_tactic, platform, post_id, "
                "post_url, posted_at, caption_sha256, pinned_sha256, channel) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    v["id"],
                    sha,
                    rec_id,
                    recording_sha,
                    topic["id"],
                    topic["pillar"],
                    topic["angle"],
                    hook_tactic,
                    platform,
                    post_id,
                    post_url.strip(),
                    posted_at,
                    _sha(caption_text),
                    _sha(pinned_text),
                    channel,
                ),
            ).lastrowid
            conn.execute("COMMIT")
            return pid
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def _table_exists(conn, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _topic_for_sha(conn, sha: str):
    return conn.execute(
        "SELECT t.* FROM script_version v JOIN script s ON s.id = v.script_id "
        "JOIN topic t ON t.id = s.topic_id WHERE v.sha256 = ?",
        (sha,),
    ).fetchone()


def hashtags_for(topic) -> list[str]:
    """1 broad (by condition) + 2 niche + 1 pillar tag, all from the approved hashtag set."""
    hs = launch_sets.load_hashtags()
    broad = _BROAD_BY_CONDITION.get(topic["condition"], hs.broad[0])
    niche = [t for t in hs.niche if topic["condition"] == "audhd" or t.lower() != "#audhs"]
    niche = niche[: max(1, min(2, hs.scheme.niche[-1]))]
    pillar_tags = hs.pillars.get(topic["pillar"]) or []
    tags = [broad, *niche, *pillar_tags[:1]]
    lo, hi = hs.scheme.total
    assert lo <= len(tags) <= hi, tags
    return tags


def render_caption(db: Database, script_ref: str) -> str:
    conn = db.connect()
    try:
        sha = resolve_script_sha(conn, script_ref)
        topic = _topic_for_sha(conn, sha)
    finally:
        conn.close()
    body = sources_list.render(db, sha, "caption")[0]
    return body + "\n\n" + " ".join(hashtags_for(topic))


def render_pinned(db: Database, script_ref: str) -> list[str]:
    conn = db.connect()
    try:
        sha = resolve_script_sha(conn, script_ref)
        topic = _topic_for_sha(conn, sha)
    finally:
        conn.close()
    parts = sources_list.render(db, sha, "comment")
    if topic["domain"] in (load_metrics_cfg().get("pinned_crisis_domains") or []):
        parts.append(launch_sets.load_crisis_lines().short_form)
    return parts


def list_publications(conn) -> list:
    return conn.execute(
        "SELECT p.*, t.working_title FROM publication p JOIN topic t ON t.id = p.topic_id "
        "ORDER BY p.id DESC"
    ).fetchall()
