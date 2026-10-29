"""Loaders/validators for config/hashtags.yaml and config/crisis_lines.yaml (MKT-03, plan 01-14).

Both files hold one language only (the one the pre-registered rule chose, D-08). The crisis-line
file is never passed through `ndc check`: it legitimately names suicide-related services.
"""

import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ndc.config import config_dir

Lang = Literal["de", "en"]


def _pillar_keys() -> tuple[str, ...]:
    data = yaml.safe_load((config_dir() / "matrix.yaml").read_text(encoding="utf-8"))
    return tuple(data["pillar"])


PILLARS = _pillar_keys()
_TAG = re.compile(r"#[\wäöüÄÖÜß]+")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Scheme(_Strict):
    broad: Literal[1]
    niche: list[int]
    pillar: Literal[1]
    total: list[int]

    @model_validator(mode="after")
    def _ranges(self) -> "Scheme":
        if self.niche != [1, 2] or self.total != [3, 5]:
            raise ValueError("scheme must be broad 1, niche [1, 2], pillar 1, total [3, 5]")
        return self


class TagStats(_Strict):
    n_accounts: int
    n_posts: int
    mid_median_views: float | None = None
    median_views: float | None = None
    note: str | None = None


class Excluded(_Strict):
    tag: str
    reason: str


class Gap(_Strict):
    pillar: str
    note: str
    candidates: list[str]


class HashtagSet(_Strict):
    version: int
    language: Lang
    harvest_file: str
    harvested_at: str
    scheme: Scheme
    broad: list[str]
    niche: list[str]
    pillars: dict[str, list[str]]
    keywords: dict[str, list[str]]
    stats: dict[str, TagStats]
    not_chosen: list[Excluded] = []
    excluded: list[Excluded]
    gaps: list[Gap] = []
    verified_in_app: date | None
    approved_at: date | None = None

    @field_validator("broad")
    @classmethod
    def _broad_len(cls, v: list[str]) -> list[str]:
        if not 1 <= len(v) <= 2:
            raise ValueError("broad needs 1-2 tags")
        return v

    @model_validator(mode="after")
    def _consistent(self) -> "HashtagSet":
        if set(self.pillars) != set(PILLARS) or set(self.keywords) != set(PILLARS):
            raise ValueError(f"pillars and keywords need exactly {PILLARS}")
        for p in PILLARS:
            if not self.pillars[p] or not self.keywords[p]:
                raise ValueError(f"pillar {p} needs tags and keywords")
        for tag in self.all_tags():
            if not _TAG.fullmatch(tag):
                raise ValueError(f"bad tag {tag!r}")
            if tag.lower() not in self.stats:
                raise ValueError(f"no harvest stats for {tag}")
            if tag.lower() in {e.tag.lower() for e in self.excluded}:
                raise ValueError(f"{tag} is both chosen and excluded")
        for g in self.gaps:
            if g.pillar not in PILLARS:
                raise ValueError(f"unknown gap pillar {g.pillar}")
        return self

    def all_tags(self) -> list[str]:
        tags = list(self.broad) + list(self.niche)
        for p in PILLARS:
            tags += self.pillars[p]
        return list(dict.fromkeys(tags))


class CrisisEntry(_Strict):
    country: str
    service: str
    number: str
    alt_numbers: list[str] = []
    audience: str
    hours: str
    source_url: str
    verified_at: date
    confirmed: bool = True
    note: str | None = None

    @field_validator("source_url")
    @classmethod
    def _https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("source_url must start with https://")
        return v


class CrisisLines(_Strict):
    version: int
    language: Lang
    approved_at: date | None = None
    short_form: str
    entries: list[CrisisEntry]

    @model_validator(mode="after")
    def _short_form_numbers(self) -> "CrisisLines":
        if not self.entries:
            raise ValueError("no entries")
        if not any(e.number in self.short_form for e in self.entries):
            raise ValueError("short_form must contain at least one listed number")
        return self


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _cached_hashtags(path: str) -> HashtagSet:
    return HashtagSet.model_validate(_load(Path(path)))


@lru_cache(maxsize=4)
def _cached_crisis(path: str) -> CrisisLines:
    return CrisisLines.model_validate(_load(Path(path)))


def load_hashtags(path: Path | None = None) -> HashtagSet:
    return _cached_hashtags(str(path or config_dir() / "hashtags.yaml"))


def load_crisis_lines(path: Path | None = None) -> CrisisLines:
    return _cached_crisis(str(path or config_dir() / "crisis_lines.yaml"))


# ---------------------------------------------------------------- accounts (OPS-02, plan 03-02)
class Platform(_Strict):
    url: str | None
    account_type: Literal["personal", "channel", "creator", "business"]

    @field_validator("url")
    @classmethod
    def _https(cls, v):
        if v is not None and not v.startswith("https://"):
            raise ValueError("account url must start with https://")
        return v


class Accounts(_Strict):
    version: int
    handle: str | None
    bio: str
    posting_slot_local: str | None
    platforms: dict[Literal["tiktok", "youtube", "instagram"], Platform]

    @model_validator(mode="after")
    def _complete(self) -> "Accounts":
        if set(self.platforms) != {"tiktok", "youtube", "instagram"}:
            raise ValueError("platforms must be exactly tiktok, youtube, instagram")
        if self.handle is not None and not re.fullmatch(r"[a-z0-9._]{3,24}", self.handle):
            raise ValueError("handle: lowercase letters, digits, . and _ only (3-24 chars)")
        return self

    def ready(self) -> bool:
        return bool(self.handle and all(p.url for p in self.platforms.values()))


def load_accounts(path: Path | None = None) -> Accounts:
    p = path or config_dir() / "accounts.yaml"
    return Accounts.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
