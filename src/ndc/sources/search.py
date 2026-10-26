"""Ranked candidate search over PubMed (+ Europe PMC OA status) — SRC-01, D-09..D-12."""

import json
import logging
from dataclasses import dataclass, field

import yaml

from ndc import artifacts
from ndc.checks.engine import check
from ndc.config import config_dir
from ndc.db import Database
from ndc.sources import europepmc, pubmed

log = logging.getLogger(__name__)


class SearchError(Exception):
    pass


@dataclass
class Candidate:
    pmid: str
    title: str
    year: int | None
    pubtypes: list[str]
    doi: str | None
    pmcid: str | None
    pubmed_pos: int
    is_oa: bool | None = None
    tier: str = "primary"
    score: float = 0.0
    safety_flag: str | None = None
    meta: dict = field(default_factory=dict)


def load_cfg() -> dict:
    return yaml.safe_load((config_dir() / "retrieval.yaml").read_text(encoding="utf-8"))


def _or(terms: list[str]) -> str:
    quoted = [f'"{t}"[tiab]' if " " in t else f"{t}[tiab]" for t in terms]
    return "(" + " OR ".join(quoted) + ")"


def topic_query(topic, cfg: dict) -> str:
    parts = []
    mesh = cfg["mesh"].get(topic["condition"])
    if mesh:
        parts.append(mesh)
    else:
        log.warning("no MeSH mapping for condition %s", topic["condition"])
    dom = cfg["domain_terms"].get(topic["domain"])
    if dom:
        parts.append(_or(dom))
    aud = (cfg.get("audience_terms") or {}).get(topic["audience"])
    if aud:
        parts.append(_or(aud))
    if not parts:
        raise SearchError(f"cannot build a query for topic {topic['id']}; pass --query")
    return " AND ".join(parts)


def build_query(topic, cfg: dict, query: str | None = None) -> str:
    """Topic part (or operator override) + the exclusions, which are always appended."""
    base = query.strip() if query else topic_query(topic, cfg)
    return f"({base}) {cfg['exclusions']}"


def _tier(pubtypes: list[str], cfg: dict) -> tuple[str, float]:
    for t in cfg["tier_weights"]:
        if any(m in pubtypes for m in t["match"]):
            return t["label"], float(t["weight"])
    return "primary", 0.0


def rank(cands: list[Candidate], cfg: dict) -> list[Candidate]:
    for c in cands:
        c.tier, w = _tier(c.pubtypes, cfg)
        bonus = cfg["relevance_bonus"] if c.pubmed_pos < cfg["relevance_top_n"] else 0.0
        c.score = w + bonus + (cfg["oa_bonus"] if c.is_oa else 0.0)
    return sorted(cands, key=lambda c: (-c.score, c.pubmed_pos))


def _from_summary(pmid: str, s: dict, pos: int) -> Candidate:
    ids = {a.get("idtype"): a.get("value") for a in s.get("articleids", [])}
    year = s.get("pubdate", "")[:4]
    return Candidate(
        pmid=pmid,
        title=s.get("title", "").strip(),
        year=int(year) if year.isdigit() else None,
        pubtypes=list(s.get("pubtype", [])),
        doi=(ids.get("doi") or "").lower() or None,
        pmcid=ids.get("pmc") or ids.get("pmcid") or None,
        pubmed_pos=pos,
        meta={
            "source": s.get("fulljournalname") or s.get("source"),
            "authors": [a.get("name") for a in s.get("authors", [])][:6],
        },
    )


def search(db: Database, topic_id: int, query: str | None = None) -> int:
    cfg = load_cfg()
    conn = db.connect()
    try:
        topic = conn.execute("SELECT * FROM topic WHERE id = ?", (topic_id,)).fetchone()
    finally:
        conn.close()
    if topic is None or topic["list_tag"] != "whitelist":
        raise SearchError(f"topic {topic_id} not found or not whitelisted")
    q = build_query(topic, cfg, query)
    ev = pubmed.esearch(f"{q} AND {cfg['evidence_filter']}", cfg["retmax_evidence"])
    prim = pubmed.esearch(q, cfg["retmax_primary"])
    order: list[str] = []
    for pmid in ev + prim:
        if pmid not in order:
            order.append(pmid)
    if not order:
        raise SearchError(f"no PubMed results for: {q}")
    summ = pubmed.esummary(order)
    raw = [artifacts.put(json.dumps(summ, sort_keys=True).encode(), "json")]
    cands = [
        _from_summary(p, summ[p], i)
        for i, p in enumerate(order)
        if p in summ and "error" not in summ[p]
    ]
    try:
        oa = europepmc.oa_status([c.pmid for c in cands])
        for c in cands:
            info = oa.get(c.pmid)
            c.is_oa = bool(info and info["is_oa"])
            c.pmcid = c.pmcid or (info or {}).get("pmcid")
    except Exception as e:  # degrade: OA unknown, search still succeeds
        log.warning("Europe PMC OA lookup failed (%s) — OA status unknown", type(e).__name__)
    for c in cands:  # only blacklisted-subject (safety) hits flag a candidate, not terminology
        hits = [f for f in check(c.title, "en", "topic").findings if f.source_file == "safety"]
        flags = {f.rule_id for f in hits}
        low = c.title.lower()
        flags |= {f"title:{w}" for w in cfg.get("title_flag_terms") or [] if w in low}
        c.safety_flag = ",".join(sorted(flags)) or None
    ranked = rank(cands, cfg)
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            run_id = conn.execute(
                "INSERT INTO search_run (topic_id, query, raw_artifacts_json) VALUES (?,?,?)",
                (topic_id, q, json.dumps(raw)),
            ).lastrowid
            for i, c in enumerate(ranked, start=1):
                conn.execute(
                    "INSERT INTO source_candidate (search_run_id, rank, score, pmid, doi, pmcid, "
                    "title, year, tier, pubtypes_json, is_oa, safety_flag, meta_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        i,
                        c.score,
                        c.pmid,
                        c.doi,
                        c.pmcid,
                        c.title,
                        c.year,
                        c.tier,
                        json.dumps(c.pubtypes),
                        None if c.is_oa is None else int(c.is_oa),
                        c.safety_flag,
                        json.dumps(c.meta, ensure_ascii=False),
                    ),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return run_id


def latest_run(conn, topic_id: int):
    return conn.execute(
        "SELECT * FROM search_run WHERE topic_id = ? ORDER BY id DESC LIMIT 1", (topic_id,)
    ).fetchone()
