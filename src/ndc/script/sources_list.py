"""Caption / pinned-comment source lists, rendered purely from DB rows (SCR-04, D-08).

Only sources actually cited by sentences of an APPROVED version are listed, in first-citation
order. Nothing here is model-written; citations are never truncated.
"""

import json

import yaml

from ndc.config import config_dir
from ndc.db import Database
from ndc.review.store import latest_decision


class NotApproved(Exception):
    pass


def load_cfg() -> dict:
    return yaml.safe_load((config_dir() / "source_list.yaml").read_text(encoding="utf-8"))


def cited_sources(conn, version_id: int) -> list:
    rows = conn.execute(
        "SELECT s.*, min(ss.ordinal) AS first_ord FROM script_sentence ss "
        "JOIN script_citation sc ON sc.script_sentence_id = ss.id "
        "JOIN source_sentence src ON src.id = sc.source_sentence_id "
        "JOIN source_snapshot snap ON snap.id = src.snapshot_id "
        "JOIN source s ON s.id = snap.source_id "
        "WHERE ss.script_version_id = ? GROUP BY s.id ORDER BY first_ord, s.id",
        (version_id,),
    ).fetchall()
    return rows


def _first_author(s) -> tuple[str, bool]:
    authors = json.loads(s["authors_json"] or "[]")
    first = authors[0] if authors else ""
    return first, len(authors) > 1


def caption_line(s) -> str:
    if s["kind"] == "awmf":
        return (
            f"AWMF S3-Leitlinie {s['title']} ({s['awmf_reg_no']}), Version {s['awmf_version']}, "
            f"gültig bis {s['awmf_valid_until']}"
        )
    first, many = _first_author(s)
    who = f"{first} et al." if many else first
    ident = f"doi:{s['doi']}" if s["doi"] else f"PMID {s['pmid']}"
    journal = f" {s['journal']}." if s["journal"] else ""
    return f"{who} ({s['year']}).{journal} {ident}".strip()


def comment_entry(s) -> str:
    if s["kind"] == "awmf":
        return f"AWMF {s['awmf_reg_no']} ({s['awmf_version']})"
    first, _ = _first_author(s)
    ident = f"PMID {s['pmid']}" if s["pmid"] else f"doi:{s['doi']}"
    return f"{first} {s['year']} ({ident})"


def pack_comments(entries: list[str], prefix: str, limit: int) -> list[str]:
    """Join entries into as few comments as fit; never cut an entry."""

    def pack(n_parts: int) -> list[list[str]]:
        parts: list[list[str]] = [[]]
        for e in entries:
            head = f"{prefix} {len(parts)}/{n_parts}: " if n_parts > 1 else f"{prefix}: "
            cand = parts[-1] + [e]
            if parts[-1] and len(head + "; ".join(cand)) > limit:
                parts.append([e])
            else:
                parts[-1] = cand
        return parts

    n = 1
    for _ in range(10):  # head length depends on the part count; iterate to a fixed point
        parts = pack(n)
        if len(parts) == n:
            break
        n = len(parts)
    if n == 1:
        return [f"{prefix}: " + "; ".join(parts[0])]
    return [f"{prefix} {i}/{n}: " + "; ".join(p) for i, p in enumerate(parts, start=1)]


def render(db: Database, sha: str, variant: str = "caption") -> list[str]:
    cfg = load_cfg()
    conn = db.connect()
    try:
        v = conn.execute("SELECT * FROM script_version WHERE sha256 = ?", (sha,)).fetchone()
        if v is None:
            raise NotApproved("Version nicht gefunden")
        dec = latest_decision(conn, sha)
        if dec is None or dec["decision"] != "approved":
            raise NotApproved("Version ist nicht freigegeben")
        srcs = cited_sources(conn, v["id"])
    finally:
        conn.close()
    if not srcs:
        raise NotApproved("keine zitierten Quellen")
    if variant == "caption":
        text = "\n".join([cfg["labels"]["heading"], *(caption_line(s) for s in srcs)])
        return [text]
    if variant == "comment":
        return pack_comments(
            [comment_entry(s) for s in srcs],
            cfg["labels"]["comment_prefix"],
            int(cfg["comment_max_chars"]),
        )
    raise ValueError(f"unknown variant {variant!r}")
