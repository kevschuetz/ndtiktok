import json

import httpx
import pytest
from sources_helpers import esummary_json, fixture_bytes

from ndc.review import gate as g
from ndc.script import draft
from ndc.sources import idcheck, store
from ndc.sources.pubmed import SentenceRow, SourceMeta

TITLE = "Evidence of emotion dysregulation as a core symptom of adult ADHD: A systematic review."
DOI = "10.1371/journal.pone.0280131"


@pytest.fixture
def crossref(monkeypatch):
    def handler(request):
        if request.url.path.endswith(DOI):
            return httpx.Response(200, content=fixture_bytes("crossref_pone0280131.json"))
        if "/works/" in request.url.path and request.url.path.endswith("2022"):
            msg = {"message": {"title": [TITLE], "issued": {"date-parts": [[2020]]}}}
            return httpx.Response(200, content=json.dumps(msg).encode())
        return httpx.Response(404, content=b"Resource not found.")

    idcheck.set_client(httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(idcheck._LIMITER, "wait", lambda i: None)
    yield
    idcheck.set_client(None)


def _src(db, **kw):
    meta = SourceMeta(
        **(
            {
                "kind": "pubmed",
                "title": TITLE,
                "pmid": "36608036",
                "doi": DOI,
                "authors": ["Soler-Gutiérrez", "X"],
                "year": 2023,
            }
            | kw
        )
    )
    snap = store.store_snapshot(
        db, meta, [SentenceRow(f"Sentence about {kw} here.")], "pubmed_abstract"
    )
    conn = db.connect()
    sid = conn.execute("SELECT source_id FROM source_snapshot WHERE id=?", (snap,)).fetchone()[0]
    conn.close()
    return sid, snap


def _statuses(db, sid):
    conn = db.connect()
    rows = {
        r["identifier_kind"]: (r["status"], r["detail"])
        for r in conn.execute("SELECT * FROM id_check WHERE source_id=? ORDER BY id", (sid,))
    }
    conn.close()
    return rows


@pytest.mark.real_idcheck
def test_real_pmid_and_doi_ok(db, router, crossref):
    sid, _ = _src(db)
    assert idcheck.check_source(db, sid) == "ok"
    assert {k: v[0] for k, v in _statuses(db, sid).items()} == {"pmid": "ok", "doi": "ok"}


@pytest.mark.real_idcheck
def test_wrong_title_mismatch(db, router, crossref):
    sid, _ = _src(db, title="Something else entirely about cats")
    assert idcheck.check_source(db, sid) == "mismatch"


@pytest.mark.real_idcheck
def test_fake_doi_unresolvable(db, router, crossref):
    sid, _ = _src(db, pmid=None, doi="10.1371/journal.pone.9999999")
    assert idcheck.check_source(db, sid) == "unresolvable"


@pytest.mark.real_idcheck
def test_bogus_pmid_unresolvable(db, router, crossref):
    sid, _ = _src(db, pmid="99999999999", doi=None)
    assert idcheck.check_source(db, sid) == "unresolvable"


@pytest.mark.real_idcheck
def test_year_tolerance(db, router, crossref):
    sid, _ = _src(db, pmid=None, doi="10.1/x2022", year=2022)
    assert idcheck.check_source(db, sid) == "mismatch"  # Crossref 2020 vs stored 2022
    sid2, _ = _src(db, pmid=None, doi="10.1/y2022", year=2021)
    assert idcheck.check_source(db, sid2) == "ok"  # 2020 vs 2021


@pytest.mark.real_idcheck
def test_pubmed_doi_differs(db, router, crossref):
    router.add("esummary.fcgi", "555", esummary_json("555", TITLE, "2023", doi="10.9/other"))
    sid, _ = _src(db, pmid="555")
    assert idcheck.check_source(db, sid) == "mismatch"
    assert "doi differs" in _statuses(db, sid)["pmid"][1]


@pytest.mark.real_idcheck
def test_transport_error_fails_closed(db, monkeypatch):
    from ndc.sources import pubmed

    def boom(ids):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(pubmed, "esummary", boom)
    sid, _ = _src(db, doi=None)
    assert idcheck.check_source(db, sid) == "error"


def test_awmf_manual_no_network(db):
    sid, _ = _src(
        db,
        kind="awmf",
        pmid=None,
        doi=None,
        awmf_reg_no="028-045",
        awmf_version="2.0",
        title="ADHS",
    )
    assert idcheck.check_source(db, sid) == "manual"
    assert _statuses(db, sid)["awmf"][0] == "manual"


@pytest.mark.real_idcheck
def test_draft_refused_before_llm_and_gate_blocks(db, router, crossref, topic_id):
    good, s1 = _src(db)
    bad, s2 = _src(db, pmid=None, doi="10.1371/journal.pone.9999999", title="Fake paper")
    store.pick(db, topic_id, s1)
    store.pick(db, topic_id, s2)
    store.lock_corpus(db, topic_id)

    class Never:
        @property
        def messages(self):
            raise AssertionError("LLM must not be called")

    with pytest.raises(idcheck.IdCheckFailed, match="Fake|unresolvable"):
        draft.draft(db, topic_id, client=Never())
    conn = db.connect()
    conn.execute("INSERT INTO script (topic_id, corpus_id) VALUES (?, 1)", (topic_id,))
    conn.execute(
        "INSERT INTO script_version (script_id, version_no, text, sha256, word_count, "
        "origin, check_status, check_json) VALUES (1,1,'x','ab',1,'draft','ok','{}')"
    )
    conn.execute(
        "INSERT INTO script_sentence (script_version_id, ordinal, text, char_start, "
        "char_end, sha256) VALUES (1,0,'x',0,1,'s')"
    )
    src_sent = conn.execute("SELECT id FROM source_sentence WHERE snapshot_id=?", (s2,)).fetchone()[
        0
    ]
    conn.execute("INSERT INTO script_citation VALUES (1, ?)", (src_sent,))
    issues = idcheck.idcheck_gate_issues(conn, 1)
    conn.close()
    assert [i.kind for i in issues] == ["block_idcheck"]
    assert idcheck.idcheck_gate_issues in g.GATE_HOOKS
