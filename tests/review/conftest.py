import os

import pytest
from review_helpers import BLOCKS, EN_A, EN_B, FakeClient, FakeMessage  # noqa: E402

from ndc.db import Database
from ndc.script import draft as d
from ndc.sources import store
from ndc.sources.pubmed import SentenceRow, SourceMeta


@pytest.fixture(autouse=True)
def _artifacts(monkeypatch):
    monkeypatch.setenv("NDC_ARTIFACTS", os.environ["NDC_DB"] + ".artifacts")


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


@pytest.fixture
def version(db):
    conn = db.connect()
    try:
        tid = conn.execute(
            "INSERT INTO topic (pillar, condition, domain, audience, angle, language, "
            "working_title, list_tag, source_likely) VALUES ('challenge_science_help','adhd',"
            "'emotion_regulation','nd_adults','science','de','Starke Gefühle','whitelist','yes')"
        ).lastrowid
    finally:
        conn.close()
    a = store.store_snapshot(
        db,
        SourceMeta(
            "pubmed",
            "Paper A",
            pmid="36608036",
            doi="10.1371/journal.pone.0280131",
            authors=["Soler-Gutiérrez", "X"],
            year=2023,
            journal="PLoS One",
        ),
        [SentenceRow(t, "Abstract") for t in EN_A],
        "pubmed_abstract",
    )
    b = store.store_snapshot(
        db,
        SourceMeta(
            "pubmed",
            "Paper B",
            pmid="27180913",
            authors=["Graziano", "Y"],
            year=2016,
            journal="Clin Psychol Rev",
        ),
        [SentenceRow(t, "Abstract") for t in EN_B],
        "pubmed_abstract",
    )
    store.pick(db, tid, a)
    store.pick(db, tid, b)
    store.lock_corpus(db, tid)
    return d.draft(db, tid, client=FakeClient([FakeMessage(BLOCKS)]))


@pytest.fixture(autouse=True)
def _idcheck_ok(monkeypatch):
    """Offline: treat every source as verified (idcheck has its own tests)."""
    from ndc.sources import idcheck

    monkeypatch.setattr(idcheck, "ensure_corpus_ok", lambda db, corpus_id: None)
    monkeypatch.setattr(idcheck, "latest_status", lambda conn, sid: ("ok", "2099-01-01T00:00:00Z"))
