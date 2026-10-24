"""Result types shared by the checker (contract consumed by Phase 2 and plan 05)."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Finding:
    rule_id: str
    tier: Literal["block", "warn"]
    category: str
    span: tuple[int, int]
    matched_text: str
    message: str
    suggest: str | None
    source_file: Literal["terminology", "safety"]


@dataclass(frozen=True)
class CheckResult:
    status: Literal["ok", "needs_override", "blocked"]
    findings: list[Finding]
    text_sha256: str
    terminology_version: int
    overridden_rule_ids: list[str] = field(default_factory=list)
