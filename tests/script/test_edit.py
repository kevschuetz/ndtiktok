import pytest
from script_helpers import EN_A, FakeClient, FakeMessage, cite, text_block

from ndc.review import store
from ndc.review.gate import gate
from ndc.script import draft as d
from ndc.script import edit
from ndc.script import verify as vf

BLOCKS = [
    text_block("Starke Gefühle bei ADHS: was die Forschung zeigt. "),
    text_block(
        "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
        [cite(0, 0, 1, EN_A[0])],
    ),
    text_block(" Das hängt mit der Ausprägung der Merkmale zusammen.", [cite(0, 1, 2, EN_A[1])]),
    text_block(" Quellen im angepinnten Kommentar."),
]


def _row(o, kind="empirical", verdict="supports"):
    return dict(
        ordinal=o,
        kind=kind,
        verdict=verdict,
        certainty_escalation=False,
        hidden_claim=False,
        note_de="n",
        suggested_fix_de=None,
    )


def _report(ordinals, kinds=None):
    kinds = kinds or {}
    return vf.VerifyReport(
        verdicts=[vf.SentenceVerdict(**_row(o, **kinds.get(o, {}))) for o in ordinals]
    )


FR = {"kind": "framing", "verdict": "not_applicable"}


@pytest.fixture
def v1(db, corpus):
    vid = d.draft(db, corpus, client=FakeClient([FakeMessage(BLOCKS)]))
    vf.verify(
        db, vid, client=FakeClient([FakeMessage([], parsed=_report([0, 1, 2, 3], {0: FR, 3: FR}))])
    )
    conn = db.connect()
    sha = conn.execute("SELECT sha256 FROM script_version WHERE id=?", (vid,)).fetchone()[0]
    conn.close()
    return vid, sha


def test_unchanged_refused(db, v1):
    _, sha = v1
    with pytest.raises(edit.EditError, match="keine Änderung"):
        edit.import_edit(db, edit.export(db, sha))


def test_one_word_change_reverifies_one(db, v1):
    vid, sha = v1
    store.decide(db, sha, "approved")
    text = edit.export(db, sha).replace("hängt mit", "hängt laut Review mit")
    client = FakeClient([FakeMessage([], parsed=_report([2]))])
    res = edit.import_edit(db, text, client=client)
    assert res["reverified"] == 1 and res["reused"] == 3
    body = client.requests[0]["messages"][0]["content"]
    assert "laut Review" in body and "greifen häufiger" not in body
    assert store.latest_decision(db, res["sha256"]) is None
    g = gate(db, res["version_id"])
    assert any(i.kind == "reused" for i in g.warnings)
    assert not gate(db, vid).approvable  # parent is now stale


def test_marker_removed_with_text_change_forced_unsupported(db, v1):
    _, sha = v1
    lines = edit.export(db, sha).splitlines()
    lines[-2] = "Das hängt wohl mit der Ausprägung der Merkmale zusammen."  # marker dropped
    client = FakeClient([FakeMessage([], parsed=_report([2]))])
    res = edit.import_edit(db, "\n".join(lines), client=client)
    conn = db.connect()
    r = conn.execute(
        "SELECT cv.verdict, cv.forced_reason FROM claim_verdict cv JOIN script_sentence "
        "ss ON ss.id=cv.script_sentence_id WHERE ss.script_version_id=? AND ss.ordinal=2",
        (res["version_id"],),
    ).fetchone()
    conn.close()
    assert tuple(r) == ("unsupported", "uncited")


@pytest.mark.parametrize("marker", ["⟦999:0⟧", "⟦12:x⟧"])
def test_bad_markers(db, v1, marker):
    _, sha = v1
    lines = edit.export(db, sha).splitlines()
    lines[-1] = "Quellen im angepinnten Kommentar, bitte. " + marker
    with pytest.raises(edit.EditError):
        edit.import_edit(db, "\n".join(lines), client=FakeClient([]))


def test_stale_parent(db, v1):
    _, sha = v1
    text = edit.export(db, sha)
    edit.import_edit(
        db,
        text.replace("hängt mit", "hängt eng mit"),
        client=FakeClient([FakeMessage([], parsed=_report([2]))]),
    )
    with pytest.raises(edit.EditError, match="veraltet"):
        edit.import_edit(db, text.replace("hängt mit", "hängt stark mit"), client=FakeClient([]))


def test_cli_export_import(runner, db, v1, tmp_path, monkeypatch):
    from ndc.cli import app

    _, sha = v1
    out = tmp_path / "e.txt"
    r = runner.invoke(app, ["script", "export", sha[:12], "-o", str(out)])
    assert r.exit_code == 0
    assert "⟦" in out.read_text()
    out.write_text(out.read_text().replace("hängt mit", "hängt eng mit"))
    monkeypatch.setattr(
        vf.llm, "_client", lambda: FakeClient([FakeMessage([], parsed=_report([2]))])
    )
    r = runner.invoke(app, ["script", "import", str(out)])
    assert r.exit_code == 0, r.output
    assert "1 neu geprüft · 3 übernommen" in r.output
