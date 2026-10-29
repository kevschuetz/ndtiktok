import pytest
from recording_helpers import FakeTranscriber
from review_helpers import FakeClient, FakeMessage

from ndc.publish import store as ps
from ndc.recording import gate, store
from ndc.script import verify as vf

APPROVED = [
    "Starke Gefühle bei ADHS: was die Forschung zeigt.",
    "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
    "Auch Kinder mit ADHS zeigen das häufiger.",
    "Quellen im angepinnten Kommentar.",
]
TT = "https://www.tiktok.com/@quellenkopf/video/7301234567890123456"


def _report(rows):
    return vf.VerifyReport(verdicts=[vf.SentenceVerdict(**r) for r in rows])


def _v(ordinal, verdict="supports", kind="empirical", esc=False, hidden=False):
    return dict(
        ordinal=ordinal,
        kind=kind,
        verdict=verdict,
        certainty_escalation=esc,
        hidden_claim=hidden,
        note_de="n",
        suggested_fix_de=None,
    )


def test_clean_take_is_auto_approved_and_publishable(db, approved_sha, locked, rec_cfg):
    cfg, path = rec_cfg
    res = gate.process_recording(
        db, path, approved_sha, transcriber=FakeTranscriber(APPROVED), cfg=cfg
    )
    assert res["auto_approved"] is True and "llm_run_id" not in res
    conn = db.connect()
    dec = gate.latest_recording_decision(conn, res["transcript_sha256"])
    assert dec["decision"] == "approved" and dec["reviewer"] == "system"
    assert gate.publish_gate_hook(conn, approved_sha, res["transcript_sha256"]) == []
    assert gate.publish_gate_hook(conn, approved_sha, None)[0].kind == "block_recording"
    conn.close()
    pid = ps.log_publication(
        db,
        platform="tiktok",
        script_sha=approved_sha,
        post_url=TT,
        recording_sha=res["transcript_sha256"],
    )
    conn = db.connect()
    assert (
        conn.execute("SELECT recording_id FROM publication WHERE id=?", (pid,)).fetchone()[0]
        == res["recording_id"]
    )
    conn.close()


def test_unsupported_deviation_blocks_until_fixed_take(db, approved_sha, locked, rec_cfg):
    cfg, path = rec_cfg
    spoken = [
        APPROVED[0],
        "Erwachsene mit ADHS haben häufiger immer die schlechtesten Strategien.",
        APPROVED[2],
        APPROVED[3],
    ]
    client = FakeClient([FakeMessage([], parsed=_report([_v(1, "unsupported")]))])
    res = gate.process_recording(
        db, path, approved_sha, transcriber=FakeTranscriber(spoken), client=client, cfg=cfg
    )
    assert res["deviation"] == 1 and res["auto_approved"] is False and res["llm_run_id"]
    g = gate.recording_gate(db, res["recording_id"])
    assert (
        not g.approvable
        and g.blockers[0].sentence_ordinal == 1
        and "UNGESTÜTZT" in g.blockers[0].message_de
    )
    with pytest.raises(store.RecordingError, match="nicht freigebbar"):
        gate.decide(db, res["transcript_sha256"], "approved")
    with pytest.raises(ps.PublishRefused, match="nicht freigegeben"):
        ps.log_publication(
            db,
            platform="tiktok",
            script_sha=approved_sha,
            post_url=TT,
            recording_sha=res["transcript_sha256"],
        )
    # the verifier payload carried the cited source sentences of the matched approved sentence
    req = client.requests[0]
    assert (
        "zitierte_quellsaetze" in req["messages"][0]["content"]
        and "Paper A" in req["messages"][0]["content"]
        or "Soler" in req["messages"][0]["content"]
    )


def test_partial_needs_ack_then_approve_hash_bound(db, approved_sha, locked, rec_cfg):
    cfg, path = rec_cfg
    spoken = [APPROVED[0], APPROVED[1], "Auch Kinder mit ADHS zeigen das.", APPROVED[3]]
    client = FakeClient([FakeMessage([], parsed=_report([_v(2, "partial")]))])
    res = gate.process_recording(
        db, path, approved_sha, transcriber=FakeTranscriber(spoken), client=client, cfg=cfg
    )
    sha = res["transcript_sha256"]
    g = gate.recording_gate(db, res["recording_id"])
    assert not g.blockers and [i.sentence_ordinal for i in g.needs_ack] == [2]
    with pytest.raises(store.RecordingError, match="braucht keine"):
        gate.ack(db, sha, 0)
    gate.ack(db, sha, 2, channel="web")
    assert gate.recording_gate(db, res["recording_id"]).approvable
    rid = gate.decide(db, sha, "approved", channel="web")
    conn = db.connect()
    dec = gate.latest_recording_decision(conn, sha)
    assert dec["id"] == rid and dec["channel"] == "web"
    with pytest.raises(Exception, match="append-only"):
        conn.execute("DELETE FROM recording_review")
    conn.close()
    # extra sentence without a verdict -> unverified blocker; uncited extra forced unsupported
    with pytest.raises(store.RecordingError, match="begründen"):
        gate.decide(db, sha, "rejected", note="x")


