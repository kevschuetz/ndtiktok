"""Moderation / crisis playbook (OPS-01, plan 03-02): validated config -> rendered document.

Rule one: nothing is ever sent automatically. The loader enforces `auto_reply: never`, the 150-char
comment limit and that every reply passes the terminology/safety check at claim level; the renderer
writes docs/moderation-playbook.md so the document can never drift from the config.
"""

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ndc.checks.engine import check
from ndc.config import config_dir
from ndc.launch_sets import load_crisis_lines

MAX_REPLY_CHARS = 150
REQUIRED_REPLIES = (
    "crisis_disclosure",
    "diagnosis_request",
    "medication_request",
    "source_request",
    "hostile",
    "scam",
    "thank_you",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Policies(_Strict):
    auto_reply: Literal["never"]
    dms: Literal["restricted", "off"]
    comment_filters: list[str]
    escalation: str
    advice: Literal["none"]
    delete_policy: str


class Reply(_Strict):
    when: str
    text: str | None
    then: str | None = None

    @field_validator("text")
    @classmethod
    def _short(cls, v):
        if v is not None and len(v) > MAX_REPLY_CHARS:
            raise ValueError(f"reply longer than {MAX_REPLY_CHARS} chars ({len(v)})")
        return v


class Spike(_Strict):
    trigger_multiple_of_median_views: float
    median_window_posts: int
    sweeps_per_day: int
    duration_hours: int
    fallback: Literal["restrict_comments", "comments_off"]
    checklist: list[str]


class Moderation(_Strict):
    version: int
    language: Literal["de", "en"]
    approved_at: date | None
    policies: Policies
    keyword_filters: dict[str, list[str] | str]
    replies: dict[str, Reply]
    spike_protocol: Spike
    sensitive_topic_pin: bool
    pre_post_checklist: list[str]

    @model_validator(mode="after")
    def _required(self) -> "Moderation":
        missing = [k for k in REQUIRED_REPLIES if k not in self.replies]
        if missing:
            raise ValueError(f"missing replies: {missing}")
        if self.spike_protocol.trigger_multiple_of_median_views < 2:
            raise ValueError("spike trigger must be at least 2x the median")
        return self


def load_moderation(path: Path | None = None) -> Moderation:
    p = path or config_dir() / "moderation.yaml"
    return Moderation.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))


def validate_replies(mod: Moderation | None = None, db=None) -> list[tuple[str, str, list[str]]]:
    """Run the terminology/safety check on every reply text. Returns [(key, status, rule_ids)];
    raises ValueError if any reply is blocked."""
    mod = mod or load_moderation()
    out = []
    for key, r in mod.replies.items():
        if not r.text:
            continue
        res = check(r.text, mod.language, "claim", db)
        out.append((key, res.status, [f.rule_id for f in res.findings]))
    blocked = [k for k, st, _ in out if st == "blocked"]
    if blocked:
        raise ValueError(f"replies blocked by the safety/terminology check: {blocked}")
    return out


def crisis_numbers_in_sync(mod: Moderation | None = None) -> bool:
    """The crisis reply must carry at least AT 142 and DE 0800 111 0 111 from crisis_lines."""
    mod = mod or load_moderation()
    text = mod.replies["crisis_disclosure"].text or ""
    numbers = {e.number for e in load_crisis_lines().entries}
    return "142" in numbers and "142" in text and "0800 111 0 111" in text


def render_playbook(mod: Moderation | None = None) -> str:
    mod = mod or load_moderation()
    cl = load_crisis_lines()
    L = []
    L.append(
        "<!-- generated from config/moderation.yaml by `ndc moderation render` — do not edit -->"
    )
    L.append("# Moderations- und Krisen-Playbook (OPS-01)\n")
    L.append(
        f"Version {mod.version} · Sprache {mod.language} · freigegeben: "
        f"{mod.approved_at or '**noch nicht** (Operator setzt approved_at in moderation.yaml)'}\n"
    )
    L.append("## 1. Grundsatz: nie automatisch antworten\n")
    L.append(
        "Keine Bots, keine gespeicherten Auto-Nachrichten, keine LLM-Antworten. Jede Antwort "
        "wird vom Operator gelesen, ausgewählt und selbst gesendet. Keine Diagnosen, keine "
        "Medikamenten- oder Therapieberatung, nirgends.\n"
    )
    p = mod.policies
    L.append(
        f"- Auto-Antwort: **{p.auto_reply}** · DMs: **{p.dms}** · "
        f"Filter: {', '.join(p.comment_filters)}\n"
        f"- Eskalation: {p.escalation.replace('_', ' ')} · "
        f"Löschen: {p.delete_policy.replace('_', ' ')}\n"
    )
    L.append("## 2. Antwortvorlagen (manuell senden, ≤ 150 Zeichen)\n")
    for key, r in mod.replies.items():
        L.append(f"### {key}\n")
        L.append(f"**Wann:** {r.when}\n")
        if r.text:
            L.append(f"> {r.text}\n")
        if r.then:
            L.append(f"**Dann:** {r.then}\n")
    L.append("## 3. Krisennummern (aus config/crisis_lines.yaml)\n")
    L.append(f"Kurzform für angepinnte Kommentare: „{cl.short_form}“\n")
    for e in cl.entries:
        L.append(f"- {e.country} · {e.service}: **{e.number}** — {e.hours}")
    L.append("")
    L.append("## 4. Keyword-Filter (in jeder App eintragen)\n")
    for group, words in mod.keyword_filters.items():
        if isinstance(words, str):
            L.append(f"- {group}: {words}")
        else:
            L.append(f"- {group}: {', '.join(words)}")
    L.append("")
    s = mod.spike_protocol
    L.append("## 5. Spike-Protokoll\n")
    L.append(
        f"Auslöser: ein Video überschreitet **{s.trigger_multiple_of_median_views:g}×** den "
        f"Median der letzten {s.median_window_posts} Posts. Dann {s.sweeps_per_day}× täglich "
        f"Kommentare durchsehen, {s.duration_hours} h lang. Wenn das nicht reicht: "
        f"**{s.fallback.replace('_', ' ')}**.\n"
    )
    for item in s.checklist:
        L.append(f"- {item}")
    L.append("")
    L.append("## 6. Checkliste vor dem ersten Post\n")
    for item in mod.pre_post_checklist:
        L.append(f"- [ ] {item}")
    if mod.sensitive_topic_pin:
        L.append(
            "- [ ] Bei sensiblen Themen (config/metrics.yaml pinned_crisis_domains): "
            "Quellen + Krisen-Kurzform anpinnen"
        )
    L.append("")
    return "\n".join(L)
