import pytest
from recording_helpers import FakeTranscriber

from ndc.recording import align as al
from ndc.recording import store as rs

APPROVED = [
    "Starke Gefühle bei ADHS: was die Forschung zeigt.",
    "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
    "Auch Kinder mit ADHS zeigen das häufiger.",
    "Quellen im angepinnten Kommentar.",
]
HEDGES = ["häufig", "manche", "könnte", "deuten darauf hin"]


def _statuses(spoken, **kw):
    return [(a.status, a.reason) for a in al.align(spoken, APPROVED, hedge_tokens=HEDGES, **kw)]


def test_identical_take_all_match():
    assert all(s == "match" for s, _ in _statuses(APPROVED))


def test_fillers_and_word_order_pass():
    spoken = [
        "Starke Gefühle bei ADHS – was die Forschung zeigt.",
        "Also, Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien, ähm.",
        "Auch Kinder mit ADHS zeigen das häufiger.",
        "Quellen im angepinnten Kommentar.",
    ]
    assert all(s == "match" for s, _ in _statuses(spoken))


def test_dropped_hedge_is_deviation_even_when_similar():
    spoken = list(APPROVED)
    spoken[2] = "Auch Kinder mit ADHS zeigen das."
    st = _statuses(spoken)
    assert st[2][0] == "deviation" and st[2][1].startswith("hedge_dropped:häufig")


def test_changed_claim_wording_is_deviation():
    spoken = list(APPROVED)
    spoken[1] = "Erwachsene mit ADHS sind häufiger einfach schlecht organisiert im Leben."
    st = _statuses(spoken)
    assert st[1][0] == "deviation" and st[1][1].startswith("similarity:")


def test_extra_and_missing_sentences():
    spoken = [APPROVED[0], APPROVED[1], "Und das ist mir persönlich wirklich wichtig.", APPROVED[3]]
    st = _statuses(spoken)
    assert sorted(s for s, _ in st) == sorted(["match", "match", "extra", "missing", "match"])
    assert st[0][0] == "match" and st[-1][0] == "match"


def test_merged_spoken_sentences_align_to_one_approved():
    spoken = [
        APPROVED[0],
        "Erwachsene mit ADHS greifen häufiger.",
        "Zu wenig hilfreichen Strategien.",
        APPROVED[2],
        APPROVED[3],
    ]
    res = al.align(spoken, APPROVED, hedge_tokens=HEDGES)
    pairs = [(a.status, a.spoken_ordinals, a.approved_ordinals) for a in res]
    assert ("match", [1, 2], [1]) in pairs


def test_split_keep_all_keeps_fragments():
    assert al.split_keep_all("Das ist ein Test. Ja. Und noch ein ganzer Satz hier.") == [
        "Das ist ein Test. Ja.",
        "Und noch ein ganzer Satz hier.",
    ]


def test_add_recording_persists_alignment(db, approved_sha, rec_cfg):
    cfg, path = rec_cfg
    spoken = [APPROVED[0], APPROVED[1], "Auch Kinder mit ADHS zeigen das.", APPROVED[3]]
    res = rs.add_recording(db, path, approved_sha, transcriber=FakeTranscriber(spoken), cfg=cfg)
    assert res["match"] == 3 and res["deviation"] == 1 and res["extra"] == 0 and res["missing"] == 0
    conn = db.connect()
    r = conn.execute("SELECT * FROM recording WHERE id=?", (res["recording_id"],)).fetchone()
    assert (
        r["transcript_sha256"] == res["transcript_sha256"]
        and r["whisper_model"] == cfg.whisper_model
    )
    assert r["transcript_final"].startswith(APPROVED[0]) and "zeigen das." in r["transcript_final"]
    rows = rs.sentences(conn, r["id"])
    assert (
        rows[2]["status"] == "deviation"
        and rows[2]["start_s"] is not None
        and rows[2]["end_s"] > rows[2]["start_s"]
    )
    assert (
        rows[0]["final_text"] == APPROVED[0]
        and rows[2]["final_text"] == "Auch Kinder mit ADHS zeigen das."
    )
    with pytest.raises(Exception, match="immutable"):
        conn.execute("UPDATE recording SET file_name='x'")
    conn.close()
    with pytest.raises(rs.RecordingError, match="existiert bereits"):
        rs.add_recording(
            db,
            path,
            approved_sha,
            transcriber=FakeTranscriber(spoken),
            cfg=cfg,
        )


def test_add_recording_refuses_outside_dir_and_unapproved(
    db, approved_sha, version, rec_cfg, tmp_path
):

    cfg, path = rec_cfg
    outside = tmp_path / "elsewhere.m4a"
    outside.write_bytes(b"x")
    with pytest.raises(rs.RecordingError, match="muss unter"):
        rs.add_recording(
            db,
            outside,
            approved_sha,
            transcriber=FakeTranscriber(APPROVED),
            cfg=cfg,
        )
    # an unapproved version of another script
    with pytest.raises(rs.RecordingError):
        rs.add_recording(
            db,
            path,
            "0" * 64,
            transcriber=FakeTranscriber(APPROVED),
            cfg=cfg,
        )


def test_cli_add_show_list(runner, db, approved_sha, rec_cfg, monkeypatch):
    from ndc.cli import app
    from ndc.recording import store as st

    cfg, path = rec_cfg
    monkeypatch.setattr(st, "load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(st, "_default_transcriber", lambda c: FakeTranscriber(APPROVED))
    r = runner.invoke(
        app, ["recording", "add", str(path), "--script", approved_sha[:12], "--force"]
    )
    assert r.exit_code == 0, r.output
    assert "match 4" in r.output
    sha = r.output.split("transcript sha ")[1].split()[0]
    r = runner.invoke(app, ["recording", "show", sha])
    assert r.exit_code == 0 and "match" in r.output and "Skript :" in r.output
    r = runner.invoke(app, ["recording", "list"])
    assert r.exit_code == 0 and "match 4" in r.output
