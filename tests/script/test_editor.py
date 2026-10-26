import pytest
from script_helpers import EN_A, FakeClient, FakeMessage, cite, text_block

from ndc.script import draft as d
from ndc.script import edit, editor
from ndc.script import verify as vf

BLOCKS = [
    text_block("Starke Gefühle bei ADHS: was die Forschung zeigt. "),
    text_block(
        "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
        [cite(0, 0, 1, EN_A[0])],
    ),
    text_block(" Quellen im angepinnten Kommentar."),
]


@pytest.fixture
def v1(db, corpus):
    return d.draft(db, corpus, client=FakeClient([FakeMessage(BLOCKS)]))


def _editor_reply(db, vid, mutate):
    conn = db.connect()
    sha = conn.execute("SELECT sha256 FROM script_version WHERE id=?", (vid,)).fetchone()[0]
    conn.close()
    lines = edit.export(db, sha).splitlines()
    return FakeMessage([text_block("\n".join(mutate(lines)))])


def _report(n):
    return vf.VerifyReport(
        verdicts=[
            vf.SentenceVerdict(
                ordinal=i,
                kind="empirical",
                verdict="supports",
                certainty_escalation=False,
                hidden_claim=False,
                note_de="n",
                suggested_fix_de=None,
            )
            for i in range(n)
        ]
    )


def test_punch_creates_verified_latest_version(db, v1):
    def mutate(lines):
        body = [ln for ln in lines if not ln.startswith("#")]
        body[0] = "Du explodierst innerlich – und weißt nicht warum."
        return [lines[0], *body]

    client = FakeClient([_editor_reply(db, v1, mutate), FakeMessage([], parsed=_report(3))])
    res = editor.punch(db, v1, client=client)
    assert res["version_id"] != v1
    assert client.requests[0]["model"] == "claude-opus-5-5"
    conn = db.connect()
    n = conn.execute(
        "SELECT count(*) FROM claim_verdict cv JOIN script_sentence ss "
        "ON ss.id=cv.script_sentence_id WHERE ss.script_version_id=?",
        (res["version_id"],),
    ).fetchone()[0]
    conn.close()
    assert n == 3


def test_invented_marker_refused(db, v1):
    def mutate(lines):
        return lines[:-1] + [lines[-1] + " ⟦1:2⟧"]

    with pytest.raises(editor.PunchError, match="invented"):
        editor.punch(db, v1, client=FakeClient([_editor_reply(db, v1, mutate)]))


def test_markdown_refused(db, v1):
    def mutate(lines):
        return [lines[0], "**Hook:** Gefühle bei ADHS sind laut.", *lines[1:]]

    with pytest.raises(editor.PunchError):
        editor.punch(db, v1, client=FakeClient([_editor_reply(db, v1, mutate)]))
