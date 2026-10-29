"""Sentence alignment between the spoken take and the approved script (D-01).

Monotone dynamic-programming alignment over token-ratio similarity, with merges of up to
`window_merge` adjacent sentences on either side. A pair is a `match` only if its ratio reaches
`similarity_threshold` AND no hedge token of the approved sentence is missing from the spoken one.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ndc.sources.split import _segmenter, normalize

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_for_match(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").casefold()
    s = _PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    return normalize_for_match(s).split()


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return SequenceMatcher(None, ta, tb).ratio()


def split_keep_all(text: str, lang: str = "de") -> list[str]:
    """Sentence split that merges short fragments into the previous sentence, so every
    word of the transcript lands in exactly one sentence (needed for word-span bookkeeping)."""
    text = normalize(text)
    if not text:
        return []
    out: list[str] = []
    for s in _segmenter(lang).segment(text):
        s = s.strip()
        if not s:
            continue
        if out and len(s.split()) < 3:
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
    return out


def missing_hedges(approved: str, spoken: str, hedge_tokens: list[str]) -> list[str]:
    a, s = normalize_for_match(approved), normalize_for_match(spoken)
    a_words, s_words = a.split(), s.split()
    out = []
    for h in hedge_tokens:
        h = normalize_for_match(h)
        if " " in h:
            if h in a and h not in s:
                out.append(h)
        else:
            if any(w.startswith(h) for w in a_words) and not any(w.startswith(h) for w in s_words):
                out.append(h)
    return out


@dataclass
class Aligned:
    status: str  # match | deviation | extra | missing
    spoken_ordinals: list[int] = field(default_factory=list)
    approved_ordinals: list[int] = field(default_factory=list)
    spoken_text: str | None = None
    approved_text: str | None = None
    similarity: float | None = None
    reason: str | None = None


def align(
    spoken: list[str],
    approved: list[str],
    *,
    similarity_threshold: float = 0.80,
    min_candidate_similarity: float = 0.30,
    window_merge: int = 2,
    hedge_tokens: list[str] | None = None,
) -> list[Aligned]:
    hedge_tokens = hedge_tokens or []
    n, m = len(spoken), len(approved)
    W = max(1, int(window_merge))

    def sim(i0, i1, j0, j1):  # spoken[i0:i1] vs approved[j0:j1]
        return similarity(" ".join(spoken[i0:i1]), " ".join(approved[j0:j1]))

    # dp[i][j] = best score aligning spoken[:i] with approved[:j]; back[i][j] = (pi, pj, kind)
    NEG = float("-inf")
    dp = [[NEG] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == NEG:
                continue
            cur = dp[i][j]
            if i < n and cur > dp[i + 1][j]:  # spoken i is extra
                dp[i + 1][j], back[i + 1][j] = cur, (i, j, "extra")
            if j < m and cur > dp[i][j + 1]:  # approved j is missing
                dp[i][j + 1], back[i][j + 1] = cur, (i, j, "missing")
            for di in range(1, W + 1):
                for dj in range(1, W + 1):
                    if di > 1 and dj > 1:
                        continue  # merge on one side only
                    if i + di <= n and j + dj <= m:
                        s = sim(i, i + di, j, j + dj)
                        if s >= min_candidate_similarity:
                            # small penalty per merge so single pairs win ties
                            score = cur + s - 0.01 * (di + dj - 2)
                            if score > dp[i + di][j + dj]:
                                dp[i + di][j + dj] = score
                                back[i + di][j + dj] = (i, j, "pair")
    # backtrack
    steps = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, kind = back[i][j]
        steps.append((pi, pj, i, j, kind))
        i, j = pi, pj
    steps.reverse()
    out: list[Aligned] = []
    for pi, pj, i, j, kind in steps:
        if kind == "extra":
            out.append(Aligned("extra", [pi], [], spoken[pi], None, None, "nicht im Skript"))
        elif kind == "missing":
            out.append(Aligned("missing", [], [pj], None, approved[pj], None, "nicht gesprochen"))
        else:
            sp, ap = " ".join(spoken[pi:i]), " ".join(approved[pj:j])
            s = similarity(sp, ap)
            dropped = missing_hedges(ap, sp, hedge_tokens)
            if dropped:
                status, reason = "deviation", "hedge_dropped:" + ",".join(dropped)
            elif s >= similarity_threshold:
                status, reason = "match", None
            else:
                status, reason = "deviation", f"similarity:{s:.2f}"
            out.append(
                Aligned(status, list(range(pi, i)), list(range(pj, j)), sp, ap, round(s, 3), reason)
            )
    return out
