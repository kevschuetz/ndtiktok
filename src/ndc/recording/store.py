"""Recording store: transcribe a take, align it to the approved script, persist immutably (D-01).

`add_recording` is the only writer. The final transcript (approved text for matches, spoken text
for deviations/extras, in spoken order) and its sha256 are fixed at insert time; the approval in
recording/gate.py keys on that sha, so a new take is always a new hash.
"""

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from ndc.config import config_dir
from ndc.db import Database
from ndc.recording.align import Aligned, align, split_keep_all, tokens
from ndc.review.gate import is_latest
from ndc.review.store import latest_decision


class RecordingError(Exception):
    pass


@dataclass(frozen=True)
class RecordingConfig:
    recordings_dir: str
    whisper_model: str
    compute_type: str
    cpu_threads: int
    language: str
    similarity_threshold: float
    min_candidate_similarity: float
    window_merge: int
    low_confidence_word_prob: float
    hedge_tokens: tuple[str, ...]


def load_config(path: Path | None = None) -> RecordingConfig:
    raw = yaml.safe_load((path or config_dir() / "recording.yaml").read_text(encoding="utf-8"))
    return RecordingConfig(
        recordings_dir=str(raw.get("recordings_dir", "/data/recordings")),
        whisper_model=str(raw.get("whisper_model", "large-v3")),
        compute_type=str(raw.get("compute_type", "int8")),
        cpu_threads=int(raw.get("cpu_threads", 2)),
        language=str(raw.get("language", "de")),
        similarity_threshold=float(raw["similarity_threshold"]),
        min_candidate_similarity=float(raw.get("min_candidate_similarity", 0.3)),
        window_merge=int(raw.get("window_merge", 2)),
        low_confidence_word_prob=float(raw.get("low_confidence_word_prob", 0.5)),
        hedge_tokens=tuple(raw.get("hedge_tokens") or ()),
    )


def _sha_text(text: str) -> str:
    return hashlib.sha256(unicodedata.normalize("NFC", text).encode("utf-8")).hexdigest()


def resolve_script_sha(conn, ref: str) -> str:
    ref = (ref or "").strip().lower()
    if len(ref) < 8 or any(c not in "0123456789abcdef" for c in ref):
        raise RecordingError("Skript-Sha: mindestens 8 Hex-Zeichen angeben")
    rows = conn.execute(
        "SELECT sha256 FROM script_version WHERE sha256 LIKE ?", (ref + "%",)
    ).fetchall()
    if len(rows) != 1:
        raise RecordingError(f"Skriptversion {ref} nicht gefunden oder mehrdeutig")
    return rows[0][0]


def _inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def sentences_with_spans(transcript) -> list[dict]:
    """Split the transcript into sentences and attach word spans (start/end/words) by walking the
    word list; token counts come from the same normalized text so they stay in step."""
    words = transcript.words
    text = transcript.text
    sents = split_keep_all(text, "de")
    out, wi = [], 0
    for s in sents:
        n = len(tokens(s))
        span = []
        while wi < len(words) and len(span) < n:
            if tokens(words[wi].word):
                span.append(words[wi])
            wi += 1
        out.append(
            {
                "text": s,
                "start": span[0].start if span else None,
                "end": span[-1].end if span else None,
                "words": [[w.start, w.end, w.word, w.prob] for w in span],
            }
        )
    return out


def _default_transcriber(cfg: RecordingConfig):
    from ndc.scan.transcribe import Transcriber

    return Transcriber(
        model=cfg.whisper_model, compute_type=cfg.compute_type, cpu_threads=cfg.cpu_threads
    )


