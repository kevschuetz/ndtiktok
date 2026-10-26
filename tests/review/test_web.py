import http.client
import os
import threading
from urllib.parse import urlencode

import pytest
from review_helpers import row, sha_of, verify_with

from ndc.review import web
from ndc.review.web_render import render_review

FR = dict(kind="framing", verdict="not_applicable")


@pytest.fixture
def server(db, version):
    srv = web.make_server(os.environ["NDC_DB"], "127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def req(port, method, path, body=None, host="localhost:8090", ctype=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host}
    if body is not None:
        headers["Content-Type"] = ctype or "application/x-www-form-urlencoded"
    c.request(method, path, body=body, headers=headers)
    r = c.getresponse()
    data = r.read().decode()
    out = (r.status, dict(r.getheaders()), data)
    c.close()
    return out


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/static/x"),
        ("GET", "/../etc/passwd"),
        ("GET", "/%2e%2e/proc/self/environ"),
        ("GET", "/proc/self/environ"),
        ("GET", "/r/abc"),
        ("GET", "/r/" + "a" * 64 + "/../x"),
        ("PUT", "/r/" + "a" * 64 + "/decide"),
        ("GET", "/r/" + "a" * 64 + "/decide"),
        ("DELETE", "/"),
    ],
)
def test_unknown_paths_404_without_echo(server, method, path):
    status, headers, body = req(server, method, path)
    assert status == 404
    assert "Nicht gefunden." in body
    assert "passwd" not in body and "environ" not in body and "static" not in body
    assert "Content-Security-Policy" in headers


def test_host_allow_list(server):
    assert req(server, "GET", "/", host="evil.example")[0] == 400
    assert req(server, "GET", "/", host="localhost:8090")[0] == 200
    assert req(server, "GET", "/", host="127.0.0.1:8090")[0] == 200


def _nonce_from(body):
    import re

    return re.search(r'name="nonce" value="([^"]+)"', body).group(1)


def test_ack_and_decide_flow(server, db, version):
    verify_with(db, version, [row(0, **FR), row(1, verdict="overstated"), row(2), row(3, **FR)])
    sha = sha_of(db, version)
    status, _, body = req(server, "GET", f"/r/{sha}")
    assert status == 200 and "Noch 1 Bestätigungen offen" in body
    assert 'value="approved" disabled' in body
    nonce = _nonce_from(body)
    status, h, _ = req(
        server,
        "POST",
        f"/r/{sha}/decide",
        urlencode({"nonce": nonce, "script_sha": sha, "decision": "approved"}),
    )
    assert status == 422
    status, h, _ = req(
        server,
        "POST",
        f"/r/{sha}/ack",
        urlencode({"nonce": nonce, "script_sha": sha, "sentence": "1"}),
    )
    assert status == 303 and h["Location"].startswith(f"/r/{sha}?ok=ack")
    status, _, body = req(server, "GET", f"/r/{sha}")
    assert "✓ bestätigt" in body and "Bereit zur Freigabe" in body
    status, h, _ = req(
        server,
        "POST",
        f"/r/{sha}/decide",
        urlencode({"nonce": nonce, "script_sha": sha, "decision": "approved"}),
    )
    assert status == 303
    conn = db.connect()
    assert conn.execute("SELECT channel, decision FROM review").fetchone()[:] == ("web", "approved")
    assert conn.execute("SELECT channel FROM claim_ack").fetchone()[0] == "web"
    conn.close()


@pytest.mark.parametrize("nonce", ["", "123.deadbeef", "notanonce"])
def test_bad_nonce(server, db, version, nonce):
    verify_with(db, version, [row(0, **FR), row(1), row(2), row(3, **FR)])
    sha = sha_of(db, version)
    status, _, body = req(
        server,
        "POST",
        f"/r/{sha}/decide",
        urlencode({"nonce": nonce, "script_sha": sha, "decision": "approved"}),
    )
    assert status == 400 and "Formular abgelaufen" in body


def test_expired_and_foreign_nonce(db, version):
    sha = sha_of(db, version)
    old = web.issue_nonce(sha, now=1000)
    assert not web.check_nonce(old, sha, now=1000 + web.NONCE_TTL + 1)
    assert not web.check_nonce(web.issue_nonce("b" * 64), sha)
    assert web.check_nonce(web.issue_nonce(sha), sha)


def test_reject_needs_note(server, db, version):
    verify_with(db, version, [row(0, **FR), row(1), row(2), row(3, **FR)])
    sha = sha_of(db, version)
    nonce = _nonce_from(req(server, "GET", f"/r/{sha}")[2])
    status, _, body = req(
        server,
        "POST",
        f"/r/{sha}/decide",
        urlencode({"nonce": nonce, "script_sha": sha, "decision": "rejected"}),
    )
    assert status == 422 and "Bitte kurz begründen." in body


def test_wrong_content_type_and_oversize(server, db, version):
    sha = sha_of(db, version)
    nonce = web.issue_nonce(sha)
    body = urlencode({"nonce": nonce, "script_sha": sha, "decision": "approved"})
    assert req(server, "POST", f"/r/{sha}/decide", body, ctype="application/json")[0] == 400
    assert req(server, "POST", f"/r/{sha}/decide", "x=" + "a" * 9000)[0] == 400


def test_server_error_hides_traceback(server, db, version, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(web, "gate", boom)
    status, _, body = req(server, "GET", f"/r/{sha_of(db, version)}")
    assert status == 500
    assert "Traceback" not in body and "secret internal detail" not in body
    assert "Nichts wurde geändert" in body


def test_render_escapes_and_has_no_scripts(db, version):
    from ndc.review.gate import Card, Cited, GateResult

    evil = Card(
        0,
        "<script>alert(1)</script>",
        "partial",
        "empirical",
        False,
        False,
        None,
        "<b>x</b>",
        None,
        False,
        [Cited("A & B", "S", None, "<img src=x>")],
        False,
        None,
        "partial",
    )
    html = render_review(
        title="T<",
        meta_line="m",
        sha="a" * 64,
        version_no=1,
        res=GateResult(False),
        cards_sorted=[evil],
        script_cards=[evil],
        decision=None,
        nonce="n",
    )
    assert "<script" not in html and "<img" not in html and "<link" not in html
    assert 'src="http' not in html
    assert "&lt;script&gt;" in html


def test_page_weight(server, db, version):
    verify_with(db, version, [row(0, **FR), row(1), row(2), row(3, **FR)])
    status, _, body = req(server, "GET", f"/r/{sha_of(db, version)}")
    assert len(body.encode()) < 60_000


def test_env_allowed_hosts(monkeypatch):
    import importlib

    monkeypatch.setenv("NDC_REVIEW_ALLOWED_HOSTS", "10.0.0.213, 10.8.0.1")
    mod = importlib.reload(web)
    try:
        assert {"localhost", "127.0.0.1", "10.0.0.213", "10.8.0.1"} == mod.ALLOWED_HOSTS
    finally:
        monkeypatch.delenv("NDC_REVIEW_ALLOWED_HOSTS")
        importlib.reload(web)
