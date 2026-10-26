"""Manual AWMF S3 guideline import (SRC-02, D-13): operator-supplied PDF -> page-numbered German
sentences in an immutable snapshot, with register number, version and validity recorded."""

import re
from collections import Counter
from datetime import date

import yaml

from ndc.config import config_dir
from ndc.db import Database
from ndc.sources import store
from ndc.sources.pubmed import SentenceRow, SourceMeta
from ndc.sources.split import split_sentences

STATUSES = ("gueltig", "in_ueberarbeitung", "abgelaufen")
STATUS_DE = {
    "gueltig": "gültig",
    "in_ueberarbeitung": "in Überarbeitung",
    "abgelaufen": "abgelaufen",
}


class AwmfError(Exception):
    pass


def _cfg() -> dict:
    return yaml.safe_load((config_dir() / "retrieval.yaml").read_text(encoding="utf-8"))["awmf"]


def extract_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    import pymupdf  # lazy: heavy import (pulls onnxruntime); never loaded by the review server

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    finally:
        doc.close()


def _norm_line(s: str) -> str:
    return re.sub(r"\d+", "#", s.strip())


def clean_pages(
    pages: list[tuple[int, str]], min_share: float = 0.5
) -> list[tuple[int, list[str]]]:
    """Drop repeated running headers/footers; return (page, lines) with hyphenation still raw."""
    split = [(n, [ln for ln in txt.splitlines() if ln.strip()]) for n, txt in pages]
    edges = Counter()
    for _, lines in split:
        for ln in {*(lines[:1]), *(lines[-1:])}:
            edges[_norm_line(ln)] += 1
    need = max(2, int(len(split) * min_share + 0.999)) if len(split) > 1 else 10**9
    repeated = {k for k, c in edges.items() if c >= need}
    out = []
    for n, lines in split:
        if lines and _norm_line(lines[0]) in repeated:
            lines = lines[1:]
        if lines and _norm_line(lines[-1]) in repeated:
            lines = lines[:-1]
        out.append((n, lines))
    return out


def _join_lines(lines: list[str]) -> str:
    """Join lines; undo end-of-line hyphenation only ("Psycho-|edukation"), keep "ADHS- und"."""
    text = ""
    for part in lines:
        if text.endswith("-") and len(text) > 1 and text[-2].isalpha() and part[:1].islower():
            text = text[:-1] + part
        else:
            text = f"{text} {part}" if text else part
    return text


def page_sentences(pages: list[tuple[int, list[str]]], section_re: str) -> list[SentenceRow]:
    sec_pat = re.compile(section_re)
    rows: list[SentenceRow] = []
    section = None
    for n, lines in pages:
        chunks: list[tuple[str | None, list[str]]] = [(section, [])]
        for ln in (x.strip() for x in lines):
            if sec_pat.match(ln) and len(ln) < 120:
                section = ln
                chunks.append((section, []))
            else:
                chunks[-1][1].append(ln)
        for sec, buf in chunks:
            for s in split_sentences(_join_lines(buf), "de"):
                rows.append(SentenceRow(s, sec or f"Seite {n}", n))
    return rows


