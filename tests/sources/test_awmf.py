import pymupdf
import pytest

from ndc.sources import awmf, store
from ndc.sources.pubmed import SentenceRow, SourceMeta


def make_pdf(pages=4, extra="") -> bytes:
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        p = doc.new_page()
        lines = [
            "S3-Leitlinie ADHS - Langfassung",
            f"Erster Satz auf Seite {n} beschreibt Psycho-",
            f"edukation bei Erwachsenen mit ADHS genau. Zweiter Satz auf Seite {n} {extra}nennt",
            "ADHS- und Autismus-Diagnostik als getrennte Themen. "
            "Dritter Satz auf dieser Seite folgt.",
            f"Seite {n} von {pages}",
        ]
        y = 72
        for ln in lines:
            p.insert_text((72, y), ln, fontsize=9)
            y += 14
    data = doc.tobytes()
    doc.close()
    return data


KW = dict(
    register="028-045",
    version="2.0 (Langfassung)",
    valid_until="2027-05-01",
    status="gueltig",
    title="ADHS bei Kindern, Jugendlichen und Erwachsenen",
)


def test_import_cleans_and_pages(db, topic_id):
    snap = awmf.import_awmf(db, make_pdf(), topic_id=topic_id, **KW)
    conn = db.connect()
    rows = conn.execute(
        "SELECT page, text FROM source_sentence WHERE snapshot_id=? ORDER BY ordinal", (snap,)
    ).fetchall()
    src = conn.execute(
        "SELECT s.* FROM source s JOIN source_snapshot ss ON ss.source_id=s.id WHERE ss.id=?",
        (snap,),
    ).fetchone()
    conn.close()
    assert len(rows) == 12
    assert [r["page"] for r in rows] == [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4]
    joined = " ".join(r["text"] for r in rows)
    assert "Psychoedukation" in joined
    assert "ADHS- und Autismus-Diagnostik" in joined
    assert "Langfassung" not in joined and "von 4" not in joined
    assert src["kind"] == "awmf" and src["awmf_status"] == "gueltig"
    assert src["awmf_valid_until"] == "2027-05-01"
    assert awmf.import_awmf(db, make_pdf(), **KW) == snap  # same bytes -> same snapshot


@pytest.mark.parametrize(
    "override,match",
    [
        ({"register": "28-45"}, "Registernummer"),
        ({"valid_until": "31.12.2026"}, "ISO"),
        ({"status": "ok"}, "status"),
    ],
)
def test_invalid_args_write_nothing(db, override, match):
    with pytest.raises(awmf.AwmfError, match=match):
        awmf.import_awmf(db, make_pdf(), **(KW | override))
    conn = db.connect()
    assert conn.execute("SELECT count(*) FROM source").fetchone()[0] == 0
    conn.close()


def test_non_pdf_refused(db):
    with pytest.raises(awmf.AwmfError, match="PDF"):
        awmf.import_awmf(db, b"hello", **KW)


def test_same_version_different_pdf_needs_flag(db):
    awmf.import_awmf(db, make_pdf(), **KW)
    with pytest.raises(awmf.AwmfError, match="--new-version"):
        awmf.import_awmf(db, make_pdf(extra="geändert "), **KW)


def test_gate_warning_for_outdated(db):
    snap = awmf.import_awmf(db, make_pdf(), **(KW | {"status": "in_ueberarbeitung"}))
    conn = db.connect()
    sid = conn.execute(
        "SELECT id FROM source_sentence WHERE snapshot_id=? AND ordinal=0", (snap,)
    ).fetchone()[0]
    tid = conn.execute(
        "INSERT INTO topic (pillar, condition, domain, audience, angle, language, "
        "working_title, list_tag, source_likely) VALUES ('parents','adhd','sleep',"
        "'parents','science','de','T','whitelist','yes')"
    ).lastrowid
    conn.close()
    other = store.store_snapshot(
        db,
        SourceMeta("pubmed", "P", pmid="9", authors=["A"], year=2020),
        [SentenceRow("Some other text here.")],
        "pubmed_abstract",
    )
    store.pick(db, tid, snap)
    store.pick(db, tid, other)
    cid = store.lock_corpus(db, tid)
    conn = db.connect()
    conn.execute("INSERT INTO script (topic_id, corpus_id) VALUES (?,?)", (tid, cid))
    conn.execute(
        "INSERT INTO script_version (script_id, version_no, text, sha256, word_count, "
        "origin, check_status, check_json) VALUES (1,1,'x','a'||hex(randomblob(31)),1,"
        "'draft','ok','{}')"
    )
    conn.execute(
        "INSERT INTO script_sentence (script_version_id, ordinal, text, char_start, "
        "char_end, sha256) VALUES (1,0,'x',0,1,'s')"
    )
    conn.execute("INSERT INTO script_citation VALUES (1, ?)", (sid,))
    issues = awmf.awmf_gate_issues(conn, 1)
    conn.close()
    assert [i.message_de for i in issues] == ["AWMF-Leitlinie 028-045 in Überarbeitung"]
    assert issues[0].kind.startswith("warn")


@pytest.mark.parametrize(
    "status,until,exp",
    [
        ("abgelaufen", "2030-01-01", True),
        ("gueltig", "2021-09-30", True),
        ("in_ueberarbeitung", "2030-01-01", False),
        ("gueltig", "2030-01-01", False),
    ],
)
def test_expired_detection(status, until, exp):
    assert awmf.expired(status, until, today="2026-10-26") is exp


def test_expired_guideline_warns_not_blocks(db):
    from ndc.review.gate import Issue

    issues_kind = "warn_awmf_expired"
    assert not issues_kind.startswith("block")
    assert Issue(issues_kind, None, "x").kind == issues_kind


def test_pick_snapshot_cli(runner, db, topic_id):
    from ndc.cli import app

    snap = awmf.import_awmf(db, make_pdf(), **KW)
    r = runner.invoke(app, ["source", "pick-snapshot", str(topic_id), str(snap)])
    assert r.exit_code == 0, r.output