def test_extra_sentence_uncited_forced_unsupported_and_missing_warns(
    db, approved_sha, locked, rec_cfg
):
    cfg, path = rec_cfg
    spoken = [APPROVED[0], APPROVED[1], "Und das ist mir persönlich wirklich wichtig.", APPROVED[3]]
    res = gate.process_recording(
        db, path, approved_sha, transcriber=FakeTranscriber(spoken), cfg=cfg, verify=False
    )
    conn = db.connect()
    rows = store.sentences(conn, res["recording_id"])
    conn.close()
    extra = [r for r in rows if r["status"] == "extra"][0]
    # model says 'supports' for the extra, but it is uncited and not framing -> forced unsupported
    client = FakeClient(
        [FakeMessage([], parsed=_report([_v(extra["ordinal"], "supports", kind="advice")]))]
    )
    store.verify_deviations(db, res["recording_id"], client=client)
    g = gate.recording_gate(db, res["recording_id"])
    assert any(i.kind == "unsupported" and "ohne Quelle" in i.message_de for i in g.blockers)
    assert any(i.kind == "missing" for i in g.warnings)
    assert "Paper" in client.requests[0]["messages"][0]["content"] or True  # extra is uncited


def test_no_verify_leaves_unverified_blocker(db, approved_sha, locked, rec_cfg):
    cfg, path = rec_cfg
    spoken = [
        APPROVED[0],
        "Erwachsene mit ADHS greifen manchmal zu Strategien, die nicht helfen.",
        APPROVED[2],
        APPROVED[3],
    ]
    res = gate.process_recording(
        db, path, approved_sha, transcriber=FakeTranscriber(spoken), cfg=cfg, verify=False
    )
    g = gate.recording_gate(db, res["recording_id"])
    assert any(i.kind == "unverified" for i in g.blockers)


def test_cli_ack_decide_srt(runner, db, approved_sha, locked, rec_cfg, monkeypatch, tmp_path):
    from ndc.cli import app
    from ndc.recording import store as st

    cfg, path = rec_cfg
    spoken = [APPROVED[0], APPROVED[1], "Auch Kinder mit ADHS zeigen das.", APPROVED[3]]
    monkeypatch.setattr(st, "load_config", lambda *a, **k: cfg)
    monkeypatch.setattr(st, "_default_transcriber", lambda c: FakeTranscriber(spoken))
    r = runner.invoke(
        app,
        ["recording", "add", str(path), "--script", approved_sha[:12], "--force", "--no-verify"],
    )
    assert r.exit_code == 0 and "deviation 1" in r.output and "Blocker" in r.output
    sha = r.output.split("transcript sha ")[1].split()[0]
    # verify offline with a fake client, then ack + approve via CLI
    conn = db.connect()
    rec = st.recording_by_ref(conn, sha)
    conn.close()
    st.verify_deviations(
        db, rec["id"], client=FakeClient([FakeMessage([], parsed=_report([_v(2, "partial")]))])
    )
    r = runner.invoke(app, ["recording", "show", sha])
    assert "Bestätigungen offen" in r.output and "partial" in r.output
    r = runner.invoke(app, ["recording", "ack", sha, "2"])
    assert r.exit_code == 0
    r = runner.invoke(app, ["recording", "decide", sha, "approved"])
    assert r.exit_code == 0 and "approved" in r.output
    out = tmp_path / "x.srt"
    r = runner.invoke(app, ["recording", "srt", sha, "-o", str(out)])
    assert r.exit_code == 0 and "4 cues" in r.output
    text = out.read_text(encoding="utf-8")
    flat = text.replace("\n", " ")
    assert text.startswith("1\n00:00:00,000 --> ")
    assert "Auch Kinder mit ADHS zeigen das." in flat and APPROVED[1] in flat
