"""Topic matrix: vocab-validated add/import/list, topic-level safety check (CONT-01, CONT-04).

Every dimension value is validated against config/matrix.yaml. Every topic that enters the DB
(add or import) runs checks.engine.check(..., level="topic") and stores safety_status plus the
findings. No runtime LLM call happens here (D-19): seeds are reviewed YAML files.
"""

import json
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from ndc.checks.engine import check
from ndc.config import config_dir
from ndc.db import Database

DIMENSIONS = ("pillar", "condition", "domain", "audience", "angle")
LIST_TAGS = ("whitelist", "blacklist")
SOURCE_LIKELY = ("yes", "maybe", "no")
STATUSES = (
    "proposed",
    "backlog",
    "selected",
    "in_production",
    "published",
    "retired",
    "rejected",
)
LANGS = ("de", "en")

INSERT_COLUMNS = (
    "pillar",
    "condition",
    "domain",
    "audience",
    "angle",
    "language",
    "working_title",
    "summary",
    "list_tag",
    "source_likely",
    "origin",
)
FILTER_COLUMNS = (*DIMENSIONS, "list_tag", "status")
LIST_COLUMNS = (
    "id",
    "pillar",
    "condition",
    "domain",
    "audience",
    "angle",
    "working_title",
    "list_tag",
    "safety_status",
    "source_likely",
    "status",
)

_SAFETY_FROM_CHECK = {"blocked": "blocked", "needs_override": "flagged", "ok": "ok"}
_SAFETY_RANK = {"ok": 0, "flagged": 1, "blocked": 2}


