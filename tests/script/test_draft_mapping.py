import pytest
from script_helpers import EN_A, EN_B, FakeClient, FakeMessage, cite, text_block

from ndc import llm
from ndc.script import draft as d


def _msg(blocks, stop="end_turn"):
    return FakeMessage(blocks, stop_reason=stop)


GOOD = [
    text_block("Kennst du das, wenn Gefühle mit voller Wucht kommen? "),
    text_block(
        "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
        [cite(0, 0, 1, EN_A[0])],
    ),
    text_block(" "),
    text_block("Die Studienlage ist dünn und uneinheitlich.", [cite(0, 2, 3, EN_A[2])]),
    text_block(
        " Auch Kinder mit ADHS zeigen das öfter, in mittlerer Stärke.",
        [cite(1, 0, 2, EN_B[0] + " " + EN_B[1])],
    ),
    text_block(" Quellen im angepinnten Kommentar."),
]


def _ids(db, snap_pos, ordinals):
    conn = db.connect()
    try:
        snap = conn.execute(
            "SELECT snapshot_id FROM corpus_source WHERE position=?", (snap_pos,)
        ).fetchone()[0]
        return {
            conn.execute(
                "SELECT id FROM source_sentence WHERE snapshot_id=? AND ordinal=?", (snap, o)
            ).fetchone()[0]
            for o in ordinals
        }
    finally:
        conn.close()


def test_build_request_shape(db, corpus):
    conn = db.connect()
    docs = d.load_corpus(conn, 1)
    topic = conn.execute("SELECT * FROM topic WHERE id=?", (corpus,)).fetchone()
    conn.close()
    cfg = llm.load_llm_config()
    req = d.build_draft_request(docs, topic, cfg.draft, "SYS")
    content = req["messages"][0]["content"]
    assert [c["type"] for c in content] == ["document", "document", "text"]
    assert content[0]["source"]["type"] == "content"
    assert [b["text"] for b in content[0]["source"]["content"]] == EN_A
    assert content[0]["citations"] == {"enabled": True}
    assert "cache_control" in content[1] and "cache_control" not in content[0]
    assert req["output_config"] == {"effort": "high"} and "thinking" not in req
    assert content[0]["title"] == "Soler et al. 2023"


def test_map_citations_exclusive_end_and_multiblock(db, corpus):
    conn = db.connect()
    docs = d.load_corpus(conn, 1)
    conn.close()
    text, sents = d.map_citations(_msg(GOOD), docs)
    assert text.startswith("Kennst du das")
    assert len(sents) == 5
    assert sents[0].cited == set()
    assert sents[1].cited == _ids(db, 0, [0])
    assert sents[2].cited == _ids(db, 0, [2])
    assert sents[3].cited == _ids(db, 1, [0, 1])
    assert sents[4].cited == set()


def test_cited_text_mismatch_aborts(db, corpus):
    conn = db.connect()
    docs = d.load_corpus(conn, 1)
    conn.close()
    bad = [
        text_block(
            "Erwachsene mit ADHS greifen häufiger zu Strategien.",
            [cite(0, 0, 1, "Something the source never said.")],
        )
    ]
    with pytest.raises(d.CitationMismatch):
        d.map_citations(_msg(bad), docs)
    out_of_range = [
        text_block("Erwachsene mit ADHS greifen häufiger zu Strategien.", [cite(0, 2, 9, EN_A[2])])
    ]
    with pytest.raises(d.CitationMismatch):
        d.map_citations(_msg(out_of_range), docs)


def test_draft_stores_version(db, corpus):
    client = FakeClient([_msg(GOOD)])
    vid = d.draft(db, corpus, client=client)
    conn = db.connect()
    v = conn.execute("SELECT * FROM script_version WHERE id=?", (vid,)).fetchone()
    n_sent = conn.execute(
        "SELECT count(*) FROM script_sentence WHERE script_version_id=?", (vid,)
    ).fetchone()[0]
    n_cit = conn.execute("SELECT count(*) FROM script_citation").fetchone()[0]
    run = conn.execute(
        "SELECT stage, prompt_sha256 FROM llm_run WHERE id=?", (v["llm_run_id"],)
    ).fetchone()
    conn.close()
    assert v["version_no"] == 1 and v["origin"] == "draft" and len(v["sha256"]) == 64
    assert v["check_status"] in ("ok", "needs_override", "blocked")
    assert v["word_count"] == len(v["text"].split())
    assert n_sent == 5 and n_cit == 4
    assert run["stage"] == "draft" and len(run["prompt_sha256"]) == 64


@pytest.mark.parametrize(
    "blocks",
    [
        [text_block("# Titel\nErwachsene mit ADHS greifen häufiger zu Strategien.")],
        [text_block("**Hook:** Gefühle bei ADHS sind manchmal sehr stark.")],
        [text_block("Einleitung hier.\n- erster Punkt in der Liste\n- zweiter Punkt hier")],
    ],
)
def test_markdown_rejected(db, corpus, blocks):
    with pytest.raises(d.DraftError, match="Markdown"):
        d.draft(db, corpus, client=FakeClient([_msg(blocks)]))
    conn = db.connect()
    assert conn.execute("SELECT count(*) FROM script_version").fetchone()[0] == 0
    conn.close()


def test_truncated_not_stored(db, corpus):
    with pytest.raises(llm.LlmTruncated):
        d.draft(db, corpus, client=FakeClient([_msg(GOOD, stop="max_tokens")]))
    conn = db.connect()
    assert conn.execute("SELECT count(*) FROM script_version").fetchone()[0] == 0
    conn.close()


def test_medication_sentence_blocks(db, corpus):
    blocks = GOOD[:2] + [
        text_block(
            " Medikamente wie Methylphenidat helfen dabei sehr gut.", [cite(0, 1, 2, EN_A[1])]
        )
    ]
    vid = d.draft(db, corpus, client=FakeClient([_msg(blocks)]))
    conn = db.connect()
    st = conn.execute("SELECT check_status FROM script_version WHERE id=?", (vid,)).fetchone()[0]
    conn.close()
    assert st == "blocked"