def import_awmf(
    db: Database,
    pdf_bytes: bytes,
    *,
    register: str,
    version: str,
    valid_until: str,
    status: str,
    title: str,
    topic_id: int | None = None,
    new_version: bool = False,
) -> int:
    cfg = _cfg()
    if not re.match(cfg["register_pattern"], register or ""):
        raise AwmfError(f"Registernummer {register!r} ungültig (Format NNN-NNN)")
    try:
        date.fromisoformat(valid_until)
    except (TypeError, ValueError) as e:
        raise AwmfError("--valid-until muss ein ISO-Datum sein (YYYY-MM-DD)") from e
    if status not in STATUSES:
        raise AwmfError(f"--status muss einer von {', '.join(STATUSES)} sein")
    if not version.strip() or not title.strip():
        raise AwmfError("--version und --title sind Pflicht")
    if len(pdf_bytes) > int(cfg["max_pdf_bytes"]) or not pdf_bytes.startswith(b"%PDF-"):
        raise AwmfError("keine PDF-Datei oder größer als erlaubt")
    rows = page_sentences(
        clean_pages(extract_pages(pdf_bytes), float(cfg["header_footer_min_share"])),
        cfg["section_pattern"],
    )
    if not rows:
        raise AwmfError("keine Sätze aus dem PDF extrahiert (gescanntes PDF?)")
    meta = SourceMeta(
        kind="awmf",
        title=title.strip(),
        awmf_reg_no=register,
        awmf_version=version.strip(),
        awmf_valid_until=valid_until,
        awmf_status=status,
        language="de",
    )
    sha = store.snapshot_sha256(rows)
    conn = db.connect()
    try:
        same = conn.execute("SELECT id FROM source_snapshot WHERE sha256 = ?", (sha,)).fetchone()
        clash = conn.execute(
            "SELECT ss.id FROM source s JOIN source_snapshot ss ON ss.source_id = s.id "
            "WHERE s.awmf_reg_no = ? AND s.awmf_version = ?",
            (register, meta.awmf_version),
        ).fetchone()
    finally:
        conn.close()
    if same is None and clash is not None and not new_version:
        raise AwmfError(
            "andere PDF mit gleicher Register-Nr. und Version vorhanden — "
            "--new-version angeben, falls beabsichtigt"
        )
    snap = store.store_snapshot(db, meta, rows, "awmf_pdf", pdf_bytes, raw_ext="pdf")
    if topic_id is not None:
        store.pick(db, topic_id, snap)
    return snap


def expired(status: str | None, valid_until: str | None, today: str | None = None) -> bool:
    today = today or date.today().isoformat()
    return status == "abgelaufen" or bool(valid_until and valid_until < today)


def awmf_gate_issues(conn, version_id: int) -> list:
    """Expired guidelines BLOCK (D-13 amended 2026-10-26); 'in Überarbeitung' only warns."""
    from ndc.review.gate import Issue

    out = []
    for s in conn.execute(
        "SELECT DISTINCT s.awmf_reg_no, s.awmf_status, s.awmf_valid_until FROM script_sentence ss "
        "JOIN script_citation sc ON sc.script_sentence_id = ss.id "
        "JOIN source_sentence src ON src.id = sc.source_sentence_id "
        "JOIN source_snapshot snap ON snap.id = src.snapshot_id "
        "JOIN source s ON s.id = snap.source_id "
        "WHERE ss.script_version_id = ? AND s.kind = 'awmf'",
        (version_id,),
    ):
        if expired(s["awmf_status"], s["awmf_valid_until"]):
            out.append(Issue("block_awmf_expired", None,
                             f"AWMF-Leitlinie {s['awmf_reg_no']} abgelaufen (gültig bis "
                             f"{s['awmf_valid_until']}) — nicht zitierbar"))
        elif s["awmf_status"] == "in_ueberarbeitung":
            out.append(Issue("warn_awmf", None,
                             f"AWMF-Leitlinie {s['awmf_reg_no']} in Überarbeitung"))
    return out


def corpus_expired_check(db: Database, corpus_id: int) -> None:
    """PRE_DRAFT_HOOK: refuse to spend an LLM call on a corpus with an expired guideline."""
    conn = db.connect()
    try:
        bad = [
            r["awmf_reg_no"]
            for r in conn.execute(
                "SELECT s.awmf_reg_no, s.awmf_status, s.awmf_valid_until FROM corpus_source cs "
                "JOIN source_snapshot ss ON ss.id = cs.snapshot_id "
                "JOIN source s ON s.id = ss.source_id WHERE cs.corpus_id = ? AND s.kind = 'awmf'",
                (corpus_id,),
            )
            if expired(r["awmf_status"], r["awmf_valid_until"])
        ]
    finally:
        conn.close()
    if bad:
        raise AwmfError(
            f"Korpus enthält abgelaufene AWMF-Leitlinie(n) {', '.join(bad)} — "
            "ndc source unpick und neu sperren (D-13)"
        )
