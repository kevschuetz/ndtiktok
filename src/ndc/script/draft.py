"""Grounded draft (SCR-01): Citations over custom-content documents built from stored sentences.

One corpus source = one document; one content block = one stored sentence, so a citation's
block index IS the sentence ordinal. end_block_index is exclusive (verified live 2026-10-26).
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field

from ndc import llm
from ndc.checks.engine import check
from ndc.config import db_path
from ndc.db import Database
from ndc.sources.split import normalize, split_sentences
from ndc.sources.store import latest_corpus


class DraftError(Exception):
    pass


class CitationMismatch(DraftError):
    pass


@dataclass
class CorpusDoc:
    position: int
    snapshot_id: int
    short_cite: str
    sentences: list[tuple[int, int, str]]  # (source_sentence.id, ordinal, text)


@dataclass
class DraftSentence:
    ordinal: int
    text: str
    char_start: int
    char_end: int
    cited: set[int] = field(default_factory=set)  # source_sentence ids


def load_corpus(conn, corpus_id: int) -> list[CorpusDoc]:
    docs = []
    for cs in conn.execute(
        "SELECT position, snapshot_id, short_cite FROM corpus_source WHERE corpus_id = ? "
        "ORDER BY position",
        (corpus_id,),
    ):
        sents = [
            (r["id"], r["ordinal"], r["text"])
            for r in conn.execute(
                "SELECT id, ordinal, text FROM source_sentence WHERE snapshot_id = ? "
                "ORDER BY ordinal",
                (cs["snapshot_id"],),
            )
        ]
        docs.append(CorpusDoc(cs["position"], cs["snapshot_id"], cs["short_cite"], sents))
    return docs


def topic_text(topic) -> str:
    parts = [f"Thema: {topic['working_title']}"]
    if topic["summary"]:
        parts.append(f"Worum es geht: {topic['summary']}")
    parts.append("Sprache: Deutsch (österreichisches Standarddeutsch). Schreib jetzt das Skript.")
    return "\n".join(parts)


def build_draft_request(docs: list[CorpusDoc], topic, stage: llm.StageConfig, system: str) -> dict:
    content = []
    for i, d in enumerate(docs):
        block = {
            "type": "document",
            "source": {
                "type": "content",
                "content": [{"type": "text", "text": t} for _, _, t in d.sentences],
            },
            "title": d.short_cite,
            "citations": {"enabled": True},
        }
        if i == len(docs) - 1:
            block["cache_control"] = {"type": "ephemeral"}
        content.append(block)
    content.append({"type": "text", "text": topic_text(topic)})
    return {
        "model": stage.model,
        "max_tokens": stage.max_tokens,
        "output_config": {"effort": stage.effort},
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }


def _blocks(message) -> list[dict]:
    data = message.model_dump(mode="json") if hasattr(message, "model_dump") else message
    return [b for b in data.get("content", []) if b.get("type") == "text"]


_MD = re.compile(r"(^\s*(#|\*\*|- |\* |\d+\.\s))|\*\*", re.M)


def has_markdown(text: str) -> bool:
    return bool(_MD.search(text))


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


def map_citations(message, docs: list[CorpusDoc]) -> tuple[str, list[DraftSentence]]:
    """Script text (normalized) and its sentences with resolved source_sentence ids."""
    blocks = _blocks(message)
    raw = "".join(b.get("text", "") for b in blocks)
    text = normalize(raw)
    cited_spans: list[tuple[int, int, set[int]]] = []
    cursor = 0
    for b in blocks:
        cits = b.get("citations") or []
        bt = normalize(b.get("text", ""))
        if not bt:
            continue
        pos = text.find(bt, cursor)
        if pos < 0:
            raise DraftError("could not locate a response block in the script text")
        cursor = pos + len(bt)
        if not cits:
            continue
        ids: set[int] = set()
        for c in cits:
            if c.get("type") != "content_block_location":
                raise CitationMismatch(f"unexpected citation type {c.get('type')!r}")
            di = c["document_index"]
            if di < 0 or di >= len(docs):
                raise CitationMismatch(f"document_index {di} out of range")
            doc = docs[di]
            start, end = c["start_block_index"], c["end_block_index"]  # end exclusive
            if not (0 <= start < end <= len(doc.sentences)):
                raise CitationMismatch(
                    f"block range {start}..{end} out of range for {doc.short_cite}"
                )
            chosen = doc.sentences[start:end]
            stored = _ws(" ".join(t for _, _, t in chosen))
            stored_nospace = _ws("".join(t for _, _, t in chosen))
            got = _ws(c.get("cited_text", ""))
            if got not in (stored, stored_nospace):
                raise CitationMismatch(
                    f"cited_text does not match stored sentences {start}..{end} of {doc.short_cite}"
                )
            ids.update(sid for sid, _, _ in chosen)
        cited_spans.append((pos, pos + len(bt), ids))

    sentences: list[DraftSentence] = []
    scur = 0
    for i, s in enumerate(split_sentences(text, "de")):
        p = text.find(s, scur)
        if p < 0:
            raise DraftError("sentence split out of sync with script text")
        scur = p + len(s)
        ds = DraftSentence(i, s, p, p + len(s))
        for a, b, ids in cited_spans:
            if a < ds.char_end and b > ds.char_start:
                ds.cited.update(ids)
        sentences.append(ds)
    if not sentences:
        raise DraftError("empty script")
    return text, sentences


def _finding_dict(f) -> dict:
    return {
        "rule_id": f.rule_id,
        "tier": f.tier,
        "category": f.category,
        "span": list(f.span),
        "matched_text": f.matched_text,
        "message": f.message,
        "suggest": f.suggest,
    }


def run_mechanical_checks(db: Database, text: str, sentences) -> tuple[str, str, int]:
    """Script- and claim-level terminology/safety checks -> (status, check_json, word_count)."""
    order = {"ok": 0, "needs_override": 1, "blocked": 2}
    script_res = check(text, "de", "script", db)
    status = script_res.status
    per = []
    for s in sentences:
        r = check(s.text, "de", "claim", db)
        if order[r.status] > order[status]:
            status = r.status
        if r.findings:
            per.append(
                {
                    "ordinal": s.ordinal,
                    "status": r.status,
                    "findings": [_finding_dict(f) for f in r.findings],
                }
            )
    payload = {
        "script": {
            "status": script_res.status,
            "findings": [_finding_dict(f) for f in script_res.findings],
            "overridden": script_res.overridden_rule_ids,
        },
        "sentences": per,
        "terminology_version": script_res.terminology_version,
    }
    return status, json.dumps(payload, ensure_ascii=False), len(text.split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(unicodedata.normalize("NFC", text).encode("utf-8")).hexdigest()


def store_version(
    conn,
    *,
    script_id: int,
    parent_id: int | None,
    version_no: int,
    text: str,
    sentences,
    origin: str,
    llm_run_id: int | None,
    check_status: str,
    check_json: str,
    word_count: int,
) -> int:
    vid = conn.execute(
        "INSERT INTO script_version (script_id, parent_version_id, version_no, text, sha256, "
        "word_count, origin, llm_run_id, check_status, check_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            script_id,
            parent_id,
            version_no,
            text,
            sha256_text(text),
            word_count,
            origin,
            llm_run_id,
            check_status,
            check_json,
        ),
    ).lastrowid
    for s in sentences:
        sid = conn.execute(
            "INSERT INTO script_sentence (script_version_id, ordinal, text, char_start, char_end, "
            "sha256) VALUES (?,?,?,?,?,?)",
            (vid, s.ordinal, s.text, s.char_start, s.char_end, sha256_text(s.text)),
        ).lastrowid
        for src in sorted(s.cited):
            conn.execute(
                "INSERT INTO script_citation (script_sentence_id, source_sentence_id) VALUES (?,?)",
                (sid, src),
            )
    return vid


def draft(
    db: Database | None = None,
    topic_id: int = 0,
    *,
    client=None,
    config: llm.LlmConfig | None = None,
) -> int:
    """Draft a new script for the topic's latest locked corpus; returns script_version id."""
    db = db or Database(db_path())
    cfg = config or llm.load_llm_config()
    conn = db.connect()
    try:
        topic = conn.execute("SELECT * FROM topic WHERE id = ?", (topic_id,)).fetchone()
        if topic is None or topic["list_tag"] != "whitelist":
            raise DraftError(f"topic {topic_id} not found or not whitelisted")
        corpus = latest_corpus(conn, topic_id)
        if corpus is None:
            raise DraftError(f"topic {topic_id} has no locked corpus (ndc corpus lock {topic_id})")
        docs = load_corpus(conn, corpus["id"])
        snap_shas = [
            r[0]
            for r in conn.execute(
                "SELECT ss.sha256 FROM corpus_source cs "
                "JOIN source_snapshot ss ON ss.id = cs.snapshot_id "
                "WHERE cs.corpus_id = ? ORDER BY cs.position",
                (corpus["id"],),
            )
        ]
    finally:
        conn.close()
    _pre_draft_hooks(db, corpus["id"])
    system, prompt_sha = llm.load_prompt(cfg.draft)
    request = build_draft_request(docs, topic, cfg.draft, system)
    message, run_id = llm.call(
        "draft",
        request,
        prompt_sha=prompt_sha,
        input_shas=[corpus["sha256"], *snap_shas],
        subject=("topic", topic_id),
        client=client,
        db=db,
        config=cfg,
    )
    text, sentences = map_citations(message, docs)
    if has_markdown("".join(blk.get("text", "") for blk in _blocks(message))):
        raise DraftError(f"llm_run {run_id}: response contains Markdown — not stored, redraft")
    status, check_json, words = run_mechanical_checks(db, text, sentences)
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            script_id = conn.execute(
                "INSERT INTO script (topic_id, corpus_id) VALUES (?, ?)", (topic_id, corpus["id"])
            ).lastrowid
            vid = store_version(
                conn,
                script_id=script_id,
                parent_id=None,
                version_no=1,
                text=text,
                sentences=sentences,
                origin="draft",
                llm_run_id=run_id,
                check_status=status,
                check_json=check_json,
                word_count=words,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return vid


# Hooks run before any LLM spend (plan 07 adds the identifier check here).
PRE_DRAFT_HOOKS: list = []


def _pre_draft_hooks(db: Database, corpus_id: int) -> None:
    for hook in PRE_DRAFT_HOOKS:
        hook(db, corpus_id)
