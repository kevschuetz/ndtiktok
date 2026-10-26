"""Immutable source snapshots, topic picks and locked corpora (SRC-03, D-09)."""

import hashlib
import json
import unicodedata
from datetime import UTC, datetime

from ndc import artifacts
from ndc.db import Database
from ndc.sources.pubmed import SentenceRow, SourceMeta

MIN_SOURCES = 2
MAX_SOURCES = 5


class StoreError(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nfc(s: str | None) -> str | None:
    return unicodedata.normalize("NFC", s) if s is not None else None


def snapshot_sha256(sentences: list[SentenceRow]) -> str:
    canon = [{"section": _nfc(s.section), "page": s.page, "text": _nfc(s.text)} for s in sentences]
    blob = json.dumps(canon, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _upsert_source(conn, meta: SourceMeta) -> int:
    row = None
    if meta.pmid:
        row = conn.execute("SELECT id FROM source WHERE pmid = ?", (meta.pmid,)).fetchone()
    if row is None and meta.doi:
        row = conn.execute("SELECT id FROM source WHERE doi = ?", (meta.doi,)).fetchone()
    if row is None and meta.awmf_reg_no:
        row = conn.execute(
            "SELECT id FROM source WHERE awmf_reg_no = ? AND awmf_version = ?",
            (meta.awmf_reg_no, meta.awmf_version),
        ).fetchone()
    vals = (
        meta.kind, meta.pmid, meta.pmcid, meta.doi, meta.awmf_reg_no, meta.awmf_version,
        meta.awmf_valid_until, meta.awmf_status, _nfc(meta.title),
        json.dumps(meta.authors, ensure_ascii=False), meta.year, meta.journal,
        json.dumps(meta.pubtypes, ensure_ascii=False), meta.language,
    )
    if row is None:
        cur = conn.execute(
            "INSERT INTO source (kind, pmid, pmcid, doi, awmf_reg_no, awmf_version, "
            "awmf_valid_until, awmf_status, title, authors_json, year, journal, pubtypes_json, "
            "language) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            vals,
        )
        return cur.lastrowid
    # Metadata may be refreshed; snapshots never change.
    conn.execute(
        "UPDATE source SET kind=?, pmid=?, pmcid=?, doi=?, awmf_reg_no=?, awmf_version=?, "
        "awmf_valid_until=?, awmf_status=?, title=?, authors_json=?, year=?, journal=?, "
        "pubtypes_json=?, language=? WHERE id=?",
        (*vals, row["id"]),
    )
    return row["id"]


def store_snapshot(
    db: Database,
    meta: SourceMeta,
    sentences: list[SentenceRow],
    origin: str,
    raw_bytes: bytes | None = None,
    raw_ext: str = "xml",
) -> int:
    """Store (or reuse) an immutable snapshot; returns snapshot id."""
    if not sentences:
        raise StoreError("no sentences to store")
    sha = snapshot_sha256(sentences)
    raw_sha = artifacts.put(raw_bytes, raw_ext) if raw_bytes is not None else None
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            source_id = _upsert_source(conn, meta)
            existing = conn.execute(
                "SELECT id FROM source_snapshot WHERE sha256 = ?", (sha,)
            ).fetchone()
            if existing:
                conn.execute("COMMIT")
                return existing["id"]
            cur = conn.execute(
                "INSERT INTO source_snapshot (source_id, sha256, origin, retrieved_at, "
                "raw_artifact_sha256, n_sentences) VALUES (?,?,?,?,?,?)",
                (source_id, sha, origin, _now(), raw_sha, len(sentences)),
            )
            snap_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO source_sentence (snapshot_id, ordinal, section, page, text) "
                "VALUES (?,?,?,?,?)",
                [
                    (snap_id, i, _nfc(s.section), s.page, _nfc(s.text))
                    for i, s in enumerate(sentences)
                ],
            )
            conn.execute("COMMIT")
            return snap_id
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def require_whitelisted(conn, topic_id: int) -> None:
    row = conn.execute("SELECT list_tag FROM topic WHERE id = ?", (topic_id,)).fetchone()
    if row is None:
        raise StoreError(f"topic {topic_id} not found")
    if row["list_tag"] != "whitelist":
        raise StoreError(f"topic {topic_id} not whitelisted")


def _distinct_sources(conn, topic_id: int) -> set[int]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT ss.source_id FROM topic_pick tp "
            "JOIN source_snapshot ss ON ss.id = tp.snapshot_id WHERE tp.topic_id = ?",
            (topic_id,),
        )
    }


