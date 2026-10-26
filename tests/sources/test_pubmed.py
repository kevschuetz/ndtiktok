import pytest

from ndc.sources import pubmed
from sources_helpers import fixture_bytes


def test_fetch_abstract_parses_metadata(router):
    meta, rows, raw = pubmed.fetch_abstract("36608036")
    assert meta.title == (
        "Evidence of emotion dysregulation as a core symptom of adult ADHD: A systematic review."
    )
    assert meta.doi == "10.1371/journal.pone.0280131"
    assert meta.pmcid == "PMC9821724"
    assert meta.year == 2023
    assert "Systematic Review" in meta.pubtypes
    assert meta.authors[0] == "Soler-Gutiérrez"
    assert len(rows) >= 8
    assert all(r.section == "Abstract" for r in rows)
    assert raw.startswith(b"<?xml")


def test_labelled_abstract_sections():
    xml = b"""<?xml version="1.0"?><PubmedArticleSet><PubmedArticle><MedlineCitation>
    <Article><Journal><ISOAbbreviation>J Test</ISOAbbreviation><JournalIssue><PubDate>
    <Year>2021</Year></PubDate></JournalIssue></Journal><ArticleTitle>T.</ArticleTitle>
    <Abstract><AbstractText Label="BACKGROUND">Adults with ADHD were studied here.</AbstractText>
    <AbstractText Label="RESULTS">The effect was small but consistent.</AbstractText></Abstract>
    <PublicationTypeList><PublicationType>Review</PublicationType></PublicationTypeList>
    </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    meta, rows = pubmed.parse_efetch(xml, "1")
    assert [r.section for r in rows] == ["BACKGROUND", "RESULTS"]
    assert meta.year == 2021


@pytest.mark.parametrize("name", ["efetch_retracted_pubtype.xml", "efetch_retracted_comment.xml"])
def test_retracted_refused(name):
    with pytest.raises(pubmed.RetractedSource):
        pubmed.parse_efetch(fixture_bytes(name), "36608036")


def test_esummary_error_is_not_found(router):
    with pytest.raises(pubmed.SourceNotFound):
        pubmed.fetch_abstract("99999999999")


def test_entity_xml_refused():
    with pytest.raises(pubmed.SourceNotFound):
        pubmed.parse_efetch(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>', "1")
