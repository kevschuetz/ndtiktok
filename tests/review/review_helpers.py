import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))

from script_helpers import EN_A, EN_B, FakeClient, FakeMessage, cite, text_block  # noqa: E402

from ndc.script import verify as vf  # noqa: E402

BLOCKS = [
    text_block("Starke Gefühle bei ADHS: was die Forschung zeigt. "),
    text_block(
        "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
        [cite(0, 0, 1, EN_A[0])],
    ),
    text_block(" Auch Kinder mit ADHS zeigen das häufiger.", [cite(1, 0, 1, EN_B[0])]),
    text_block(" Quellen im angepinnten Kommentar."),
]


def row(o, kind="empirical", verdict="supports", esc=False, hidden=False):
    return dict(
        ordinal=o,
        kind=kind,
        verdict=verdict,
        certainty_escalation=esc,
        hidden_claim=hidden,
        note_de="n",
        suggested_fix_de=None,
    )


def verify_with(db, version_id, rows):
    report = vf.VerifyReport(verdicts=[vf.SentenceVerdict(**r) for r in rows])
    vf.verify(db, version_id, client=FakeClient([FakeMessage([], parsed=report)]))


def sha_of(db, version_id):
    conn = db.connect()
    try:
        return conn.execute(
            "SELECT sha256 FROM script_version WHERE id=?", (version_id,)
        ).fetchone()[0]
    finally:
        conn.close()