def pick(db: Database, topic_id: int, snapshot_id: int) -> None:
    conn = db.connect()
    try:
        require_whitelisted(conn, topic_id)
        snap = conn.execute(
            "SELECT source_id FROM source_snapshot WHERE id = ?", (snapshot_id,)
        ).fetchone()
        if snap is None:
            raise StoreError(f"snapshot {snapshot_id} not found")
        sources = _distinct_sources(conn, topic_id)
        if snap["source_id"] not in sources and len(sources) >= MAX_SOURCES:
            raise StoreError(f"topic {topic_id} already has {MAX_SOURCES} sources")
        conn.execute(
            "INSERT OR IGNORE INTO topic_pick (topic_id, snapshot_id) VALUES (?, ?)",
            (topic_id, snapshot_id),
        )
    finally:
        conn.close()


def unpick(db: Database, topic_id: int, snapshot_id: int) -> None:
    conn = db.connect()
    try:
        conn.execute(
            "DELETE FROM topic_pick WHERE topic_id = ? AND snapshot_id = ?", (topic_id, snapshot_id)
        )
    finally:
        conn.close()


def short_cite(conn, snapshot_id: int) -> str:
    r = conn.execute(
        "SELECT s.kind, s.authors_json, s.year, s.awmf_reg_no, s.title, ss.origin "
        "FROM source_snapshot ss JOIN source s ON s.id = ss.source_id WHERE ss.id = ?",
        (snapshot_id,),
    ).fetchone()
    if r["kind"] == "awmf":
        cite = f"AWMF {r['awmf_reg_no']}"
    else:
        authors = json.loads(r["authors_json"] or "[]")
        first = authors[0] if authors else (r["title"] or "?").split()[0]
        cite = f"{first} et al. {r['year']}" if len(authors) > 1 else f"{first} {r['year']}"
    if r["origin"] == "epmc_fulltext":
        cite += " (Volltext)"
    return cite


def lock_corpus(db: Database, topic_id: int) -> int:
    """Freeze the topic's current picks into a corpus; returns corpus id (reused if identical)."""
    conn = db.connect()
    try:
        require_whitelisted(conn, topic_id)
        snaps = conn.execute(
            "SELECT ss.id, ss.sha256 FROM topic_pick tp JOIN source_snapshot ss "
            "ON ss.id = tp.snapshot_id WHERE tp.topic_id = ? ORDER BY tp.picked_at, ss.id",
            (topic_id,),
        ).fetchall()
        n = len(_distinct_sources(conn, topic_id))
        if n < MIN_SOURCES or n > MAX_SOURCES:
            raise StoreError(
                f"corpus needs {MIN_SOURCES}–{MAX_SOURCES} distinct sources, topic has {n}"
            )
        sha = hashlib.sha256("\n".join(s["sha256"] for s in snaps).encode()).hexdigest()
        row = conn.execute(
            "SELECT id FROM corpus WHERE topic_id = ? AND sha256 = ?", (topic_id, sha)
        ).fetchone()
        if row:
            return row["id"]
        conn.execute("BEGIN IMMEDIATE")
        try:
            cid = conn.execute(
                "INSERT INTO corpus (topic_id, sha256) VALUES (?, ?)", (topic_id, sha)
            ).lastrowid
            for pos, s in enumerate(snaps):
                conn.execute(
                    "INSERT INTO corpus_source (corpus_id, position, snapshot_id, short_cite) "
                    "VALUES (?,?,?,?)",
                    (cid, pos, s["id"], short_cite(conn, s["id"])),
                )
            conn.execute("COMMIT")
            return cid
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def latest_corpus(conn, topic_id: int):
    return conn.execute(
        "SELECT * FROM corpus WHERE topic_id = ? ORDER BY id DESC LIMIT 1", (topic_id,)
    ).fetchone()
