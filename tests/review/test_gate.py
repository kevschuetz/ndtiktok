import pytest
from review_helpers import row, sha_of, verify_with

from ndc.review import gate as g
from ndc.review import store

FRAMING = dict(kind="framing", verdict="not_applicable")


def _rows(mid1="supports", mid2="supports", esc=False):
    return [
        row(0, **FRAMING),
        row(1, verdict=mid1, esc=esc),
        row(2, verdict=mid2),
        row(3, **FRAMING),
    ]


def test_unverified_blocks(db, version):
    res = g.gate(db, version)
    assert not res.approvable and any(i.kind == "unverified" for i in res.blockers)


def test_all_supported_is_approvable(db, version):
    verify_with(db, version, _rows())
    res = g.gate(db, version)
    assert res.approvable, (res.blockers, res.needs_ack)


@pytest.mark.parametrize("verdict", ["unsupported", "contradicts"])
def test_blocking_verdicts(db, version, verdict):
    verify_with(db, version, _rows(mid1=verdict))
    res = g.gate(db, version)
    assert not res.approvable and [i.sentence_ordinal for i in res.blockers] == [1]


@pytest.mark.parametrize(
    "kw", [dict(mid1="overstated"), dict(mid1="partial"), dict(mid1="supports", esc=True)]
)
def test_needs_ack_then_approvable(db, version, kw):
    verify_with(db, version, _rows(**kw))
    res = g.gate(db, version)
    assert not res.approvable and [i.sentence_ordinal for i in res.needs_ack] == [1]
    store.ack(db, sha_of(db, version), 1, note="ok so")
    assert g.gate(db, version).approvable


def test_ack_for_other_sha_does_not_count(db, version):
    verify_with(db, version, _rows(mid1="overstated"))
    conn = db.connect()
    conn.execute(
        "INSERT INTO claim_ack (script_sha256, sentence_ordinal, reviewer, channel) "
        "VALUES ('f'||substr(?,2), 1, 'op', 'cli')",
        (sha_of(db, version),),
    )
    conn.close()
    assert not g.gate(db, version).approvable


def test_word_count_is_warning_only(db, version):
    verify_with(db, version, _rows())
    res = g.gate(db, version)
    assert res.approvable and any(i.kind == "word_count" for i in res.warnings)


def test_hooks_merge(db, version, monkeypatch):
    verify_with(db, version, _rows())
    monkeypatch.setattr(
        g,
        "GATE_HOOKS",
        [lambda conn, vid: [g.Issue("block_test", None, "x"), g.Issue("warn_test", None, "y")]],
    )
    res = g.gate(db, version)
    assert not res.approvable
    assert [i.kind for i in res.blockers] == ["block_test"]
    assert "warn_test" in [i.kind for i in res.warnings]


def test_risk_order_sorting(db, version):
    verify_with(db, version, _rows(mid1="supports", mid2="overstated"))
    conn = db.connect()
    cs = g.sorted_cards(g.cards(conn, version))
    conn.close()
    assert [c.ordinal for c in cs] == [2, 1, 0, 3]
    assert list(g.RISK_ORDER) == [
        "contradicts",
        "unsupported",
        "overstated",
        "partial",
        "escalation",
        "supports",
        "not_applicable",
    ]
