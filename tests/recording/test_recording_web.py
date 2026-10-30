import http.client
import json
import os
import sys
import threading
from urllib.parse import urlencode

import pytest
from recording_helpers import FakeTranscriber
from review_helpers import FakeClient, FakeMessage

from ndc.recording import gate
from ndc.review import web
from ndc.script import verify as vf

APPROVED = [
    "Starke Gefühle bei ADHS: was die Forschung zeigt.",
    "Erwachsene mit ADHS greifen häufiger zu wenig hilfreichen Strategien.",
    "Auch Kinder mit ADHS zeigen das häufiger.",
    "Quellen im angepinnten Kommentar.",
]


@pytest.fixture
def server(db):
    srv = web.make_server(os.environ["NDC_DB"], "127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def req(port, method, path, body=None, host="localhost:8090"):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    c.request(method, path, body=body, headers=headers)
    r = c.getresponse()
    data = r.read().decode()
    out = (r.status, dict(r.getheaders()), data)
    c.close()
    return out


@pytest.fixture
def partial_recording(db, approved_sha, locked, rec_cfg):
    cfg, path = rec_cfg
    spoken = [APPROVED[0], APPROVED[1], "Auch Kinder mit ADHS zeigen das.", APPROVED[3]]
    report = vf.VerifyReport(
        verdicts=[
            vf.SentenceVerdict(
                ordinal=2,
                kind="empirical",
                verdict="partial",
                certainty_escalation=False,
                hidden_claim=False,
                note_de="Hedge fehlt",
                suggested_fix_de="häufiger ergänzen",
            )
        ]
    )
    res = gate.process_recording(
        db,
        path,
        approved_sha,
        transcriber=FakeTranscriber(spoken),
        client=FakeClient([FakeMessage([], parsed=report)]),
        cfg=cfg,
    )
    return res["transcript_sha256"]


def test_web_imports_no_heavy_modules():
    assert "faster_whisper" not in sys.modules and "pymupdf" not in sys.modules


def test_list_shows_recordings_and_due_link(server, partial_recording):
    status, _, body = req(server, "GET", "/")
    assert (
        status == 200 and "Aufnahmen" in body and "/rec/" in body and "Kennzahlen fällig: 0" in body
    )


def test_recording_page_cards_ack_and_approve(server, db, partial_recording):
    sha = partial_recording
    status, headers, body = req(server, "GET", f"/rec/{sha}")
    assert status == 200 and "Bestätigungen offen" in body and "TEILWEISE" in body
    assert "Auch Kinder mit ADHS zeigen das." in body and "Hedge fehlt" in body
    assert "Content-Security-Policy" in headers and "<script" not in body
    nonce = body.split('name="nonce" value="')[1].split('"')[0]
    # bad nonce
    status, _, _ = req(
        server,
        "POST",
        f"/rec/{sha}/ack",
        urlencode({"nonce": "1.x", "script_sha": sha, "sentence": 2}),
    )
    assert status == 400
    status, headers, _ = req(
        server,
        "POST",
        f"/rec/{sha}/ack",
        urlencode({"nonce": nonce, "script_sha": sha, "sentence": 2}),
    )
    assert status == 303 and headers["Location"].startswith(f"/rec/{sha}?ok=ack")
    status, headers, _ = req(
        server,
        "POST",
        f"/rec/{sha}/decide",
        urlencode({"nonce": nonce, "script_sha": sha, "decision": "approved", "note": ""}),
    )
    assert status == 303 and "ok=approved" in headers["Location"]
    conn = db.connect()
    dec = gate.latest_recording_decision(conn, sha)
    conn.close()
    assert dec["decision"] == "approved" and dec["channel"] == "web"
    status, _, body = req(server, "GET", f"/rec/{sha}")
    assert "Bereits entschieden: approved" in body


def test_recording_404s_and_host(server, partial_recording):
    assert req(server, "GET", "/rec/abc")[0] == 404
    assert req(server, "GET", "/rec/" + "0" * 64)[0] == 404
    assert req(server, "GET", "/due/../etc/passwd")[0] == 404
    assert req(server, "GET", f"/rec/{partial_recording}", host="evil.example")[0] == 400
    assert req(server, "PUT", "/due")[0] == 404


def test_due_page_without_and_with_file(server, tmp_path, monkeypatch):
    monkeypatch.setattr(web, "DUE_PATH", str(tmp_path / "due.json"))
    status, _, body = req(server, "GET", "/due")
    assert status == 200 and "Keine fälligen Kennzahlen" in body
    (tmp_path / "due.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-11-04T18:00:00Z",
                "due": [
                    {
                        "publication_id": 1,
                        "platform": "tiktok",
                        "age": "24h",
                        "post_age_hours": 25.0,
                        "window_closes_in_h": 5.0,
                        "title": "<b>Starke</b> Gefühle",
                        "post_url": "x",
                        "fields": "full",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    status, _, body = req(server, "GET", "/due")
    assert status == 200 and "&lt;b&gt;Starke" in body and "ndc metrics add 1 --age 24h" in body
    status, _, body = req(server, "GET", "/")
    assert "Kennzahlen fällig: 1" in body
