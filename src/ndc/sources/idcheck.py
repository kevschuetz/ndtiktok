"""Mechanical identifier verification (SRC-04): PMID via PubMed esummary, DOI via Crossref.
Never LLM-judged. ok = title similarity >= 0.90 AND year within +/-1 (AND PubMed's DOI equals the
stored DOI when both exist). Network failures are 'error' and fail closed."""

import os
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ndc.db import Database
from ndc.sources import pubmed
from ndc.sources.pubmed import _RateLimiter, _retryable

CROSSREF = "https://api.crossref.org/works"
RECHECK_DAYS = 30
OK_STATES = ("ok", "manual")
_LIMITER = _RateLimiter()
_client: httpx.Client | None = None


class IdCheckFailed(Exception):
    pass


def set_client(client: httpx.Client | None) -> None:
    global _client
    _client = client


def _http() -> httpx.Client:
    global _client
    if _client is None:
        email = os.environ.get("NCBI_EMAIL") or "ndc@localhost"
        _client = httpx.Client(timeout=20.0, headers={"User-Agent": f"ndc/0.1 (mailto:{email})"})
    return _client


@retry(retry=retry_if_exception(_retryable), stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=0.5, max=8), reraise=True)
def _crossref(doi: str) -> httpx.Response:
    _LIMITER.wait(0.25)
    r = _http().get(f"{CROSSREF}/{doi}")
    if r.status_code == 404:
        return r
    r.raise_for_status()
    return r


def norm_title(t: str | None) -> str:
    t = unicodedata.normalize("NFC", t or "").casefold().strip().rstrip(".")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def titles_match(a: str | None, b: str | None) -> bool:
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio() >= 0.90


def _year_ok(stored, fetched) -> bool:
    return stored is None or fetched is None or abs(int(stored) - int(fetched)) <= 1


def _check_pmid(src) -> tuple[str, str | None, int | None, str]:
    try:
        s = pubmed.esummary([src["pmid"]]).get(src["pmid"], {})
    except Exception as e:  # network/5xx -> fail closed
        return "error", None, None, type(e).__name__
    if not s or "error" in s:
        return "unresolvable", None, None, "PubMed: not found"
    title, year = s.get("title"), s.get("pubdate", "")[:4]
    year = int(year) if year.isdigit() else None
    pm_doi = next((a.get("value", "").lower() for a in s.get("articleids", [])
                   if a.get("idtype") == "doi"), None)
    if src["doi"] and pm_doi and pm_doi != src["doi"].lower():
        return "mismatch", title, year, f"doi differs: PubMed {pm_doi}"
    if not titles_match(src["title"], title):
        return "mismatch", title, year, "title differs"
    if not _year_ok(src["year"], year):
        return "mismatch", title, year, "year differs"
    return "ok", title, year, ""


def _check_doi(src) -> tuple[str, str | None, int | None, str]:
    try:
        r = _crossref(src["doi"])
    except Exception as e:
        return "error", None, None, type(e).__name__
    if r.status_code == 404:
        return "unresolvable", None, None, "Crossref: 404"
    m = r.json().get("message", {})
    title = (m.get("title") or [None])[0]
    parts = (m.get("issued") or {}).get("date-parts") or [[None]]
    year = parts[0][0] if parts and parts[0] else None
    if not titles_match(src["title"], title):
        return "mismatch", title, year, "title differs"
    if not _year_ok(src["year"], year):
        return "mismatch", title, year, "year differs"
    return "ok", title, year, ""


