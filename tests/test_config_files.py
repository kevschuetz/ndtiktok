"""config/hashtags.yaml and config/crisis_lines.yaml (MKT-03, plan 01-14)."""

import re

import pytest

from ndc.checks.engine import check
from ndc.launch_sets import PILLARS, load_crisis_lines, load_hashtags


def test_hashtags_validates():
    hs = load_hashtags()
    assert hs.version >= 1
    assert hs.language in ("de", "en")
    assert hs.scheme.broad == 1
    assert hs.scheme.niche == [1, 2]
    assert hs.scheme.pillar == 1
    assert hs.scheme.total == [3, 5]
    assert 1 <= len(hs.broad) <= 2
    assert hs.niche
    assert set(hs.pillars) == set(PILLARS)
    assert all(hs.pillars[p] for p in PILLARS)
    assert set(hs.keywords) == set(PILLARS)
    assert all(hs.keywords[p] for p in PILLARS)
    for tag in hs.all_tags():
        assert tag.lower() in hs.stats, tag
    assert "verified_in_app" in hs.model_fields_set


def test_every_chosen_tag_passes_safety():
    hs = load_hashtags()
    for tag in hs.all_tags():
        res = check(tag, hs.language, level="topic")
        assert res.status != "blocked", (tag, [f.rule_id for f in res.findings])


def test_actually_autistic_only_in_excluded():
    hs = load_hashtags()
    assert all("actuallyautistic" not in t.lower() for t in hs.all_tags())
    assert any("actuallyautistic" in e.tag.lower() for e in hs.excluded)


def test_crisis_lines_validate():
    cl = load_crisis_lines()
    assert cl.entries
    for e in cl.entries:
        assert e.source_url.startswith("https://")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.verified_at.isoformat())
        assert e.number and e.service and e.country and e.audience and e.hours
    assert any(e.number in cl.short_form for e in cl.entries)


def test_crisis_lines_language_content():
    cl = load_crisis_lines()
    numbers = " | ".join(e.number for e in cl.entries)
    hs = load_hashtags()
    assert cl.language == hs.language
    if cl.language == "de":
        for n in ("142", "147", "0800 111 0 111", "143"):
            assert n in numbers, n
    else:
        for n in ("116 123", "85258", "988"):
            assert n in numbers, n


@pytest.mark.parametrize("bad", ["#Ritalin", "#ADHSMedikamente"])
def test_safety_filter_catches_examples(bad):
    assert check(bad, "de", level="topic").status == "blocked"
