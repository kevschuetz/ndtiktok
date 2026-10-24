"""Import of in-session judgments (D-21) with the evidence substring guard (D-01).

Phase 1 makes no Anthropic API calls: the Claude Code executor reads the judging bundles, judges
them by config/judging_rubric.md and writes one JSON file per batch. This module validates that
file strictly (extra keys forbidden), checks every caption / pinned-comment / speech evidence
string against the stored text, derives the account levels and writes everything as
`llm_session` field observations in one transaction.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ndc.config import config_dir as _config_dir
from ndc.db import Database

Level = Literal[0, 1, 2, 3]
Conf = Literal["low", "medium", "high"]
Face = Literal["face", "faceless", "mixed", "unknown"]
Format = Literal["talking_head", "voiceover_broll", "text_on_screen", "animation", "skit", "mixed"]
Gender = Literal["male", "female", "mixed", "none", "unknown"]
Pillar = Literal["challenge_science_help", "strengths", "parents", "men_dads_partners"]
Audience = Literal["nd_adults", "parents", "men", "dads", "partners"]
Monetization = Literal[
    "shop", "book", "course", "linktree", "sponsor", "affiliate", "membership", "none"
]
Hedging = Literal["hedged", "neutral", "diagnostic_lists"]

TEXT_MIN_POSTS = 3
VIDEO_MIN_VIDEOS = 2
RUBRIC_FILE = "judging_rubric.md"
PROVENANCE = "llm_session"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PostCiting(_Strict):
    post_id: str
    source: Literal["caption", "pinned_comment"]
    level: Level
    evidence: str | None = None


class SpeechCiting(_Strict):
    level: Level
    evidence: str | None = None


class OnscreenCiting(_Strict):
    text_seen: str | None = None
    level: Level


class VideoJudgment(_Strict):
    video_id: str
    speech: list[SpeechCiting] = Field(default_factory=list)
    onscreen: list[OnscreenCiting] = Field(default_factory=list)
    face: Face = "unknown"
    format: Format | None = None


class Confidence(_Strict):
    source_citing: Conf
    face: Conf
    format: Conf
    pillars: Conf
    monetization_signals: Conf


class AccountJudgment(_Strict):
    account_key: str
    posts: list[PostCiting] = Field(default_factory=list)
    videos: list[VideoJudgment] = Field(default_factory=list)
    face: Face
    format: Format
    visible_speaker_gender: Gender = "unknown"
    pillars: list[Pillar] = Field(default_factory=list)
    audiences: list[Audience] = Field(default_factory=list)
    monetization_signals: list[Monetization] = Field(default_factory=list)
    hedging_or_diagnostic: Hedging
    confidence: Confidence
    notes: str = ""

    @field_validator("account_key")
    @classmethod
    def _key(cls, v: str) -> str:
        platform, _, handle = v.partition(":")
        if platform not in ("tiktok", "youtube") or not handle:
            raise ValueError("account_key must be 'tiktok:<handle>' or 'youtube:<handle>'")
        return v

    @field_validator("monetization_signals")
    @classmethod
    def _none_alone(cls, v: list[str]) -> list[str]:
        if "none" in v and len(v) > 1:
            raise ValueError("'none' must be used alone")
        return v


class Citation(BaseModel):
    """One citation to guard: a caption/pinned post entry, a speech or an on-screen entry."""

    source: Literal["caption", "pinned_comment", "speech", "onscreen"]
    level: int
    evidence: str | None = None
    post_id: str | None = None
    video_id: str | None = None


class GuardedCitation(Citation):
    claimed_level: int
    guard_result: Literal["kept", "downgraded"]


class JudgmentFileError(Exception):
    pass


@dataclass
class ImportReport:
    accounts: int = 0
    downgraded: int = 0
    queued: list = field(default_factory=list)


def rubric_version(cfg: str | Path | None = None) -> int:
    text = (Path(cfg or _config_dir()) / RUBRIC_FILE).read_text(encoding="utf-8")
    m = re.search(r"^rubric_version:\s*(\d+)\s*$", text, re.M)
    if not m:
        raise ValueError(f"{RUBRIC_FILE} has no 'rubric_version: N' line")
    return int(m.group(1))


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _contains(stored: str | None, evidence: str) -> bool:
    """Literal substring check; runs of whitespace count as one space (rubric rule)."""
    if not stored or not evidence or not evidence.strip():
        return False
    return evidence in stored or _ws(evidence) in _ws(stored)


def _stored_text(conn, account_id: int, cit: Citation) -> str | None:
    if cit.source in ("caption", "pinned_comment"):
        col = "description" if cit.source == "caption" else "pinned_comment"
        row = conn.execute(
            f"SELECT {col} FROM competitor_post WHERE account_id = ? AND post_id = ?",  # noqa: S608
            (account_id, cit.post_id),
        ).fetchone()
        return row[0] if row else None
    row = conn.execute(
        "SELECT transcript FROM competitor_video WHERE account_id = ? AND platform_video_id = ?",
        (account_id, cit.video_id),
    ).fetchone()
    return row[0] if row else None


def apply_evidence_guard(conn, account_id: int, cit: Citation) -> GuardedCitation:
    """Level > 0 caption/pinned/speech citations need verbatim evidence in the stored text;
    otherwise the level drops to 0. On-screen citations cannot be checked and keep their level."""
    level, result = cit.level, "kept"
    if cit.source != "onscreen" and cit.level > 0:
        if cit.evidence is None or not _contains(_stored_text(conn, account_id, cit), cit.evidence):
            level, result = 0, "downgraded"
    return GuardedCitation(
        **cit.model_dump(exclude={"level"}),
        level=level,
        claimed_level=cit.level,
        guard_result=result,
    )


def account_level(levels: list[int], min_count: int) -> int:
    """Highest level L such that >= min_count items reach L (item level >= L); 0 otherwise."""
    for lvl in (3, 2, 1):
        if sum(1 for x in levels if x >= lvl) >= min_count:
            return lvl
    return 0


def load_file(path: str | Path) -> list[AccountJudgment]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise JudgmentFileError(f"cannot read {path}: {exc}") from exc
    if isinstance(raw, dict):
        if raw.get("provenance", PROVENANCE) != PROVENANCE:
            raise JudgmentFileError(f"provenance must be {PROVENANCE!r}")
        items = raw.get("judgments")
    else:
        items = raw
    if not isinstance(items, list):
        raise JudgmentFileError("expected a 'judgments' list")
    out, errors = [], []
    for i, item in enumerate(items):
        key = item.get("account_key", f"#{i}") if isinstance(item, dict) else f"#{i}"
        try:
            out.append(AccountJudgment.model_validate(item))
        except ValidationError as exc:
            for e in exc.errors():
                loc = ".".join(str(x) for x in e["loc"])
                errors.append(f"account {key}: field {loc}: {e['msg']}")
    keys = [j.account_key for j in out]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        errors.append(f"duplicate account_key: {', '.join(sorted(dupes))}")
    if errors:
        raise JudgmentFileError(
            "judgment file refused, nothing imported:\n  " + "\n  ".join(errors)
        )
    return out


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _account_id(conn, key: str) -> int | None:
    platform, _, handle = key.partition(":")
    row = conn.execute(
        "SELECT id FROM competitor_account WHERE platform = ? AND lower(handle) = lower(?)",
        (platform, handle),
    ).fetchone()
    return row[0] if row else None


def _import_one(conn, aid: int, j: AccountJudgment, method: str, run_id, now: str) -> int:
    conn.execute(
        "DELETE FROM competitor_field_obs WHERE account_id = ? AND provenance = ?",
        (aid, PROVENANCE),
    )
    conn.execute("DELETE FROM competitor_post_citing WHERE account_id = ?", (aid,))
    downgraded = 0
    post_levels: dict[str, int] = {}
    video_levels: dict[str, int] = {}
    guarded: list[GuardedCitation] = []
    for p in j.posts:
        g = apply_evidence_guard(conn, aid, Citation(**p.model_dump()))
        guarded.append(g)
        post_levels[p.post_id] = max(post_levels.get(p.post_id, 0), g.level)
    for v in j.videos:
        video_levels.setdefault(v.video_id, 0)
        for s in v.speech:
            g = apply_evidence_guard(
                conn, aid, Citation(source="speech", video_id=v.video_id, **s.model_dump())
            )
            guarded.append(g)
            video_levels[v.video_id] = max(video_levels[v.video_id], g.level)
        for o in v.onscreen:
            g = apply_evidence_guard(
                conn,
                aid,
                Citation(
                    source="onscreen", video_id=v.video_id, level=o.level, evidence=o.text_seen
                ),
            )
            guarded.append(g)
            video_levels[v.video_id] = max(video_levels[v.video_id], g.level)
    for g in guarded:
        downgraded += g.guard_result == "downgraded"
        conn.execute(
            "INSERT INTO competitor_post_citing (account_id, post_id, video_id, source, level,"
            " claimed_level, evidence, guard_result, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                aid,
                g.post_id,
                g.video_id,
                g.source,
                g.level,
                g.claimed_level,
                g.evidence,
                g.guard_result,
                now,
            ),
        )
    c = j.confidence
    fields: list[tuple[str, str | None, str]] = []
    if post_levels:
        lvl = account_level(list(post_levels.values()), TEXT_MIN_POSTS)
        fields.append(("source_text_level", str(lvl), c.source_citing))
    if video_levels:
        lvl = account_level(list(video_levels.values()), VIDEO_MIN_VIDEOS)
        fields.append(("source_video_level", str(lvl), c.source_citing))
    fields += [
        ("face", j.face, c.face),
        ("format", j.format, c.format),
        ("visible_speaker_gender", j.visible_speaker_gender, c.face),
        ("pillars", ",".join(j.pillars) or None, c.pillars),
        ("audiences", ",".join(j.audiences) or None, c.pillars),
        ("monetization_signals", ",".join(j.monetization_signals) or None, c.monetization_signals),
        ("hedging_or_diagnostic", j.hedging_or_diagnostic, c.source_citing),
    ]
    if downgraded:
        fields.append(("evidence_guard", f"downgraded:{downgraded}", "high"))
    for name, value, conf in fields:
        conn.execute(
            "INSERT INTO competitor_field_obs (account_id, field, value, provenance, confidence,"
            " method, scan_run_id, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (aid, name, value, PROVENANCE, conf, method, run_id, now),
        )
    return downgraded


def import_judgments(
    db: Database, path: str | Path, cfg: str | Path | None = None, run_id: int | None = None
) -> ImportReport:
    """Validate the whole file first, then write all accounts in one transaction."""
    from ndc.scan import queue

    judgments = load_file(path)
    method = f"in-session judgment, rubric v{rubric_version(cfg)}"
    rep = ImportReport()
    conn = db.connect()
    try:
        ids = {}
        missing = []
        for j in judgments:
            aid = _account_id(conn, j.account_key)
            if aid is None:
                missing.append(j.account_key)
            ids[j.account_key] = aid
        if missing:
            raise JudgmentFileError(
                "judgment file refused, nothing imported: unknown account(s): " + ", ".join(missing)
            )
        now = _now()
        conn.execute("BEGIN")
        try:
            for j in judgments:
                rep.downgraded += _import_one(conn, ids[j.account_key], j, method, run_id, now)
                rep.accounts += 1
            for j in judgments:
                flag, _ = queue.recompute_conn(conn, ids[j.account_key], now)
                if flag:
                    rep.queued.append(j.account_key)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return rep
