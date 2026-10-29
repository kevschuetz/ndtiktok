import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "review"))
sys.path.insert(0, str(REPO / "tests" / "recording"))
sys.path.insert(0, str(REPO / "tests" / "script"))

from review_helpers import BLOCKS, EN_A, EN_B, FakeClient, FakeMessage, row, sha_of, verify_with  # noqa: E402

from ndc import readout  # noqa: E402
from ndc.db import Database  # noqa: E402
from ndc.review import store as rstore  # noqa: E402
from ndc.script import draft as d  # noqa: E402
from ndc.sources import store  # noqa: E402
from ndc.sources.pubmed import SentenceRow, SourceMeta  # noqa: E402

FRAMING = dict(kind="framing", verdict="not_applicable")


@pytest.fixture(autouse=True)
def _cfg(tmp_path, monkeypatch):
    """Writable copy of config/ so readout.lock() can write its lock file."""
    d_ = tmp_path / "cfg"
    shutil.copytree(REPO / "config", d_)
    monkeypatch.setenv("NDC_CONFIG_DIR", str(d_))
    monkeypatch.setenv("NDC_ARTIFACTS", os.environ["NDC_DB"] + ".artifacts")
    return d_


@pytest.fixture(autouse=True)
def _idcheck_ok(monkeypatch):
    from ndc.sources import idcheck

    monkeypatch.setattr(idcheck, "ensure_corpus_ok", lambda db, corpus_id: None)
    monkeypatch.setattr(idcheck, "latest_status", lambda conn, sid: ("ok", "2099-01-01T00:00:00Z"))


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
            "'emotion_regulation','nd_adults','myth_vs_research','de','Starke Gefühle',"
            "'whitelist','yes')"
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


@pytest.fixture
def approved_sha(db, version):
    verify_with(db, version, [row(0, **FRAMING), row(1), row(2), row(3, **FRAMING)])
    sha = sha_of(db, version)
    rstore.decide(db, sha, "approved")
    return sha


@pytest.fixture
def locked(db):
    readout.lock(db)
    return True


@pytest.fixture
def rec_cfg(tmp_path):
    from ndc.recording.store import load_config

    base = load_config()
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "take1.m4a").write_bytes(b"\x00fakeaudio")
    cfg = base.__class__(**{**base.__dict__, "recordings_dir": str(rec_dir)})
    return cfg, rec_dir / "take1.m4a"
