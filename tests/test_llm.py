import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from ndc import llm
from ndc.db import Database

sys.path.insert(0, str(Path(__file__).parent / "script"))
from script_helpers import FakeClient, FakeMessage  # noqa: E402


@pytest.fixture(autouse=True)
def _art(monkeypatch):
    monkeypatch.setenv("NDC_ARTIFACTS", os.environ["NDC_DB"] + ".artifacts")


def test_config_loads_and_models_differ():
    cfg = llm.load_llm_config()
    assert cfg.draft.model == "claude-opus-5-5"
    assert cfg.verify.model != cfg.draft.model
    assert cfg.draft.word_range == (140, 190)


def test_same_models_rejected(tmp_path):
    raw = yaml.safe_load(open(os.path.join(os.environ["NDC_CONFIG_DIR"], "llm.yaml")))
    raw["verify"]["model"] = raw["draft"]["model"]
    p = tmp_path / "llm.yaml"
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(llm.ConfigError):
        llm.load_llm_config(p)


def test_prompt_sha_covers_appended_files():
    cfg = llm.load_llm_config()
    text, sha = llm.load_prompt(cfg.draft)
    assert "Styleguide" in text and "Style Guide — nd-content" in text
    import hashlib

    assert sha == hashlib.sha256(text.encode()).hexdigest()


def _request():
    return {
        "model": "claude-opus-5-5",
        "max_tokens": 10,
        "system": "s",
        "messages": [{"role": "user", "content": "hi"}],
    }


def test_call_logs_row_and_artifacts():
    db = Database(os.environ["NDC_DB"])
    client = FakeClient([FakeMessage([{"type": "text", "text": "ok"}])])
    msg, run_id = llm.call(
        "draft",
        _request(),
        prompt_sha="p" * 64,
        input_shas=["a"],
        subject=("topic", 7),
        client=client,
        db=db,
    )
    conn = db.connect()
    row = dict(conn.execute("SELECT * FROM llm_run WHERE id = ?", (run_id,)).fetchone())
    conn.close()
    assert row["stage"] == "draft" and row["prompt_sha256"] == "p" * 64
    assert row["thinking_tokens"] == 100 and row["stop_reason"] == "end_turn"
    assert row["subject_kind"] == "topic" and row["subject_id"] == 7
    assert row["cost_usd"] == pytest.approx((1000 * 4 + 500 * 20) / 1e6)
    req = open(row["request_artifact_path"], "rb").read()
    assert row["request_sha256"] == __import__("hashlib").sha256(req).hexdigest()
    assert json.loads(req)["model"] == "claude-opus-5-5"
    assert b"api_key" not in req.lower() and b"x-api-key" not in req.lower()
    assert os.path.exists(row["response_artifact_path"])


@pytest.mark.parametrize(
    "stop,exc", [("max_tokens", llm.LlmTruncated), ("refusal", llm.LlmRefused)]
)
def test_bad_stop_reason_logged_then_raised(stop, exc):
    db = Database(os.environ["NDC_DB"])
    client = FakeClient([FakeMessage([], stop_reason=stop)])
    with pytest.raises(exc):
        llm.call("draft", _request(), client=client, db=db)
    conn = db.connect()
    assert conn.execute("SELECT stop_reason FROM llm_run").fetchone()[0] == stop
    conn.close()


def test_null_price_gives_null_cost():
    db = Database(os.environ["NDC_DB"])
    client = FakeClient([FakeMessage([{"type": "text", "text": "ok"}])])
    req = _request() | {"model": "claude-sonnet-5-5"}
    _, run_id = llm.call("verify", req, client=client, db=db)
    conn = db.connect()
    assert conn.execute("SELECT cost_usd FROM llm_run WHERE id=?", (run_id,)).fetchone()[0] is None
    conn.close()


def test_missing_key_is_clear_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.LlmError, match="ANTHROPIC_API_KEY"):
        llm._client()