def add_recording(
    db: Database,
    path: str | Path,
    script_ref: str,
    *,
    transcriber=None,
    cfg: RecordingConfig | None = None,
) -> dict:
    cfg = cfg or load_config()
    p = Path(path)
    if not _inside(p, Path(cfg.recordings_dir)):
        raise RecordingError(f"Aufnahme muss unter {cfg.recordings_dir} liegen")
    if not p.is_file():
        raise RecordingError(f"Datei nicht gefunden: {p}")
    conn = db.connect()
    try:
        sha = resolve_script_sha(conn, script_ref)
        v = conn.execute("SELECT * FROM script_version WHERE sha256 = ?", (sha,)).fetchone()
        dec = latest_decision(conn, sha)
        if dec is None or dec["decision"] != "approved":
            raise RecordingError("Skriptversion ist nicht freigegeben")
        if not is_latest(conn, v):
            raise RecordingError("Skriptversion ist veraltet — es gibt eine neuere Version")
        approved = [
            r["text"]
            for r in conn.execute(
                "SELECT text FROM script_sentence WHERE script_version_id = ? ORDER BY ordinal",
                (v["id"],),
            )
        ]
    finally:
        conn.close()

    file_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    tr = (transcriber or _default_transcriber(cfg)).transcribe_words(str(p), cfg.language)
    spans = sentences_with_spans(tr)
    aligned: list[Aligned] = align(
        [s["text"] for s in spans],
        approved,
        similarity_threshold=cfg.similarity_threshold,
        min_candidate_similarity=cfg.min_candidate_similarity,
        window_merge=cfg.window_merge,
        hedge_tokens=list(cfg.hedge_tokens),
    )
    rows, final_parts = [], []
    for a in aligned:
        if a.status == "missing":
            rows.append(
                dict(
                    status="missing",
                    spoken_text=None,
                    approved_ordinal=a.approved_ordinals[0],
                    approved_text=a.approved_text,
                    final_text=None,
                    start_s=None,
                    end_s=None,
                    similarity=None,
                    reason=a.reason,
                    words=[],
                )
            )
            continue
        sp = [spans[i] for i in a.spoken_ordinals]
        words = [w for s in sp for w in s["words"]]
        final = a.approved_text if a.status == "match" else a.spoken_text
        final_parts.append(final)
        rows.append(
            dict(
                status=a.status,
                spoken_text=a.spoken_text,
                approved_ordinal=a.approved_ordinals[0] if a.approved_ordinals else None,
                approved_text=a.approved_text,
                final_text=final,
                start_s=sp[0]["start"],
                end_s=sp[-1]["end"],
                similarity=a.similarity,
                reason=a.reason,
                words=words,
            )
        )
    final_text = " ".join(final_parts)
    final_sha = _sha_text(final_text)
    counts = {
        k: sum(1 for r in rows if r["status"] == k)
        for k in ("match", "deviation", "extra", "missing")
    }
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if conn.execute(
                "SELECT 1 FROM recording WHERE transcript_sha256 = ?", (final_sha,)
            ).fetchone():
                raise RecordingError("identische Aufnahme (Transkript) existiert bereits")
            rid = conn.execute(
                "INSERT INTO recording (script_version_id, script_sha256, file_name, file_sha256, "
                "duration_s, whisper_model, language, transcript_raw, transcript_final, "
                "transcript_sha256, similarity_threshold, n_match, n_deviation, n_extra, "
                "n_missing) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    v["id"],
                    sha,
                    p.name,
                    file_sha,
                    tr.duration_s,
                    cfg.whisper_model,
                    cfg.language,
                    tr.text,
                    final_text,
                    final_sha,
                    cfg.similarity_threshold,
                    counts["match"],
                    counts["deviation"],
                    counts["extra"],
                    counts["missing"],
                ),
            ).lastrowid
            for i, r in enumerate(rows):
                conn.execute(
                    "INSERT INTO recording_sentence (recording_id, ordinal, status, spoken_text, "
                    "approved_ordinal, approved_text, final_text, start_s, end_s, similarity, "
                    "reason, "
                    "words_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        i,
                        r["status"],
                        r["spoken_text"],
                        r["approved_ordinal"],
                        r["approved_text"],
                        r["final_text"],
                        r["start_s"],
                        r["end_s"],
                        r["similarity"],
                        r["reason"],
                        json.dumps(r["words"]),
                    ),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return {"recording_id": rid, "transcript_sha256": final_sha, **counts}


def recording_by_ref(conn, ref: str):
    """Accept a recording id or a transcript-sha prefix."""
    ref = (ref or "").strip().lower()
    if ref.isdigit():
        row = conn.execute("SELECT * FROM recording WHERE id = ?", (int(ref),)).fetchone()
    else:
        if len(ref) < 8:
            raise RecordingError("Sha-Präfix mit mindestens 8 Zeichen oder eine ID angeben")
        rows = conn.execute(
            "SELECT * FROM recording WHERE transcript_sha256 LIKE ?", (ref + "%",)
        ).fetchall()
        if len(rows) > 1:
            raise RecordingError("Sha-Präfix ist mehrdeutig")
        row = rows[0] if rows else None
    if row is None:
        raise RecordingError(f"Aufnahme {ref} nicht gefunden")
    return row


def sentences(conn, recording_id: int) -> list:
    return conn.execute(
        "SELECT rs.*, rv.verdict, rv.kind, rv.certainty_escalation, rv.hidden_claim, "
        "rv.forced_reason, rv.note_de, rv.suggested_fix_de "
        "FROM recording_sentence rs LEFT JOIN recording_verdict rv "
        "ON rv.recording_sentence_id = rs.id WHERE rs.recording_id = ? ORDER BY rs.ordinal",
        (recording_id,),
    ).fetchall()
