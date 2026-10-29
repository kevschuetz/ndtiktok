"""config/moderation.yaml + src/ndc/moderation.py (OPS-01, plan 03-02)."""

import pytest
import yaml
from pydantic import ValidationError

from ndc import moderation
from ndc.config import config_dir


def test_loads_and_has_required_replies():
    mod = moderation.load_moderation()
    assert mod.policies.auto_reply == "never" and mod.policies.advice == "none"
    assert set(moderation.REQUIRED_REPLIES) <= set(mod.replies)
    assert mod.spike_protocol.trigger_multiple_of_median_views == 10
    assert mod.spike_protocol.sweeps_per_day == 2 and mod.spike_protocol.duration_hours == 72


def test_every_reply_passes_check_and_is_short():
    mod = moderation.load_moderation()
    rows = moderation.validate_replies(mod)
    assert rows and all(st != "blocked" for _, st, _ in rows)
    for r in mod.replies.values():
        assert r.text is None or len(r.text) <= moderation.MAX_REPLY_CHARS


def test_crisis_numbers_in_sync():
    assert moderation.crisis_numbers_in_sync()


def test_loader_rejects_auto_reply_and_long_text(tmp_path):
    data = yaml.safe_load((config_dir() / "moderation.yaml").read_text(encoding="utf-8"))
    bad = dict(data)
    bad["policies"] = dict(data["policies"], auto_reply="llm")
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(bad, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValidationError):
        moderation.load_moderation(p)
    bad = dict(data)
    bad["replies"] = dict(data["replies"], thank_you={"when": "x", "text": "a" * 151})
    p.write_text(yaml.safe_dump(bad, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValidationError, match="longer"):
        moderation.load_moderation(p)
    bad = dict(data)
    bad["unknown_key"] = 1
    p.write_text(yaml.safe_dump(bad, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValidationError):
        moderation.load_moderation(p)


def test_render_contains_everything():
    text = moderation.render_playbook()
    assert text.startswith("<!-- generated from config/moderation.yaml")
    assert (
        "nie automatisch" in text and "Spike" in text and "142" in text and "0800 111 0 111" in text
    )
    for key in moderation.REQUIRED_REPLIES:
        assert f"### {key}" in text


def test_cli_check_and_render(runner, tmp_path):
    from ndc.cli import app

    r = runner.invoke(app, ["moderation", "check"])
    assert r.exit_code == 0 and "in sync" in r.output and "crisis_disclosure" in r.output
    out = tmp_path / "pb.md"
    r = runner.invoke(app, ["moderation", "render", "--out", str(out)])
    assert r.exit_code == 0 and out.exists() and "Playbook" in out.read_text(encoding="utf-8")
