"""Pure language decision (MKT-02, D-20): decide(accounts, rule) -> DecisionResult.

The rule's ordered `when` conditions live in config/decision_rule.yaml and are evaluated here with
a tiny whitelisted expression grammar (names, numbers, comparisons, and/or) — no other code runs.
"""

import ast
import hashlib
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from ndc.db import Database

Lang = Literal["de", "en"]


class AccountRow(BaseModel):
    handle: str
    language: Lang
    platform: Literal["tiktok", "youtube"]
    followers: int | None = None
    reach_median: float | None = None  # median views of newest 15 posts >= 72 h old
    n_reach_posts: int = 0
    source_citing_score: int | None = None  # 0-3, final value
    face: Literal["face", "faceless", "mixed", "unknown"] = "unknown"
    voice_gender: Literal["male", "female", "mixed", "none", "unknown"] = "unknown"


class Tier(BaseModel):
    min: int
    max: int | None = None


class RuleRow(BaseModel):
    id: str
    when: str
    verdict: Lang
    inconclusive: bool
    why: str = ""


class DecisionRule(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: int
    sample_min_followers: int
    tiers: dict[str, Tier]
    min_posts_for_reach: int
    reach_platform: Literal["tiktok", "youtube"]
    reach_tier: str
    validity_min_mid_accounts: int
    source_score_threshold: int
    slot_face: str
    slot_voice_gender: str
    rules: list[RuleRow]
    sha256: str = ""


class DecisionResult(BaseModel):
    verdict: Lang
    matched_row: str
    inconclusive: bool
    metrics: dict
    rule_sha256: str


_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
)


def _compile_when(expr: str):
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"disallowed syntax in rule condition: {expr!r}")
    return compile(tree, "<decision_rule>", "eval")


def load_rule(path: str | Path) -> DecisionRule:
    raw = Path(path).read_bytes()
    rule = DecisionRule.model_validate(yaml.safe_load(raw))
    rule.sha256 = hashlib.sha256(raw).hexdigest()
    if not rule.rules or rule.rules[-1].when.strip() != "else":
        raise ValueError("decision rule must end with an 'else' row")
    for r in rule.rules[:-1]:
        _compile_when(r.when)
    return rule


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _in_tier(followers: int | None, tier: Tier) -> bool:
    if followers is None:
        return False
    return followers >= tier.min and (tier.max is None or followers <= tier.max)


def _reach(accounts: list[AccountRow], rule: DecisionRule, lang: str, platform: str):
    tier = rule.tiers[rule.reach_tier]
    vals = [
        a.reach_median
        for a in accounts
        if a.language == lang
        and a.platform == platform
        and _in_tier(a.followers, tier)
        and a.reach_median is not None
        and a.n_reach_posts >= rule.min_posts_for_reach
    ]
    return len(vals), _median(vals)


def _sourcing(accounts: list[AccountRow], rule: DecisionRule, lang: str) -> tuple[int, int]:
    sourced, slot = _sourcing_keys(accounts, rule, lang)
    return len(sourced), len(slot)


def _sourcing_keys(
    accounts: list[AccountRow], rule: DecisionRule, lang: str, with_platform: bool = False
) -> tuple[set[str], set[str]]:
    sourced: set[str] = set()
    slot: set[str] = set()
    for a in accounts:
        if a.language != lang:
            continue
        if a.followers is not None and a.followers < rule.sample_min_followers:
            continue
        if a.source_citing_score is None or a.source_citing_score < rule.source_score_threshold:
            continue
        key = a.handle.strip().lower()
        if with_platform:
            key = f"{a.platform}:{key}"
        sourced.add(key)
        if a.face == rule.slot_face and a.voice_gender == rule.slot_voice_gender:
            slot.add(key)
    return sourced, slot


def tier_of(followers: int | None, rule: DecisionRule) -> str:
    if followers is None:
        return "unknown"
    if followers < rule.sample_min_followers:
        return "below_min"
    for name, t in rule.tiers.items():
        if _in_tier(followers, t):
            return name
    return "unknown"


def decision_context(accounts: list[AccountRow], rule: DecisionRule) -> dict:
    """Sample counts per language/platform/tier and the handles behind N/S (for the log)."""
    counts: dict[str, int] = {}
    for a in accounts:
        k = f"{a.language} {a.platform} {tier_of(a.followers, rule)}"
        counts[k] = counts.get(k, 0) + 1
    out: dict = {"counts": dict(sorted(counts.items())), "n_accounts": len(accounts)}
    for lang in ("de", "en"):
        sourced, slot = _sourcing_keys(accounts, rule, lang, with_platform=True)
        out[f"sourced_{lang}"] = sorted(sourced)
        out[f"slot_{lang}"] = sorted(slot)
    return out


