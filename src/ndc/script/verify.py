"""Adversarial verification (SCR-02, D-03, D-06, D-14, D-15).

A different model than the drafter, structured output, sees only script sentences + cited stored
sentences (+/- one neighbour as context). Blockers are forced in code, never left to the model.
Verification never rewrites the script (D-03): suggested fixes are stored as text only.
"""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ndc import llm
from ndc.config import db_path
from ndc.db import Database


class VerifyError(Exception):
    pass


class VerifyIncomplete(VerifyError):
    pass


class SentenceVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    kind: Literal["empirical", "hedged_generalization", "advice", "framing"]
    verdict: Literal[
        "supports", "partial", "overstated", "unsupported", "contradicts", "not_applicable"
    ]
    certainty_escalation: bool
    hidden_claim: bool
    note_de: str
    suggested_fix_de: str | None


class VerifyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdicts: list[SentenceVerdict]


def reuse_key(text: str, cited_ids, prompt_sha: str, model: str) -> str:
    blob = json.dumps(
        {"t": text, "c": sorted(int(i) for i in cited_ids), "p": prompt_sha, "m": model},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _sentences(conn, version_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, ordinal, text FROM script_sentence WHERE script_version_id = ? ORDER BY ordinal",
        (version_id,),
    ).fetchall()
    if not rows:
        raise VerifyError(f"script version {version_id} has no sentences")
    corpus_id = conn.execute(
        "SELECT s.corpus_id FROM script_version v JOIN script s ON s.id = v.script_id "
        "WHERE v.id = ?",
        (version_id,),
    ).fetchone()[0]
    out = []
    for r in rows:
        cited = []
        for c in conn.execute(
            "SELECT ss.id, ss.snapshot_id, ss.ordinal, ss.section, ss.page, ss.text, cs.short_cite "
            "FROM script_citation sc JOIN source_sentence ss ON ss.id = sc.source_sentence_id "
            "JOIN corpus_source cs ON cs.snapshot_id = ss.snapshot_id AND cs.corpus_id = ? "
            "WHERE sc.script_sentence_id = ? ORDER BY ss.snapshot_id, ss.ordinal",
            (corpus_id, r["id"]),
        ):
            ctx = {
                n["ordinal"]: n["text"]
                for n in conn.execute(
                    "SELECT ordinal, text FROM source_sentence WHERE snapshot_id = ? "
                    "AND ordinal IN (?, ?)",
                    (c["snapshot_id"], c["ordinal"] - 1, c["ordinal"] + 1),
                )
            }
            cited.append(
                {
                    "id": c["id"],
                    "quelle": c["short_cite"],
                    "abschnitt": c["section"],
                    "seite": c["page"],
                    "satz": c["text"],
                    "kontext_davor": ctx.get(c["ordinal"] - 1),
                    "kontext_danach": ctx.get(c["ordinal"] + 1),
                }
            )
        out.append({"row_id": r["id"], "ordinal": r["ordinal"], "text": r["text"], "cited": cited})
    return out


def build_verify_request(sentences: list[dict], stage: llm.StageConfig, system: str) -> dict:
    payload = {
        "skript": [
            {"ordinal": s["ordinal"], "satz": s["text"], "zitierte_quellsaetze": s["cited"]}
            for s in sentences
        ]
    }
    return {
        "model": stage.model,
        "max_tokens": stage.max_tokens,
        "output_config": {"effort": stage.effort},
        "system": system,
        "messages": [
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}
        ],
    }


def force(v: SentenceVerdict, cited: bool) -> tuple[str, str | None]:
    """Final verdict + forced_reason. Code, not the model, decides blockers."""
    if v.hidden_claim:
        return "unsupported", "hidden_claim"
    if v.kind == "framing":
        return "not_applicable", None
    if not cited:
        return "unsupported", "uncited"
    if v.verdict == "not_applicable":
        return "unsupported", "not_applicable_on_claim"
    return v.verdict, None


def verify(
    db: Database | None = None,
    version_id: int = 0,
    *,
    only_ordinals: set[int] | None = None,
    client=None,
    config: llm.LlmConfig | None = None,
) -> int | None:
    """Verify a version; returns llm_run id, or None if already fully verified."""
    db = db or Database(db_path())
    cfg = config or llm.load_llm_config()
    conn = db.connect()
    try:
        v = conn.execute("SELECT * FROM script_version WHERE id = ?", (version_id,)).fetchone()
        if v is None:
            raise VerifyError(f"script version {version_id} not found")
        sents = _sentences(conn, version_id)
        done = {
            r[0]
            for r in conn.execute(
                "SELECT ss.ordinal FROM claim_verdict cv JOIN script_sentence ss "
                "ON ss.id = cv.script_sentence_id WHERE ss.script_version_id = ?",
                (version_id,),
            )
        }
    finally:
        conn.close()
    todo = [s for s in sents if s["ordinal"] not in done]
    if only_ordinals is not None:
        todo = [s for s in todo if s["ordinal"] in only_ordinals]
    if not todo:
        return None
    system, prompt_sha = llm.load_prompt(cfg.verify)
    request = build_verify_request(todo, cfg.verify, system)
    msg, run_id = llm.call(
        "verify",
        request,
        prompt_sha=prompt_sha,
        input_shas=[v["sha256"]],
        subject=("script_version", version_id),
        client=client,
        parse_model=VerifyReport,
        db=db,
        config=cfg,
    )
    report: VerifyReport | None = getattr(msg, "parsed_output", None)
    if report is None:
        raise VerifyIncomplete(f"llm_run {run_id}: no parsed output")
    by_ord = {x.ordinal: x for x in report.verdicts}
    missing = [s["ordinal"] for s in todo if s["ordinal"] not in by_ord]
    if missing:
        raise VerifyIncomplete(f"llm_run {run_id}: verifier skipped sentences {missing}")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for s in todo:
                x = by_ord[s["ordinal"]]
                final, reason = force(x, bool(s["cited"]))
                conn.execute(
                    "INSERT INTO claim_verdict (script_sentence_id, llm_run_id, verdict, kind, "
                    "certainty_escalation, hidden_claim, forced_reason, model_verdict, note_de, "
                    "suggested_fix_de, reuse_key) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        s["row_id"],
                        run_id,
                        final,
                        x.kind,
                        int(x.certainty_escalation),
                        int(x.hidden_claim),
                        reason,
                        x.verdict,
                        x.note_de,
                        x.suggested_fix_de,
                        reuse_key(
                            s["text"], [c["id"] for c in s["cited"]], prompt_sha, cfg.verify.model
                        ),
                    ),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return run_id


def verdict_counts(conn, version_id: int) -> dict[str, int]:
    return {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT cv.verdict, count(*) FROM claim_verdict cv JOIN script_sentence ss "
            "ON ss.id = cv.script_sentence_id WHERE ss.script_version_id = ? GROUP BY cv.verdict",
            (version_id,),
        )
    }