class TopicError(ValueError):
    """Operator-facing validation or state error (CLI prints it and exits non-zero)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VocabEntry(_Strict):
    de: str
    en: str
    guideline_layer: Literal["awmf_s3", "pubmed_reviews"] | None = None
    sensitive: bool = False
    note: str | None = None


class Matrix(_Strict):
    version: int
    pillar: dict[str, VocabEntry]
    condition: dict[str, VocabEntry]
    domain: dict[str, VocabEntry]
    audience: dict[str, VocabEntry]
    angle: dict[str, VocabEntry]

    @field_validator("condition")
    @classmethod
    def _conditions_have_layer(cls, v: dict[str, VocabEntry]) -> dict[str, VocabEntry]:
        missing = [k for k, e in v.items() if e.guideline_layer is None]
        if missing:
            raise ValueError(f"conditions without guideline_layer: {missing}")
        return v

    def keys(self, dim: str) -> tuple[str, ...]:
        return tuple(getattr(self, dim))


class SeedTopic(_Strict):
    pillar: str
    condition: str
    domain: str
    audience: str
    angle: str
    working_title: str
    summary: str
    list_tag: Literal["whitelist", "blacklist"]
    source_likely: Literal["yes", "maybe", "no"]
    notes: str | None = None  # reviewer note in the YAML; not stored


class Seed(_Strict):
    version: int
    language: Literal["de", "en"]
    topics: list[SeedTopic]


@dataclass(frozen=True)
class ImportResult:
    inserted: int
    skipped: int  # already present (UNIQUE working_title, language)
    blocked: int
    flagged: int


@lru_cache(maxsize=4)
def _load_matrix_from(path: str, mtime: float) -> Matrix:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Matrix.model_validate(data)


def load_matrix() -> Matrix:
    path = config_dir() / "matrix.yaml"
    return _load_matrix_from(str(path), path.stat().st_mtime)


def valid_values(field: str) -> tuple[str, ...]:
    if field in DIMENSIONS:
        return load_matrix().keys(field)
    return {"list_tag": LIST_TAGS, "status": STATUSES, "source_likely": SOURCE_LIKELY}[field]


def _validate_value(field: str, value: Any, where: str = "") -> None:
    allowed = valid_values(field)
    if value not in allowed:
        prefix = f"{where}." if where else ""
        raise TopicError(
            f"{prefix}{field}: {value!r} is not a valid key; valid: {', '.join(allowed)}"
        )


def safety_check(working_title: str, summary: str | None, language: str | None):
    """Topic-level check of title + summary. Returns (safety_status, hits_json).

    With no language yet (pre-decision operator adds) both languages are checked and the worst
    result wins, so an English "melatonin" title cannot slip through a German-only check.
    """
    text = working_title + "\n" + (summary or "")
    langs = [language] if language else list(LANGS)
    status, hits = "ok", []
    for lang in langs:
        res = check(text, lang=lang, level="topic")
        s = _SAFETY_FROM_CHECK[res.status]
        if _SAFETY_RANK[s] > _SAFETY_RANK[status]:
            status = s
        for f in res.findings:
            hit = {"rule_id": f.rule_id, "tier": f.tier, "matched_text": f.matched_text}
            if hit not in hits:
                hits.append(hit)
    return status, json.dumps(hits, ensure_ascii=False) if hits else None


def _insert_sql(cols: list[str], ignore: bool = False) -> str:
    verb = "INSERT OR IGNORE" if ignore else "INSERT"
    allcols = [*cols, "safety_status", "safety_hits_json"]
    marks = ", ".join("?" * len(allcols))
    return f"{verb} INTO topic ({', '.join(allcols)}) VALUES ({marks})"


def add_topic(db: Database, **fields: Any) -> int:
    unknown = set(fields) - set(INSERT_COLUMNS)
    if unknown:
        raise ValueError(f"unknown topic fields: {sorted(unknown)}")
    for dim in DIMENSIONS:
        _validate_value(dim, fields.get(dim))
    _validate_value("list_tag", fields.get("list_tag"))
    _validate_value("source_likely", fields.get("source_likely"))
    lang = fields.get("language")
    if lang is not None and lang not in LANGS:
        raise TopicError(f"language: {lang!r} is not valid; valid: de, en")
    status, hits = safety_check(fields["working_title"], fields.get("summary"), lang)
    cols = [c for c in INSERT_COLUMNS if fields.get(c) is not None]
    conn = db.connect()
    try:
        cur = conn.execute(_insert_sql(cols), [fields[c] for c in cols] + [status, hits])
        return int(cur.lastrowid)
    finally:
        conn.close()


def _parse_seed(path: Path) -> Seed:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TopicError(f"{path}: cannot read seed YAML: {exc}") from exc
    try:
        seed = Seed.model_validate(data)
    except ValidationError as exc:
        errs = "; ".join(f"{_loc(e['loc'])}: {e['msg']}" for e in exc.errors(include_url=False))
        raise TopicError(f"{path}: {errs}") from exc
    for i, t in enumerate(seed.topics):
        for dim in DIMENSIONS:
            _validate_value(dim, getattr(t, dim), where=f"{path}: topics[{i}]")
    return seed


def _loc(loc: tuple) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def import_seed(db: Database, path: str | Path) -> ImportResult:
    """Load a reviewed seed YAML. All-or-nothing: any invalid topic aborts the whole file."""
    path = Path(path)
    seed = _parse_seed(path)
    prepared = []
    for t in seed.topics:
        status, hits = safety_check(t.working_title, t.summary, seed.language)
        prepared.append((t, status, hits))
    cols = list(INSERT_COLUMNS)
    sql = _insert_sql(cols, ignore=True)
    inserted = 0
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for t, status, hits in prepared:
                row = {**t.model_dump(), "language": seed.language, "origin": "matrix"}
                cur = conn.execute(sql, [row.get(c) for c in cols] + [status, hits])
                inserted += cur.rowcount
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    new_status = [s for _, s, _ in prepared]
    return ImportResult(
        inserted=inserted,
        skipped=len(prepared) - inserted,
        blocked=new_status.count("blocked"),
        flagged=new_status.count("flagged"),
    )


def list_topics(db: Database, filters: dict[str, Any] | None = None) -> list[sqlite3.Row]:
    filters = {k: v for k, v in (filters or {}).items() if v is not None}
    unknown = set(filters) - set(FILTER_COLUMNS)
    if unknown:
        raise ValueError(f"unknown topic filters: {sorted(unknown)}")
    for k, v in filters.items():
        _validate_value(k, v)
    # column names come from the fixed FILTER_COLUMNS allow-list; values are parameters
    where = " AND ".join(f"{k} = ?" for k in filters)
    sql = f"SELECT {', '.join(LIST_COLUMNS)} FROM topic"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY id"
    conn = db.connect()
    try:
        return conn.execute(sql, list(filters.values())).fetchall()
    finally:
        conn.close()
