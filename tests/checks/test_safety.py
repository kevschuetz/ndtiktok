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


# CR-01 (Phase 1 code review): ordinary phrasings that passed safety.yaml v1. Each must block.
KNOWN_FALSE_NEGATIVES = [
    ("Signs of ADHD in women", "en"),
    ("symptoms of autism in adults", "en"),
    ("Could I have ADHD?", "en"),
    ("how to get diagnosed with ADHD as an adult", "en"),
    ("ADHD test online", "en"),
    ("ADHD drugs and your brain", "en"),
    ("Should you get a prescription?", "en"),
    ("Wellbutrin for ADHD", "en"),
    ("self harm and autism", "en"),
    ("I want to end my life", "en"),
    ("aba therapy", "en"),
    ("magnesium for ADHD", "en"),
    ("Bin ich Autist?", "de"),
    ("Könnte ich ADHS haben?", "de"),
    ("Wie bekomme ich eine ADHS-Diagnose?", "de"),
    ("ADHS-Test für Erwachsene", "de"),
    ("Binge Eating und ADHS", "de"),
    ("Psychopharmaka bei Autismus", "de"),
    ("Arzneimittel gegen ADHS", "de"),
    ("Ritalins Wirkung", "de"),
    ("Vitamin D bei ADHS", "de"),
    ("Ich will mich umbringen", "de"),
    ("Medi­kamente", "de"),
    # variants of the same gaps
    ("self-harm and autism", "en"),
    ("Medi​kamente gegen ADHS", "de"),
    ("Concertas Nebenwirkungen", "de"),
]


@pytest.mark.parametrize("text,lang", KNOWN_FALSE_NEGATIVES)
def test_known_false_negatives(text, lang):
    findings = check_safety(text, lang, "topic")
    assert any(f.tier == "block" for f in findings), text
    assert check(text, lang, "topic").status == "blocked"


def test_obfuscated_span_maps_to_original_text():
    text = "Neue Medi­kamente"
    f = check_safety(text, "de", "script")[0]
    assert text[f.span[0] : f.span[1]] == f.matched_text
    assert f.matched_text == "Medi­kamente"


# Approved wording (style guide hedging/disclaimers/identity terms) must stay block-free.
APPROVED_SAFE = [
    ("Kein Ersatz für ärztliche oder psychotherapeutische Beratung.", "de"),
    ("Ich bin kein Therapeut – ich lese die Forschung und übersetze sie.", "de"),
    ("Not a substitute for medical or psychotherapeutic advice.", "en"),
    ("I'm not a therapist — I read the research and translate it.", "en"),
    ("Manche Menschen mit ADHS erleben Zeit anders.", "de"),
    ("Eine Person im Autismus-Spektrum kann Geräusche stärker wahrnehmen.", "de"),
    ("Nach der Diagnose fühlen sich manche Erwachsene erleichtert.", "de"),
    ("After the diagnosis, some adults feel relieved.", "en"),
    ("That doesn't mean it's the same for everyone.", "en"),
    ("Was kann ich als Vater bei ADHS im Alltag tun?", "de"),
    ("How can you support a partner with ADHD?", "en"),
]


@pytest.mark.parametrize("text,lang", APPROVED_SAFE)
def test_approved_wording_has_no_block(text, lang):
    res = check(text, lang, "script")
    assert [f for f in res.findings if f.tier == "block"] == [], text