def check_source(db: Database, source_id: int) -> str:
    """Run all applicable checks; store one row per identifier; return the worst status."""
    conn = db.connect()
    try:
        src = conn.execute("SELECT * FROM source WHERE id = ?", (source_id,)).fetchone()
    finally:
        conn.close()
    if src is None:
        raise IdCheckFailed(f"source {source_id} not found")
    results = []
    if src["kind"] == "awmf":
        results.append(("awmf", src["awmf_reg_no"], ("manual", None, None, "no registry API")))
    else:
        if src["pmid"]:
            results.append(("pmid", src["pmid"], _check_pmid(src)))
        if src["doi"]:
            results.append(("doi", src["doi"], _check_doi(src)))
        if not results:
            results.append(("pmid", None, ("unresolvable", None, None, "no identifier")))
    conn = db.connect()
    try:
        for kind, ident, (status, title, year, detail) in results:
            conn.execute(
                "INSERT INTO id_check (source_id, identifier_kind, identifier, status, "
                "fetched_title, fetched_year, detail) VALUES (?,?,?,?,?,?,?)",
                (source_id, kind, ident, status, title, year, detail),
            )
    finally:
        conn.close()
    return worst([r[2][0] for r in results])


_RANK = {"ok": 0, "manual": 0, "error": 1, "mismatch": 2, "unresolvable": 3}


def worst(statuses: list[str]) -> str:
    return max(statuses, key=lambda s: _RANK[s]) if statuses else "unresolvable"


def latest_status(conn, source_id: int) -> tuple[str | None, str | None]:
    """Worst status over each identifier's latest row, and the newest checked_at."""
    rows = conn.execute(
        "SELECT identifier_kind, status, checked_at FROM id_check WHERE id IN "
        "(SELECT max(id) FROM id_check WHERE source_id = ? GROUP BY identifier_kind)",
        (source_id,),
    ).fetchall()
    if not rows:
        return None, None
    return worst([r["status"] for r in rows]), min(r["checked_at"] for r in rows)


def ensure_corpus_ok(db: Database, corpus_id: int) -> None:
    """PRE_DRAFT_HOOK: re-check stale/failed sources; raise naming every failing one."""
    conn = db.connect()
    try:
        srcs = conn.execute(
            "SELECT DISTINCT s.id, cs.short_cite FROM corpus_source cs JOIN source_snapshot ss "
            "ON ss.id = cs.snapshot_id JOIN source s ON s.id = ss.source_id WHERE cs.corpus_id = ?",
            (corpus_id,),
        ).fetchall()
        state = {s["id"]: latest_status(conn, s["id"]) for s in srcs}
    finally:
        conn.close()
    cutoff = (datetime.now(UTC) - timedelta(days=RECHECK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bad = []
    for s in srcs:
        status, checked = state[s["id"]]
        if status not in OK_STATES or checked is None or checked < cutoff:
            status = check_source(db, s["id"])
        if status not in OK_STATES:
            bad.append(f"{s['short_cite']} ({status})")
    if bad:
        raise IdCheckFailed("Quelle nicht verifizierbar: " + "; ".join(bad))


def idcheck_gate_issues(conn, version_id: int) -> list:
    from ndc.review.gate import Issue

    out = []
    for s in conn.execute(
        "SELECT DISTINCT s.id, s.title, s.pmid, s.doi FROM script_sentence ss "
        "JOIN script_citation sc ON sc.script_sentence_id = ss.id "
        "JOIN source_sentence src ON src.id = sc.source_sentence_id "
        "JOIN source_snapshot snap ON snap.id = src.snapshot_id "
        "JOIN source s ON s.id = snap.source_id WHERE ss.script_version_id = ?",
        (version_id,),
    ):
        status, _ = latest_status(conn, s["id"])
        if status not in OK_STATES:
            ident = s["pmid"] or s["doi"] or s["id"]
            out.append(Issue("block_idcheck", None,
                             f"Quelle nicht verifizierbar: {ident} ({status or 'ungeprüft'})"))
    return out


def summary(conn, topic_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT DISTINCT s.id, s.pmid, s.doi, s.awmf_reg_no, s.title FROM topic_pick tp "
        "JOIN source_snapshot ss ON ss.id = tp.snapshot_id JOIN source s ON s.id = ss.source_id "
        "WHERE tp.topic_id = ?",
        (topic_id,),
    ).fetchall()
    out = []
    for r in rows:
        st, at = latest_status(conn, r["id"])
        out.append({"id": r["id"], "ident": r["pmid"] or r["doi"] or r["awmf_reg_no"],
                    "title": r["title"], "status": st, "checked_at": at})
    return out

