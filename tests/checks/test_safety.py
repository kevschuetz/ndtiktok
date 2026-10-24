import pytest

from ndc.checks.engine import check
from ndc.checks.safety import check_safety

LEVELS = ["topic", "script", "claim"]

CASES = [
    ("ADHS-Medikamente im Alltag", "de"),
    ("Methylphenidat und Konzentration", "de"),
    ("Ist mein Kind autistisch?", "de"),
    ("Habe ich ADHS?", "de"),
    ("10 Anzeichen für Autismus", "de"),
    ("Der große ADHS-Selbsttest", "de"),
    ("Was ist ABA?", "de"),
    ("do I have ADHD", "en"),
    ("is my child autistic", "en"),
    ("Adderall and focus", "en"),
    ("signs you have ADHD", "en"),
    ("melatonin for sleep", "en"),
]


@pytest.mark.parametrize("text,lang", CASES)
@pytest.mark.parametrize("level", LEVELS)
def test_blacklisted_subject_blocks(text, lang, level):
    res = check(text, lang, level)
    assert res.status == "blocked"
    assert any(f.source_file == "safety" and f.tier == "block" for f in res.findings)


@pytest.mark.parametrize("text,lang", CASES)
def test_identical_across_levels(text, lang):
    results = [check_safety(text, lang, level) for level in LEVELS]
    assert results[0] and results[0] == results[1] == results[2]


def test_abakus_does_not_block():
    assert check_safety("Der Abakus im Mathematikunterricht", "de", "topic") == []


def test_every_safety_rule_is_block():
    from ndc.checks.rules import load_safety

    rules = load_safety()
    assert rules.rules and all(r.tier == "block" for r in rules.rules)


def test_harmless_topic_ok():
    res = check("ADHS und Morgenroutine mit Kindern", "de", "topic")
    assert res.status == "ok", res.findings
