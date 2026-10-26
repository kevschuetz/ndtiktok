import sqlite3

import pytest
from sources_helpers import esummary_json

from ndc.sources import pubmed, store
from ndc.sources.pubmed import SentenceRow, SourceMeta


def _meta(pmid="1", title="Paper one", doi=None):
    return SourceMeta(kind="pubmed", title=title, pmid=pmid, doi=doi, authors=["A", "B"], year=2020)


ROWS = [
    SentenceRow("First sentence is here.", "Abstract"),
    SentenceRow("Second one too.", "Abstract"),
]


def test_snapshot_sha_stable_and_sensitive():
    a = store.snapshot_sha256(ROWS)
    assert a == store.snapshot_sha256([SentenceRow(r.text, r.section) for r in ROWS])
    assert a != store.snapshot_sha256([SentenceRow(ROWS[0].text, "Results"), ROWS[1]])
    # NFC: decomposed umlaut hashes like composed
    assert store.snapshot_sha256([SentenceRow("Gefühle sind stark.")]) == store.snapshot_sha256(
        [SentenceRow("Gefühle sind stark.")]
    )


def test_store_is_idempotent_and_immutable(db, router):
    s1 = store.store_snapshot(db, _meta(), ROWS, "pubmed_abstract", b"<x/>")
    s2 = store.store_snapshot(db, _meta(), ROWS, "pubmed_abstract", b"<x/>")
    assert s1 == s2
    s3 = store.store_snapshot(
        db, _meta(), ROWS[:1] + [SentenceRow("Changed text now.")], "pubmed_abstract"
    )
    assert s3 != s1
    conn = db.connect()
    try:
        assert conn.execute("SELECT count(*) FROM source").fetchone()[0] == 1
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE source_sentence SET text = 'x' WHERE snapshot_id = ?", (s1,))
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM source_snapshot WHERE id = ?", (s1,))
    finally:
        conn.close()


def test_lock_corpus_bounds_and_reuse(db, router, topic_id):
    a = store.store_snapshot(db, _meta("1"), ROWS, "pubmed_abstract")
    store.pick(db, topic_id, a)
    with pytest.raises(store.StoreError, match="topic has 1"):
        store.lock_corpus(db, topic_id)
    b = store.store_snapshot(
        db, _meta("2", "Paper two"), [SentenceRow("Other paper text here.")], "pubmed_abstract"
    )
    store.pick(db, topic_id, b)
    c1 = store.lock_corpus(db, topic_id)
    assert store.lock_corpus(db, topic_id) == c1
    for i in range(3, 6):
        s = store.store_snapshot(
            db,
            _meta(str(i), f"Paper {i}"),
            [SentenceRow(f"Text of paper {i} here.")],
            "pubmed_abstract",
        )
        store.pick(db, topic_id, s)
    s6 = store.store_snapshot(
        db, _meta("6", "Paper 6"), [SentenceRow("Sixth paper text here.")], "pubmed_abstract"
    )
    with pytest.raises(store.StoreError, match="already has 5"):
        store.pick(db, topic_id, s6)
    conn = db.connect()
    try:
        cites = [
            r[0]
            for r in conn.execute(
                "SELECT short_cite FROM corpus_source WHERE corpus_id = ? ORDER BY position", (c1,)
            )
        ]
        sha = conn.execute("SELECT sha256 FROM corpus WHERE id = ?", (c1,)).fetchone()[0]
    finally:
        conn.close()
    assert cites == ["A et al. 2020", "A et al. 2020"]
    assert len(sha) == 64


def test_blacklisted_topic_refused(db, router, black_topic_id):
    a = store.store_snapshot(db, _meta("1"), ROWS, "pubmed_abstract")
    with pytest.raises(store.StoreError, match="not whitelisted"):
        store.pick(db, black_topic_id, a)


def test_cli_add_show_lock(runner, router, topic_id, db):
    from ndc.cli import app

    router.add("esummary.fcgi", "27180913", esummary_json("27180913", "Second"))
    router.add(
        "efetch.fcgi",
        "27180913",
        (
            b'<?xml version="1.0"?><PubmedArticleSet><PubmedArticle><MedlineCitation><Article>'
            b"<Journal><ISOAbbreviation>Clin Psychol Rev</ISOAbbreviation><JournalIssue><PubDate>"
            b"<Year>2016</Year></PubDate></JournalIssue></Journal><ArticleTitle>Second.</ArticleTitle>"
            b"<Abstract><AbstractText>Children with ADHD show emotion dysregulation often."
            b"</AbstractText>"
            b"</Abstract><AuthorList><Author><LastName>Graziano</LastName></Author></AuthorList>"
            b"</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
        ),
    )
    r = runner.invoke(app, ["source", "add", "--pmid", "36608036", "--topic", str(topic_id)])
    assert r.exit_code == 0, r.output
    snap = int(r.output.split()[1].rstrip(":"))
    r2 = runner.invoke(app, ["source", "add", "--pmid", "36608036", "--topic", str(topic_id)])
    assert r2.output.split()[1].rstrip(":") == str(snap)
    r = runner.invoke(app, ["source", "show", str(snap)])
    assert "[0]" in r.output
    r = runner.invoke(app, ["corpus", "lock", str(topic_id)])
    assert r.exit_code == 1
    r = runner.invoke(app, ["source", "add", "--pmid", "27180913", "--topic", str(topic_id)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["corpus", "lock", str(topic_id)])
    assert r.exit_code == 0, r.output
    import re

    assert re.search(r"sha256 [0-9a-f]{64}", r.output)


def test_cli_add_unknown_pmid(runner, router, topic_id):
    from ndc.cli import app

    r = runner.invoke(app, ["source", "add", "--pmid", "99999999999", "--topic", str(topic_id)])
    assert r.exit_code == 1
    assert "not found" in r.output
    _ = pubmed
