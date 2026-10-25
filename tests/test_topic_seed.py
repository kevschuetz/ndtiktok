"""The real reviewed topic seed (plan 01-15, CONT-01/CONT-04, D-09..D-11, D-19)."""

import re
from collections import Counter
from pathlib import Path

import pytest

from ndc import topics
from ndc.checks.engine import check

SEED = Path(__file__).resolve().parent.parent / "config" / "topic_seed.yaml"
DECIDED_LANGUAGE = "de"  # docs/language-decision.md, verdict R1
CORE = {"adhd", "autism", "audhd", "nd_general"}


@pytest.fixture(scope="module")
def seed():
    return topics._parse_seed(SEED)  # vocab + strict-key validation, raises on any error


def _text(t):
    return t.working_title + "\n" + t.summary


def test_seed_parses_in_decided_language(seed):
    assert seed.language == DECIDED_LANGUAGE
    assert seed.version == 1


def test_seed_size_and_pillar_balance(seed):
    assert 60 <= len(seed.topics) <= 80
    counts = Counter(t.pillar for t in seed.topics)
    assert set(counts) == set(topics.load_matrix().pillar)
    assert max(counts.values()) - min(counts.values()) <= 4


def test_broader_nd_conditions(seed):
    extra = {t.condition for t in seed.topics} - CORE
    assert len(extra) >= 4


def test_non_s3_conditions_flagged_pubmed_reviews(seed):
    m = topics.load_matrix()
    for t in seed.topics:
        if t.list_tag == "whitelist" and m.condition[t.condition].guideline_layer != "awmf_s3":
            assert t.notes and "pubmed_reviews" in t.notes, t.working_title


def test_blacklist_examples_blocked_and_cover_required_subjects(seed):
    black = [t for t in seed.topics if t.list_tag == "blacklist"]
    assert len(black) >= 6
    categories = set()
    for t in black:
        res = check(_text(t), lang=seed.language, level="topic")
        assert res.status == "blocked", t.working_title
        categories |= {f.category for f in res.findings if f.tier == "block"}
    assert {"medication", "diagnosis_question", "aba"} <= categories
    assert any(re.search(r"ist mein kind autistisch", t.working_title.lower()) for t in black)


def test_no_whitelist_topic_blocked(seed):
    for t in seed.topics:
        if t.list_tag != "whitelist":
            continue
        res = check(_text(t), lang=seed.language, level="topic")
        assert res.status != "blocked", (t.working_title, res.findings)
        assert not [f for f in res.findings if f.tier == "block"], t.working_title


def test_working_titles_unique(seed):
    titles = [t.working_title for t in seed.topics]
    assert len(titles) == len(set(titles))


def test_matrix_spread(seed):
    wl = [t for t in seed.topics if t.list_tag == "whitelist"]
    assert {t.angle for t in wl} == set(topics.load_matrix().angle)
    assert {"men", "dads", "partners"} <= {t.audience for t in wl}
