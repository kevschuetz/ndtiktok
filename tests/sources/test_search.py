import json

import pytest

from ndc.sources import europepmc, pubmed, search


def _summ(pmid, title, pubtypes, year="2020", pmc=None):
    ids = [{"idtype": "pubmed", "value": pmid}]
    if pmc:
        ids.append({"idtype": "pmc", "value": pmc})
    return {"uid": pmid, "title": title, "pubdate": year, "pubtype": pubtypes, "articleids": ids}


SUMM = {
    "1": _summ("1", "Primary study of emotion in ADHD.", ["Journal Article"], "2024"),
    "2": _summ(
        "2", "Systematic review of emotion dysregulation.", ["Systematic Review"], pmc="PMC2"
    ),
    "3": _summ("3", "Narrative review of emotion.", ["Review"]),
    "4": _summ("4", "Clinical guideline for ADHD.", ["Practice Guideline"]),
    "5": _summ("5", "Using stimulants to treat emotional lability.", ["Review"]),
    "6": _summ("6", "Second primary study here.", ["Journal Article"]),
    "7": _summ("7", "Emotion regulation training: a meta-analysis.", ["Meta-Analysis"]),
}


@pytest.fixture
def fake_apis(monkeypatch):
    calls = []

    def esearch(term, retmax):
        calls.append(term)
        if "intervention*[ti]" in term:  # help facet clause (title-level since 042ef27)
            return ["7"] if "systematic[sb]" in term else []
        if "mechanism*[tiab]" in term:
            return []
        return ["2", "3", "4", "5"] if "systematic[sb]" in term else ["1", "2", "6"]

    monkeypatch.setattr(pubmed, "esearch", esearch)
    monkeypatch.setattr(pubmed, "esummary", lambda ids: {i: SUMM[i] for i in ids})
    monkeypatch.setattr(europepmc, "oa_status", lambda ids: {"2": {"is_oa": True, "pmcid": "PMC2"}})
    return calls


def _topic(db, topic_id):
    conn = db.connect()
    try:
        return conn.execute("SELECT * FROM topic WHERE id=?", (topic_id,)).fetchone()
    finally:
        conn.close()


def test_build_query_mesh_domain_and_exclusions(db, topic_id):
    cfg = search.load_cfg()
    q = search.build_query(_topic(db, topic_id), cfg)
    assert '"Attention Deficit Disorder with Hyperactivity"[MeSH]' in q
    assert '"emotion regulation"[tiab]' in q
    assert q.endswith(cfg["exclusions"])
    q2 = search.build_query(_topic(db, topic_id), cfg, "my own terms")
    assert q2.startswith("(my own terms)") and q2.endswith(cfg["exclusions"])


def test_search_ranks_evidence_first_and_caches(db, topic_id, fake_apis):
    run_id = search.search(db, topic_id)
    assert len(fake_apis) == 6  # 3 facets x (evidence + primary)
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM source_candidate WHERE search_run_id=? ORDER BY rank", (run_id,)
    ).fetchall()
    conn.close()
    pmids = [r["pmid"] for r in rows]
    assert set(pmids) == {"1", "2", "3", "4", "5", "6", "7"}
    facets = {r["pmid"]: json.loads(r["facets_json"]) for r in rows}
    assert facets["7"] == ["help"] and facets["2"] == ["phenomenon"]
    tiers = {r["pmid"]: r["tier"] for r in rows}
    assert tiers == {
        "1": "primary",
        "2": "SR/MA",
        "3": "review",
        "4": "guideline",
        "5": "review",
        "6": "primary",
        "7": "SR/MA",
    }
    pos = {p: i for i, p in enumerate(pmids)}
    assert pos["4"] < pos["3"] and pos["2"] < pos["3"]  # guideline, SR/MA above review
    assert max(pos["3"], pos["5"]) < min(pos["1"], pos["6"])  # reviews above primary
    oa = {r["pmid"]: r["is_oa"] for r in rows}
    assert oa["2"] == 1 and oa["1"] == 0
    flags = {r["pmid"]: r["safety_flag"] for r in rows}
    assert flags["5"] and "stimulant" in flags["5"]
    assert flags["2"] is None
    assert json.loads(rows[0]["pubtypes_json"])


def test_oa_failure_degrades(db, topic_id, fake_apis, monkeypatch):
    def boom(ids):
        raise RuntimeError("503")

    monkeypatch.setattr(europepmc, "oa_status", boom)
    run_id = search.search(db, topic_id)
    conn = db.connect()
    vals = {
        r[0]
        for r in conn.execute("SELECT is_oa FROM source_candidate WHERE search_run_id=?", (run_id,))
    }
    conn.close()
    assert vals == {None}


def test_rank_deterministic():
    cfg = search.load_cfg()
    a = [search.Candidate(str(i), f"t{i}", 2020, ["Review"], None, None, i) for i in range(8)]
    r1 = [c.pmid for c in search.rank(list(a), cfg)]
    r2 = [c.pmid for c in search.rank(list(reversed(a)), cfg)]
    assert r1 == r2


def test_cli_search_and_pick(runner, db, topic_id, fake_apis, router, monkeypatch):
    from sources_helpers import fixture_bytes

    from ndc.cli import app

    r = runner.invoke(app, ["source", "search", str(topic_id)])
    assert r.exit_code == 0, r.output
    assert "query:" in r.output
    # pick rank of pmid 2 (OA) -> abstract from router (reuse 36608036 fixtures) + full text
    conn = db.connect()
    rk = conn.execute("SELECT rank FROM source_candidate WHERE pmid='2'").fetchone()[0]
    conn.close()
    router.add(
        "esummary.fcgi", "2", fixture_bytes("esummary_36608036.json").replace(b'"36608036"', b'"2"')
    )
    router.add("efetch.fcgi", "2", fixture_bytes("efetch_36608036.xml"))
    monkeypatch.setattr(
        europepmc, "fulltext_xml", lambda pmcid: fixture_bytes("fulltext_PMC9821724.xml")
    )
    r = runner.invoke(app, ["source", "pick", str(topic_id), str(rk)])
    assert r.exit_code == 0, r.output
    assert "Volltext" in r.output and "Sätze" in r.output
    r = runner.invoke(app, ["source", "pick", str(topic_id), "99"])
    assert r.exit_code == 1


def test_missing_help_facet_warns(db, topic_id, fake_apis):
    from ndc.sources import store
    from ndc.sources.pubmed import SentenceRow, SourceMeta

    search.search(db, topic_id)
    s2 = store.store_snapshot(
        db, SourceMeta("pubmed", "x", pmid="2"), [SentenceRow("A b c d.")], "pubmed_abstract"
    )
    store.pick(db, topic_id, s2)
    conn = db.connect()
    assert search.missing_facets(conn, topic_id) == ["help"]
    conn.close()
    s7 = store.store_snapshot(
        db, SourceMeta("pubmed", "y", pmid="7"), [SentenceRow("E f g h.")], "pubmed_abstract"
    )
    store.pick(db, topic_id, s7)
    conn = db.connect()
    assert search.missing_facets(conn, topic_id) == []
    conn.close()
