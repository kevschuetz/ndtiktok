import os

import pytest
import yaml
from script_helpers import EN_A, FakeClient, FakeMessage, cite, text_block

from ndc import llm
from ndc.script import draft as d
from ndc.script import verify as vf

BLOCKS = [
    text_block("Starke Gefühle bei ADHS: was die Forschung zeigt. "),
    text_block(
        "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
        [cite(0, 0, 1, EN_A[0])],
    ),
    text_block(" Die Forschung ist sich hier völlig einig."),
    text_block(" Das hängt mit der Schwere der Symptome zusammen.", [cite(0, 1, 2, EN_A[1])]),
    text_block(" Quellen im angepinnten Kommentar."),
]


@pytest.fixture
def version(db, corpus):
    return d.draft(db, corpus, client=FakeClient([FakeMessage(BLOCKS)]))


def _report(rows):
    return vf.VerifyReport(verdicts=[vf.SentenceVerdict(**r) for r in rows])


def _row(o, kind="empirical", verdict="supports", esc=False, hidden=False):
    return dict(
        ordinal=o,
        kind=kind,
        verdict=verdict,
        certainty_escalation=esc,
        hidden_claim=hidden,
        note_de="n",
        suggested_fix_de=None,
    )


def test_request_contains_only_sentences_and_sources(db, version):
    cfg = llm.load_llm_config()
    conn = db.connect()
    sents = vf._sentences(conn, version)
    conn.close()
    system, _ = llm.load_prompt(cfg.verify)
    req = vf.build_verify_request(sents, cfg.verify, system)
    body = req["messages"][0]["content"]
    assert EN_A[0] in body and "kontext_danach" in body
    draft_first_line = (
        open(os.path.join(os.environ["NDC_CONFIG_DIR"], "prompts/draft_de.md")).readline().strip()
    )
    assert draft_first_line not in body and draft_first_line not in req["system"]
    assert req["model"] == cfg.verify.model != cfg.draft.model


def test_forcing_and_storage(db, version):
    rows = [
        _row(0, kind="framing", verdict="not_applicable"),
        _row(1, verdict="overstated", esc=True),
        _row(2, kind="framing", verdict="not_applicable", hidden=True),
        _row(3, verdict="supports"),
        _row(4, kind="framing", verdict="not_applicable"),
    ]
    client = FakeClient([FakeMessage([], parsed=_report(rows))])
    run = vf.verify(db, version, client=client)
    assert run is not None
    conn = db.connect()
    got = {
        r["ordinal"]: (r["verdict"], r["forced_reason"], r["model_verdict"])
        for r in conn.execute(
            "SELECT ss.ordinal, cv.* FROM claim_verdict cv JOIN script_sentence ss "
            "ON ss.id = cv.script_sentence_id WHERE ss.script_version_id=?",
            (version,),
        )
    }
    conn.close()
    assert got[0] == ("not_applicable", None, "not_applicable")
    assert got[1] == ("overstated", None, "overstated")
    assert got[2] == ("unsupported", "hidden_claim", "not_applicable")
    assert got[3] == ("supports", None, "supports")
    # second run is a no-op
    assert vf.verify(db, version, client=FakeClient([])) is None


def test_uncited_empirical_forced(db, version):
    rows = [_row(i) for i in range(5)]
    rows[2] = _row(2, kind="empirical", verdict="supports")  # uncited sentence 2
    vf.verify(db, version, client=FakeClient([FakeMessage([], parsed=_report(rows))]))
    conn = db.connect()
    r = conn.execute(
        "SELECT cv.verdict, cv.forced_reason FROM claim_verdict cv JOIN script_sentence "
        "ss ON ss.id=cv.script_sentence_id WHERE ss.ordinal=2"
    ).fetchone()
    conn.close()
    assert tuple(r) == ("unsupported", "uncited")


def test_missing_ordinal_stores_nothing(db, version):
    rows = [_row(i) for i in range(4)]
    with pytest.raises(vf.VerifyIncomplete):
        vf.verify(db, version, client=FakeClient([FakeMessage([], parsed=_report(rows))]))
    conn = db.connect()
    assert conn.execute("SELECT count(*) FROM claim_verdict").fetchone()[0] == 0
    conn.close()


def test_extra_fields_forbidden():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        vf.SentenceVerdict(**_row(0), extra="x")


def test_reuse_key_stability():
    a = vf.reuse_key("Satz.", [3, 1], "p", "m")
    assert a == vf.reuse_key("Satz.", [1, 3], "p", "m")
    assert a != vf.reuse_key("Satz!", [1, 3], "p", "m")
    assert a != vf.reuse_key("Satz.", [1, 3], "q", "m")


def test_same_model_config_rejected(tmp_path):
    raw = yaml.safe_load(open(os.path.join(os.environ["NDC_CONFIG_DIR"], "llm.yaml")))
    raw["verify"]["model"] = raw["draft"]["model"]
    p = tmp_path / "llm.yaml"
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(llm.ConfigError):
        llm.load_llm_config(p)
