"""Edit flow (D-16): export with citation markers -> operator edits -> import as a NEW version.

The parent version and its verdicts/acks/approvals are never touched; the new version has its
own sha, so no approval carries over. Unchanged sentences (same text, same cited sentences, same
verify prompt+model) reuse their verdict; only changed ones go to the verifier.
"""

import re
from dataclasses import dataclass, field

from ndc import llm
from ndc.config import db_path
from ndc.db import Database
from ndc.review.gate import is_latest
from ndc.script.draft import DraftSentence, has_markdown, run_mechanical_checks, store_version
from ndc.script.verify import reuse_key, verify
from ndc.sources.split import normalize, split_sentences

_HEADER = re.compile(r"^#\s*ndc-script\s+parent=([0-9a-f]{64})\b")
_MARKER = re.compile(r"\s*⟦([^⟧]*)⟧\s*$")
_REF = re.compile(r"^\d+:\d+$")


class EditError(Exception):
    pass


@dataclass
class ImportedLine:
    text: str
    refs: list[tuple[int, int]] = field(default_factory=list)  # (snapshot_id, ordinal)


@dataclass
class ImportedScript:
    parent_sha: str
    lines: list[ImportedLine]


def export(db: Database, sha: str) -> str:
    conn = db.connect()
    try:
        v = conn.execute("SELECT * FROM script_version WHERE sha256 = ?", (sha,)).fetchone()
        if v is None:
            raise EditError("Version nicht gefunden")
        topic_id = conn.execute(
            "SELECT topic_id FROM script WHERE id = ?", (v["script_id"],)
        ).fetchone()[0]
        out = [
            f"# ndc-script parent={sha} topic={topic_id}",
            "# Eine Zeile pro Satz. Marker ⟦snapshot:satz,…⟧ am Zeilenende = Quellen des Satzes.",
            "# Zeilen mit # werden ignoriert. Danach: ndc script import <datei>",
        ]
        for s in conn.execute(
            "SELECT id, text FROM script_sentence WHERE script_version_id = ? ORDER BY ordinal",
            (v["id"],),
        ):
            refs = [
                f"{r['snapshot_id']}:{r['ordinal']}"
                for r in conn.execute(
                    "SELECT src.snapshot_id, src.ordinal FROM script_citation sc "
                    "JOIN source_sentence src "
                    "ON src.id = sc.source_sentence_id WHERE sc.script_sentence_id = ? "
                    "ORDER BY src.snapshot_id, src.ordinal",
                    (s["id"],),
                )
            ]
            out.append(s["text"] + (f" ⟦{','.join(refs)}⟧" if refs else ""))
        return "\n".join(out) + "\n"
    finally:
        conn.close()


def parse_import(text: str) -> ImportedScript:
    lines = text.splitlines()
    parent = None
    for ln in lines:
        m = _HEADER.match(ln.strip())
        if m:
            parent = m.group(1)
            break
    if parent is None:
        raise EditError("Kopfzeile '# ndc-script parent=<sha>' fehlt")
    out: list[ImportedLine] = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        refs: list[tuple[int, int]] = []
        m = _MARKER.search(s)
        if m:
            s = s[: m.start()].rstrip()
            for part in [p.strip() for p in m.group(1).split(",") if p.strip()]:
                if not _REF.match(part):
                    raise EditError(f"ungültiger Marker {part!r}")
                a, b = part.split(":")
                refs.append((int(a), int(b)))
        elif "⟦" in s or "⟧" in s:
            raise EditError(f"Marker nicht am Zeilenende: {s[:60]!r}")
        out.append(ImportedLine(s, refs))
    if not out:
        raise EditError("keine Sätze gefunden")
    return ImportedScript(parent, out)