def compute_metrics(accounts: list[AccountRow], rule: DecisionRule) -> dict:
    n_mid_de, r_de = _reach(accounts, rule, "de", rule.reach_platform)
    n_mid_en, r_en = _reach(accounts, rule, "en", rule.reach_platform)
    if r_de is None or r_en is None:
        q = None
    elif r_de == 0:
        q = float("inf")
    else:
        q = r_en / r_de
    n_de, s_de = _sourcing(accounts, rule, "de")
    n_en, s_en = _sourcing(accounts, rule, "en")
    _, yt_de = _reach(accounts, rule, "de", "youtube")
    _, yt_en = _reach(accounts, rule, "en", "youtube")
    return {
        "R_DE": r_de,
        "R_EN": r_en,
        "Q": q,
        "n_mid_de": n_mid_de,
        "n_mid_en": n_mid_en,
        "N_DE": n_de,
        "N_EN": n_en,
        "S_DE": s_de,
        "S_EN": s_en,
        "youtube_R_DE": yt_de,
        "youtube_R_EN": yt_en,  # reported only, never in Q (D-18)
    }


def decide(accounts: list[AccountRow], rule: DecisionRule) -> DecisionResult:
    """Pure: evaluate the rule rows in order; first match wins; the final row is 'else'."""
    m = compute_metrics(accounts, rule)
    env = {k: v for k, v in m.items() if not k.startswith("youtube_")}
    matched = rule.rules[-1]
    for row in rule.rules[:-1]:
        try:
            hit = bool(eval(_compile_when(row.when), {"__builtins__": {}}, dict(env)))  # noqa: S307
        except TypeError:  # a None metric (e.g. Q without reach) cannot satisfy a condition
            hit = False
        if hit:
            matched = row
            break
    return DecisionResult(
        verdict=matched.verdict,
        matched_row=matched.id,
        inconclusive=matched.inconclusive,
        metrics=m,
        rule_sha256=rule.sha256,
    )


def fmt_metric(v) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.2f}" if v != float("inf") else "inf"
    return str(v)


def write_decision_log(
    db: Database,
    res: DecisionResult,
    log_path: str | Path,
    context: dict | None = None,
    prereg_evidence: dict | None = None,
) -> int:
    """Append a dated 'Validation week 1' section to the log and insert a language_decision row.

    context (decision_context) and prereg_evidence (rule commit time vs first scan_run) add the
    sample counts, the handles behind N/S and the pre-registration check to the section."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = res.metrics
    s_de_answer = "yes" if (m.get("S_DE") or 0) >= 1 else "no"
    lines = [
        f"\n## Validation week 1 — language decision {now}\n\n",
        f"- verdict: **{res.verdict}** (row {res.matched_row}"
        f"{', inconclusive' if res.inconclusive else ''})\n",
    ]
    for k in ("R_DE", "R_EN", "Q", "n_mid_de", "n_mid_en", "N_DE", "N_EN", "S_DE", "S_EN"):
        lines.append(f"- {k}: {fmt_metric(m.get(k))}\n")
    lines.append(
        "- YouTube Shorts reach (reported only, not in Q): "
        f"DE {fmt_metric(m.get('youtube_R_DE'))}, "
        f"EN {fmt_metric(m.get('youtube_R_EN'))}\n"
    )
    slot_de = (context or {}).get("slot_de") or []
    lines.append(
        f"- Does a sourced, male, faceless German account exist? **{s_de_answer}** "
        f"(S_DE = {fmt_metric(m.get('S_DE'))}"
        + (f"; counting: {', '.join(slot_de)}" if slot_de else "")
        + ")\n"
    )
    lines.append(f"- rule sha256: `{res.rule_sha256}`\n")
    if context:
        for lang in ("de", "en"):
            src = context.get(f"sourced_{lang}") or []
            lines.append(
                f"- sourced {lang.upper()} accounts (N_{lang.upper()}): "
                f"{', '.join(src) if src else 'none'}\n"
            )
        n_acc = context.get("n_accounts", 0)
        lines.append(f"- sample: {n_acc} accounts; per language/platform/tier:\n")
        for k, n in (context.get("counts") or {}).items():
            lines.append(f"  - {k}: {n}\n")
    if prereg_evidence:
        committed = prereg_evidence.get("rule_committed_at") or "not given"
        first = prereg_evidence.get("first_scan_run_at") or "no scan_run"
        precedes = prereg_evidence.get("precedes")
        verdict = {True: "yes", False: "NO"}.get(precedes, "unknown")
        lines.append(
            f"- pre-registration: rule lock committed {committed}; first scan_run started {first}; "
            f"commit precedes the first scan_run: {verdict}\n"
        )
    lines.append(
        "- Q uses TikTok mid-tier reach only; YouTube Shorts reach is reported alongside (D-18). "
        "Milestone 1 runs in one language only (D-08).\n"
    )
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# Language decision log (MKT-02)\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.writelines(lines)
    metrics_json = json.dumps(
        {k: (None if v == float("inf") else v) for k, v in m.items()}, sort_keys=True
    )
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO language_decision (verdict, matched_row, inconclusive, metrics_json,"
            " rule_sha256, decided_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                res.verdict,
                res.matched_row,
                int(res.inconclusive),
                metrics_json,
                res.rule_sha256,
                now,
            ),
        )
        return cur.lastrowid
    finally:
        conn.close()


def current_language(db: Database) -> Lang | None:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT verdict FROM language_decision ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()
