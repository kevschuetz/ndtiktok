import time
from pathlib import Path

import pytest

from ndc.checks.engine import check
from ndc.checks.terminology import check_terminology

FIX = Path(__file__).resolve().parent.parent / "fixtures"


def _rules(findings):
    return {(f.rule_id, f.tier) for f in findings}


def _by_rule(findings, rule_id):
    return [f for f in findings if f.rule_id == rule_id]


@pytest.mark.parametrize(
    "text,rule_id,tier",
    [
        ("Er leidet an ADHS.", "de.leiden_an", "warn"),
        ("Sie litt unter Autismus.", "de.leiden_an", "warn"),
        ("Er hat jahrelang darunter gelitten.", "de.leiden_an", "warn"),
        ("Sie leidet seit Jahren an ADHS.", "de.leiden_an", "warn"),
        ("Bei hochfunktionalen Autisten ist das anders.", "de.hochfunktional", "block"),
        ("Das sind ihre Superkräfte.", "de.superkraft", "warn"),
        ("Das Asperger-Syndrom wurde gestrichen.", "any.asperger", "warn"),
        ("Man wollte ihm das Stimming abgewöhnen.", "de.aba_framing", "block"),
        ("Die ABA-Therapie ist umstritten.", "any.aba", "block"),
        ("Angewandte Verhaltensanalyse ist umstritten.", "de.aba_framing", "block"),
        ("Menschen mit Autismus erleben das oft.", "de.person_first", "warn"),
        ("Autisten erleben das oft.", "de.autisten", "warn"),
        ("Schwerer Autismus wird anders beschrieben.", "de.hochfunktional", "block"),
    ],
)
def test_must_flag_de(text, rule_id, tier):
    assert (rule_id, tier) in _rules(check_terminology(text, "de"))


@pytest.mark.parametrize(
    "text,rule_id,tier",
    [
        ("He suffers from ADHD.", "en.suffer_from", "warn"),
        ("She is high-functioning.", "any.functioning_en", "block"),
        ("ADHD is my superpower.", "any.superpower", "warn"),
        ("He was told he has Asperger's.", "any.asperger", "warn"),
        ("They tried applied behavior analysis.", "en.aba_framing", "block"),
        ("A person with autism may notice this.", "en.person_first", "warn"),
        ("Teachers tried to stop stimming.", "en.aba_framing", "block"),
    ],
)
def test_must_flag_en(text, rule_id, tier):
    assert (rule_id, tier) in _rules(check_terminology(text, "en"))


def test_person_first_suggests_identity_first():
    de = _by_rule(check_terminology("Menschen mit Autismus", "de"), "de.person_first")
    assert de and "autistische Menschen" in de[0].suggest
    en = _by_rule(check_terminology("person with autism", "en"), "en.person_first")
    assert en and "autistic people" in en[0].suggest


def test_autisten_suggestion_mentions_noun_case():
    f = _by_rule(check_terminology("Autisten", "de"), "de.autisten")
    assert f and "autistische Menschen" in f[0].suggest and "Autist:innen" in f[0].suggest


def test_autist_colon_innen_and_neutral_spectrum_not_flagged():
    text = "Autist:innen und eine Person im Autismus-Spektrum."
    rules = {f.rule_id for f in check_terminology(text, "de")}
    assert "de.autisten" not in rules
    assert "de.gender_form" not in rules
    assert "de.person_first" not in rules


def test_other_gender_colon_warns_with_neutral_suggestion():
    f = _by_rule(check_terminology("Viele Lehrer:innen wissen das.", "de"), "de.gender_form")
    assert f and f[0].tier == "warn" and f[0].suggest


def test_menschen_mit_adhs_not_flagged():
    assert check_terminology("Manche Menschen mit ADHS erleben Zeit anders.", "de") == []


def test_quoted_asperger_not_flagged():
    findings = check_terminology("Früher sagte man „Asperger“.", "de")
    assert not _by_rule(findings, "any.asperger")


def test_unbalanced_quote_is_unquoted():
    findings = check_terminology("Früher sagte man „Asperger.", "de")
    assert _by_rule(findings, "any.asperger")


def test_abakus_not_aba():
    assert not _by_rule(check_terminology("Der Abakus ist alt.", "de"), "any.aba")


def test_span_points_at_matched_text():
    text = "Er leidet an ADHS."
    f = _by_rule(check_terminology(text, "de"), "de.leiden_an")[0]
    assert text[f.span[0] : f.span[1]] == f.matched_text
    assert f.source_file == "terminology"


@pytest.mark.parametrize(
    "name,lang", [("sample_script_de.txt", "de"), ("sample_script_en.txt", "en")]
)
def test_sample_scripts_cover_every_category(name, lang):
    res = check((FIX / name).read_text(encoding="utf-8"), lang, "script")
    cats = {f.category for f in res.findings}
    assert {"functioning_label", "hype", "pathologizing", "outdated", "aba_framing"} <= cats
    assert res.status == "blocked"
    # exactly one unquoted Asperger occurrence; the quoted one must not flag
    assert len([f for f in res.findings if f.rule_id == "any.asperger"]) == 1


@pytest.mark.parametrize("name,lang", [("precision_de.txt", "de"), ("precision_en.txt", "en")])
def test_precision_corpus_has_no_block(name, lang):
    lines = [x for x in (FIX / name).read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) >= 15
    for line in lines:
        res = check(line, lang, "script")
        blocks = [f for f in res.findings if f.tier == "block"]
        assert blocks == [], (line, blocks)


def test_long_input_is_fast():
    text = ("Manche Menschen mit ADHS erleben Zeit anders, und das ist okay. " * 200)[:10000]
    t0 = time.perf_counter()
    check(text, "de", "script")
    assert time.perf_counter() - t0 < 1.0
