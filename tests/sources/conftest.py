"""Fixtures for tests/sources (offline HTTP, tmp DB)."""

import os

import httpx
import pytest
from sources_helpers import Router, fixture_bytes

from ndc.db import Database
from ndc.sources import pubmed


@pytest.fixture
def router(monkeypatch):
    r = Router()
    r.add("esummary.fcgi", "36608036", fixture_bytes("esummary_36608036.json"))
    r.add("efetch.fcgi", "36608036", fixture_bytes("efetch_36608036.xml"))
    r.add("esummary.fcgi", "99999999999", fixture_bytes("esummary_bogus.json"))
    pubmed.set_client(httpx.Client(transport=httpx.MockTransport(r.handler)))
    monkeypatch.setattr(pubmed._LIMITER, "wait", lambda interval: None)
    monkeypatch.setenv("NDC_ARTIFACTS", os.path.join(os.environ["NDC_DB"] + ".artifacts"))
    yield r
    pubmed.set_client(None)


@pytest.fixture
def db():
    return Database(os.environ["NDC_DB"])


@pytest.fixture
def topic_id(db):
    conn = db.connect()
    try:
        return conn.execute(
            "INSERT INTO topic (pillar, condition, domain, audience, angle, language, "
            "working_title, list_tag, source_likely) VALUES "
            "('challenge_science_help','adhd','emotion_regulation','adults','science','de',"
            "'Starke Gefühle bei ADHS','whitelist','yes')"
        ).lastrowid
    finally:
        conn.close()


@pytest.fixture
def black_topic_id(db):
    conn = db.connect()
    try:
        return conn.execute(
            "INSERT INTO topic (pillar, condition, domain, audience, angle, language, "
            "working_title, list_tag, source_likely) VALUES "
            "('challenge_science_help','adhd','focus_attention','adults','science','de',"
            "'Medikamente bei ADHS','blacklist','yes')"
        ).lastrowid
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _no_crossref(monkeypatch, request):
    """Offline: DOI checks resolve to ok unless a test opts in to the real checker."""
    if "real_idcheck" in request.keywords:
        return
    from ndc.sources import idcheck

    monkeypatch.setattr(idcheck, "_check_doi", lambda src: ("ok", src["title"], src["year"], ""))


def pytest_configure(config):
    config.addinivalue_line("markers", "real_idcheck: run the real DOI checker (offline mocks)")
