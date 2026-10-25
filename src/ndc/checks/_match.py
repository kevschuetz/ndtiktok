"""Shared matcher: applies Rule objects to normalized text and returns Findings."""

from ndc.checks.models import Finding
from ndc.checks.rules import Rule
from ndc.checks.text import normalize, strip_invisible, strip_quoted, tokens


def _seq_spans(toks, seq: list[set[str]], window: int):
    for i, (surf, lem, start, _end) in enumerate(toks):
        if surf not in seq[0] and lem not in seq[0]:
            continue
        pos, ok = i, True
        for step in seq[1:]:
            nxt = None
            for j in range(pos + 1, min(pos + window, len(toks) - 1) + 1):
                if toks[j][0] in step or toks[j][1] in step:
                    nxt = j
                    break
            if nxt is None:
                ok = False
                break
            pos = nxt
        if ok:
            yield start, toks[pos][3]


def apply_rules(text: str, lang: str, rules: list[Rule], source_file: str) -> list[Finding]:
    norm = normalize(text)
    clean, idx = strip_invisible(norm)  # spans below are on `clean`; idx maps back to `norm`
    stripped = strip_quoted(clean)
    tok_cache: dict[bool, list] = {}
    out: dict[tuple[str, int, int], Finding] = {}
    for rule in rules:
        if not rule.applies_to(lang):
            continue
        hay = stripped if rule.allow_in_quotes else clean
        for m in rule.matches:
            spans: list[tuple[int, int]] = []
            if m.regex:
                spans = [
                    (x.start(), x.end()) for x in m.compiled().finditer(hay) if x.end() > x.start()
                ]
            else:
                if rule.allow_in_quotes not in tok_cache:
                    tok_cache[rule.allow_in_quotes] = tokens(hay, lang)
                toks = tok_cache[rule.allow_in_quotes]
                if m.lemma:
                    wanted = {w.lower() for w in m.lemma}
                    spans = [(s, e) for surf, lem, s, e in toks if surf in wanted or lem in wanted]
                else:
                    seq = [{w.lower() for w in step} for step in m.lemma_seq]
                    spans = list(_seq_spans(toks, seq, m.window))
            for cs, ce in spans:
                s, e = idx[cs], idx[ce - 1] + 1
                key = (rule.id, s, e)
                if key not in out:
                    out[key] = Finding(
                        rule_id=rule.id,
                        tier=rule.tier,
                        category=rule.category,
                        span=(s, e),
                        matched_text=norm[s:e],
                        message=rule.message,
                        suggest=rule.suggest,
                        source_file=source_file,
                    )
    return sorted(out.values(), key=lambda f: (f.span[0], f.rule_id))
