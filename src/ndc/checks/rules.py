"""Pydantic models for config/terminology.yaml and config/safety.yaml (unknown keys rejected)."""

import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ndc.config import config_dir

Tier = Literal["block", "warn"]
Level = Literal["topic", "script", "claim"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Match(_Strict):
    lemma: list[str] | None = None
    lemma_seq: list[list[str]] | None = None
    regex: str | None = None
    case_sensitive: bool = False
    window: int = 3

    @model_validator(mode="after")
    def _exactly_one(self) -> "Match":
        given = [x for x in (self.lemma, self.lemma_seq, self.regex) if x]
        if len(given) != 1:
            raise ValueError("match needs exactly one of lemma, lemma_seq, regex")
        if self.regex:
            re.compile(self.regex)
        if self.window < 1 or self.window > 5:
            raise ValueError("window must be 1..5")
        return self

    def compiled(self) -> re.Pattern:
        return re.compile(self.regex, 0 if self.case_sensitive else re.IGNORECASE)


class Rule(_Strict):
    id: str
    lang: Literal["de", "en", "any"]
    tier: Tier
    category: str
    match: Match | list[Match]
    allow_in_quotes: bool = False
    message: str
    suggest: str | None = None
    rationale: str | None = None
    source: str | None = None
    levels: list[Level] | None = None

    @property
    def matches(self) -> list[Match]:
        return self.match if isinstance(self.match, list) else [self.match]

    def applies_to(self, lang: str) -> bool:
        return self.lang in ("any", lang)


class _RuleFile(_Strict):
    version: int
    approved_by: str | None = None
    approved_at: date | datetime | str | None = None

    @staticmethod
    def _unique(rules: list[Rule]) -> list[Rule]:
        ids = [r.id for r in rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate rule ids: {sorted(dupes)}")
        return rules


class TerminologyFile(_RuleFile):
    terms: list[Rule]

    @field_validator("terms")
    @classmethod
    def _ids(cls, v: list[Rule]) -> list[Rule]:
        return cls._unique(v)


class SafetyFile(_RuleFile):
    scope: Literal["subject"]
    levels: list[Level]
    rules: list[Rule]

    @field_validator("rules")
    @classmethod
    def _all_block(cls, v: list[Rule]) -> list[Rule]:
        bad = [r.id for r in v if r.tier != "block"]
        if bad:
            raise ValueError(f"safety rules must all be tier block: {bad}")
        return cls._unique(v)


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at top level")
    return data


@lru_cache(maxsize=8)
def _load_term(path: str, mtime: float) -> TerminologyFile:
    return TerminologyFile.model_validate(_read(Path(path)))


@lru_cache(maxsize=8)
def _load_safety(path: str, mtime: float) -> SafetyFile:
    return SafetyFile.model_validate(_read(Path(path)))


def load_terminology(path: Path | None = None) -> TerminologyFile:
    p = path or config_dir() / "terminology.yaml"
    return _load_term(str(p), p.stat().st_mtime)


def load_safety(path: Path | None = None) -> SafetyFile:
    p = path or config_dir() / "safety.yaml"
    return _load_safety(str(p), p.stat().st_mtime)
