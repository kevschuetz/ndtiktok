"""SRT captions from the recording (D-04): cue text = final transcript sentence (approved
wording for matches, spoken wording for approved deviations); timing = first/last spoken word."""

import json

MAX_LINE = 42
MAX_CUE = 2 * MAX_LINE


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap(text: str) -> str:
    """Two lines of <= MAX_LINE chars, broken at a word boundary near the middle."""
    if len(text) <= MAX_LINE:
        return text
    words = text.split()
    best, cut = None, None
    acc = 0
    for i, w in enumerate(words[:-1]):
        acc += len(w) + (1 if i else 0)
        score = abs(acc - len(text) / 2)
        if best is None or score < best:
            best, cut = score, i + 1
    return " ".join(words[:cut]) + "\n" + " ".join(words[cut:])


def _chunks(text: str, words: list, start: float, end: float) -> list[tuple[float, float, str]]:
    """Split an over-long sentence into cues of <= MAX_CUE chars using word timings when
    available, else proportional time."""
    if len(text) <= MAX_CUE:
        return [(start, end, text)]
    toks = text.split()
    groups, cur = [], []
    for t in toks:
        if cur and len(" ".join(cur + [t])) > MAX_CUE:
            groups.append(cur)
            cur = [t]
        else:
            cur.append(t)
    if cur:
        groups.append(cur)
    out, pos, total = [], 0, len(toks)
    for g in groups:
        n = len(g)
        if words and len(words) == total:
            s, e = words[pos][0], words[pos + n - 1][1]
        else:
            s = start + (end - start) * pos / total
            e = start + (end - start) * (pos + n) / total
        out.append((s, e, " ".join(g)))
        pos += n
    return out


def to_srt(conn, recording_id: int) -> str:
    rows = conn.execute(
        "SELECT * FROM recording_sentence WHERE recording_id = ? AND final_text IS NOT NULL "
        "ORDER BY ordinal",
        (recording_id,),
    ).fetchall()
    cues, prev_end, n = [], 0.0, 0
    for r in rows:
        if r["start_s"] is None or r["end_s"] is None:
            continue
        words = json.loads(r["words_json"] or "[]")
        for s, e, text in _chunks(r["final_text"], words, r["start_s"], r["end_s"]):
            s = max(s, prev_end)
            e = max(e, s + 0.3)
            n += 1
            cues.append(f"{n}\n{_ts(s)} --> {_ts(e)}\n{_wrap(text)}\n")
            prev_end = e
    return "\n".join(cues)