def import_edit(
    db: Database | None = None, text: str = "", *, client=None, config: llm.LlmConfig | None = None
) -> dict:
    """Create the new version; returns {version_id, sha256, reused, reverified}."""
    db = db or Database(db_path())
    cfg = config or llm.load_llm_config()
    imp = parse_import(text)
    conn = db.connect()
    try:
        parent = conn.execute(
            "SELECT * FROM script_version WHERE sha256 = ?", (imp.parent_sha,)
        ).fetchone()
        if parent is None:
            raise EditError("Elternversion nicht gefunden")
        if not is_latest(conn, parent):
            raise EditError("veraltet — es gibt bereits eine neuere Version dieses Skripts")
        corpus_id = conn.execute(
            "SELECT corpus_id FROM script WHERE id = ?", (parent["script_id"],)
        ).fetchone()[0]
        allowed = {
            (r[0], r[1]): r[2]
            for r in conn.execute(
                "SELECT src.snapshot_id, src.ordinal, src.id FROM corpus_source cs "
                "JOIN source_sentence src ON src.snapshot_id = cs.snapshot_id "
                "WHERE cs.corpus_id = ?",
                (corpus_id,),
            )
        }
        parent_cv = {
            r["reuse_key"]: r
            for r in conn.execute(
                "SELECT cv.* FROM claim_verdict cv JOIN script_sentence ss "
                "ON ss.id = cv.script_sentence_id WHERE ss.script_version_id = ?",
                (parent["id"],),
            )
        }
    finally:
        conn.close()

    for ln in imp.lines:
        for ref in ln.refs:
            if ref not in allowed:
                raise EditError(f"Marker {ref[0]}:{ref[1]} gehört nicht zum Korpus dieses Skripts")

    full = normalize(" ".join(ln.text for ln in imp.lines))
    if has_markdown("\n".join(ln.text for ln in imp.lines)):
        raise EditError("Markdown im Text — bitte nur gesprochenen Fließtext")
    if full == parent["text"]:
        raise EditError("keine Änderung am Text (reine Marker-Änderungen sind nicht möglich)")

    sentences: list[DraftSentence] = []
    cur = 0
    for ln in imp.lines:
        ids = {allowed[r] for r in ln.refs}
        for s in split_sentences(ln.text, "de") or [normalize(ln.text)]:
            p = full.find(s, cur)
            if p < 0:
                raise EditError("Satz konnte im Text nicht verortet werden")
            cur = p + len(s)
            sentences.append(DraftSentence(len(sentences), s, p, p + len(s), set(ids)))

    _, verify_prompt_sha = llm.load_prompt(cfg.verify)
    status, check_json, words = run_mechanical_checks(db, full, sentences)

    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            latest = conn.execute(
                "SELECT max(version_no) FROM script_version WHERE script_id = ?",
                (parent["script_id"],),
            ).fetchone()[0]
            if latest != parent["version_no"]:
                raise EditError("veraltet — es gibt bereits eine neuere Version dieses Skripts")
            vid = store_version(
                conn,
                script_id=parent["script_id"],
                parent_id=parent["id"],
                version_no=parent["version_no"] + 1,
                text=full,
                sentences=sentences,
                origin="edit",
                llm_run_id=None,
                check_status=status,
                check_json=check_json,
                word_count=words,
            )
            changed: set[int] = set()
            reused = 0
            for s in sentences:
                key = reuse_key(s.text, s.cited, verify_prompt_sha, cfg.verify.model)
                old = parent_cv.get(key)
                if old is None:
                    changed.add(s.ordinal)
                    continue
                sid = conn.execute(
                    "SELECT id FROM script_sentence WHERE script_version_id = ? AND ordinal = ?",
                    (vid, s.ordinal),
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO claim_verdict (script_sentence_id, llm_run_id, verdict, kind, "
                    "certainty_escalation, hidden_claim, forced_reason, model_verdict, note_de, "
                    "suggested_fix_de, reuse_key, reused_from_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        old["llm_run_id"],
                        old["verdict"],
                        old["kind"],
                        old["certainty_escalation"],
                        old["hidden_claim"],
                        old["forced_reason"],
                        old["model_verdict"],
                        old["note_de"],
                        old["suggested_fix_de"],
                        key,
                        old["id"],
                    ),
                )
                reused += 1
            sha = conn.execute("SELECT sha256 FROM script_version WHERE id = ?", (vid,)).fetchone()[
                0
            ]
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    if changed:
        verify(db, vid, only_ordinals=changed, client=client, config=cfg)
    return {"version_id": vid, "sha256": sha, "reused": reused, "reverified": len(changed)}
