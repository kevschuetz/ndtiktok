"""The ONLY place that talks to the Anthropic API (SCR-06, D-01/D-02/D-04).

Every call: canonical request JSON -> sha256 -> write-once request artifact -> API -> response
artifact -> one llm_run row. Truncated/refused responses are logged, then raised. Request
artifacts contain the request body only — never headers or keys.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ndc import artifacts
from ndc.config import config_dir, db_path
from ndc.db import Database

log = logging.getLogger(__name__)


class ConfigError(Exception):
    pass


class LlmError(Exception):
    pass


class LlmTruncated(LlmError):
    pass


class LlmRefused(LlmError):
    pass


@dataclass(frozen=True)
class StageConfig:
    model: str
    effort: str
    max_tokens: int
    prompt: str
    append_files: tuple[str, ...] = ()
    word_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class LlmConfig:
    draft: StageConfig
    verify: StageConfig
    prices: dict = field(default_factory=dict)
    editor: StageConfig | None = None


def _stage(raw: dict, name: str) -> StageConfig:
    try:
        wr = raw.get("word_range")
        return StageConfig(
            model=str(raw["model"]),
            effort=str(raw.get("effort", "high")),
            max_tokens=int(raw["max_tokens"]),
            prompt=str(raw["prompt"]),
            append_files=tuple(raw.get("append_files") or ()),
            word_range=(int(wr[0]), int(wr[1])) if wr else None,
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError(f"llm.yaml: bad '{name}' stage: {e}") from e


def load_llm_config(path: Path | None = None) -> LlmConfig:
    p = path or config_dir() / "llm.yaml"
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg = LlmConfig(
        draft=_stage(raw.get("draft") or {}, "draft"),
        verify=_stage(raw.get("verify") or {}, "verify"),
        prices=raw.get("prices") or {},
        editor=_stage(raw["editor"], "editor") if raw.get("editor") else None,
    )
    if cfg.draft.model == cfg.verify.model:
        raise ConfigError("verify.model must differ from draft.model (D-02)")
    if cfg.editor and cfg.editor.model == cfg.verify.model:
        raise ConfigError("verify.model must differ from editor.model (D-02/D-21)")
    return cfg


def load_prompt(stage: StageConfig) -> tuple[str, str]:
    """Prompt text (+ appended files, verbatim) and sha256 of the exact bytes used."""
    parts = [(config_dir() / stage.prompt).read_text(encoding="utf-8")]
    for f in stage.append_files:
        parts.append((config_dir() / f).read_text(encoding="utf-8"))
    text = "\n\n".join(p.rstrip("\n") for p in parts) + "\n"
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _client():
    import os

    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LlmError("ANTHROPIC_API_KEY missing (set it in /home/nd-content/.env)")
    return anthropic.Anthropic()


def _usage(msg) -> dict:
    u = getattr(msg, "usage", None)
    details = getattr(u, "output_tokens_details", None)
    return {
        "input": getattr(u, "input_tokens", None),
        "output": getattr(u, "output_tokens", None),
        "cache_read": getattr(u, "cache_read_input_tokens", None),
        "cache_write": getattr(u, "cache_creation_input_tokens", None),
        "thinking": getattr(details, "thinking_tokens", None),
    }


_warned_prices: set[str] = set()


def cost_usd(prices: dict, model: str, usage: dict) -> float | None:
    p = prices.get(model) or {}
    keys = ("input", "output", "cache_read", "cache_write_5m")
    if any(p.get(k) is None for k in keys):
        if model not in _warned_prices:
            log.warning("llm.yaml has no complete price for %s — cost_usd left NULL", model)
            _warned_prices.add(model)
        return None
    total = (
        (usage["input"] or 0) * p["input"]
        + (usage["output"] or 0) * p["output"]
        + (usage["cache_read"] or 0) * p["cache_read"]
        + (usage["cache_write"] or 0) * p["cache_write_5m"]
    )
    return round(total / 1e6, 6)


def _dump(msg) -> bytes:
    if hasattr(msg, "model_dump"):
        data = msg.model_dump(mode="json")
    else:
        data = msg
    return canonical_json(data)


def call(
    stage: str,
    request: dict,
    *,
    prompt_sha: str | None = None,
    input_shas: list[str] | None = None,
    subject: tuple[str, int] | None = None,
    client=None,
    parse_model=None,
    db: Database | None = None,
    config: LlmConfig | None = None,
):
    """Send one request; returns (message, llm_run_id). parse_model -> client.messages.parse."""
    cfg = config or load_llm_config()
    db = db or Database(db_path())
    logged = dict(request)
    if parse_model is not None:
        logged["output_format"] = {
            "pydantic": parse_model.__name__,
            "schema": parse_model.model_json_schema(),
        }
    req_bytes = canonical_json(logged)
    req_sha = hashlib.sha256(req_bytes).hexdigest()
    artifacts.put(req_bytes, "json")
    req_path = str(artifacts.path(req_sha, "json"))

    c = client or _client()
    if parse_model is not None:
        msg = c.messages.parse(**request, output_format=parse_model)
    else:
        msg = c.messages.create(**request)

    resp_bytes = _dump(msg)
    resp_sha = artifacts.put(resp_bytes, "json")
    usage = _usage(msg)
    model = request.get("model", "")
    stop = getattr(msg, "stop_reason", None)
    conn = db.connect()
    try:
        run_id = conn.execute(
            "INSERT INTO llm_run (stage, model, request_sha256, response_artifact_path, "
            "input_tokens, output_tokens, cost_usd, prompt_sha256, input_sha256s_json, "
            "request_artifact_path, cache_read_tokens, cache_write_tokens, thinking_tokens, "
            "stop_reason, request_id, subject_kind, subject_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                stage,
                model,
                req_sha,
                str(artifacts.path(resp_sha, "json")),
                usage["input"],
                usage["output"],
                cost_usd(cfg.prices, model, usage),
                prompt_sha,
                json.dumps(input_shas or []),
                req_path,
                usage["cache_read"],
                usage["cache_write"],
                usage["thinking"],
                stop,
                getattr(msg, "_request_id", None),
                subject[0] if subject else None,
                subject[1] if subject else None,
            ),
        ).lastrowid
    finally:
        conn.close()
    log.info(
        "llm_run %s stage=%s model=%s stop=%s tokens in=%s out=%s",
        run_id,
        stage,
        model,
        stop,
        usage["input"],
        usage["output"],
    )
    if stop == "max_tokens":
        raise LlmTruncated(f"llm_run {run_id}: response truncated (raise {stage}.max_tokens)")
    if stop == "refusal":
        raise LlmRefused(f"llm_run {run_id}: model refused")
    return msg, run_id
