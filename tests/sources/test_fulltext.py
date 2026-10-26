import pytest
from sources_helpers import fixture_bytes

from ndc.sources import fulltext


def test_plos_fulltext_sections():
    rows = fulltext.jats_to_sentences(fixture_bytes("fulltext_PMC9821724.xml"))
    tops = {r.section.split(" › ")[0] for r in rows}
    assert tops <= {"Abstract", "Introduction", "Results", "Discussion"}
    assert {"Abstract", "Introduction", "Results", "Discussion"} <= tops
    assert 150 <= len(rows) <= 300
    joined = " ".join(r.text for r in rows)
    assert "Funding" not in joined
    assert "[]" not in joined and "()" not in joined
    assert any("›" in r.section for r in rows)


def test_methods_variants_dropped():
    xml = b"""<article><front><article-meta><abstract><p>Adults with ADHD were studied
    carefully.</p></abstract></article-meta></front><body>
    <sec><title>Materials and methods</title><p>We recruited many participants here.</p></sec>
    <sec><title>2. Results</title><p>Scores differed between groups <xref>[4]</xref> clearly.
    </p></sec></body></article>"""
    rows = fulltext.jats_to_sentences(xml)
    assert [r.section for r in rows] == ["Abstract", "Results"]
    assert rows[1].text == "Scores differed between groups clearly."


def test_entity_refused():
    with pytest.raises(fulltext.FullTextError):
        fulltext.jats_to_sentences(b'<!DOCTYPE a [<!ENTITY x "y">]><article/>')
