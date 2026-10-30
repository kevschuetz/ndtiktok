"""Phone review server (D-17..D-19). stdlib only, exactly four routes, no file serving.

Hardening (2026-10-21 polymarkt incident: path traversal -> /proc/self/environ):
- regex route table; everything else is 404 with a fixed body (no path echo)
- no static handler, no open() of anything derived from the request; DB is the only I/O
- Host allow-list (localhost/127.0.0.1) against DNS rebinding through the tunnel
- HMAC nonce bound to the script sha on every POST; CSP form-action 'self'
- fixed German error copy, never a traceback; access log without query/body
The container running this has no API keys (no env_file).
"""

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from ndc.db import Database
from ndc.recording import gate as rgate
from ndc.recording import store as rstore
from ndc.review import store
from ndc.review.gate import cards, gate, latest_version_of, sorted_cards
from ndc.review.web_render import (
    render_due,
    render_error,
    render_list,
    render_recording,
    render_review,
)

log = logging.getLogger(__name__)

SHA = r"([0-9a-f]{64})"
ROUTES = [
    ("GET", re.compile(r"^/$"), "list"),
    ("GET", re.compile(rf"^/r/{SHA}$"), "review"),
    ("POST", re.compile(rf"^/r/{SHA}/ack$"), "ack"),
    ("POST", re.compile(rf"^/r/{SHA}/decide$"), "decide"),
    ("GET", re.compile(rf"^/rec/{SHA}$"), "rec"),
    ("POST", re.compile(rf"^/rec/{SHA}/ack$"), "rec_ack"),
    ("POST", re.compile(rf"^/rec/{SHA}/decide$"), "rec_decide"),
    ("GET", re.compile(r"^/due$"), "due"),
]
DUE_PATH = "/data/due.json"  # constant: written by `ndc metrics due --write`; never from a request
ALLOWED_HOSTS = {"localhost", "127.0.0.1"} | {
    h.strip().lower()
    for h in os.environ.get("NDC_REVIEW_ALLOWED_HOSTS", "").split(",")
    if h.strip()
}
MAX_BODY = 8 * 1024
NONCE_TTL = 24 * 3600
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
}
_KEY = secrets.token_bytes(32)


def issue_nonce(sha: str, now: float | None = None) -> str:
    ts = str(int(now if now is not None else time.time()))
    mac = hmac.new(_KEY, f"{sha}|{ts}".encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{mac}"


def check_nonce(nonce: str, sha: str, now: float | None = None) -> bool:
    try:
        ts, mac = nonce.split(".", 1)
        age = (now if now is not None else time.time()) - int(ts)
    except (ValueError, AttributeError):
        return False
    if age < 0 or age > NONCE_TTL:
        return False
    want = hmac.new(_KEY, f"{sha}|{ts}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, mac)


class Handler(BaseHTTPRequestHandler):
    db_path: str = ""
    server_version = "ndc-review"
    sys_version = ""

    # -- plumbing -------------------------------------------------------------------------------
    def log_message(self, fmt, *args):  # no query strings / bodies in logs
        pass

    def _send(self, code: int, html: str, location: str | None = None) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        log.info("review %s %s", self.command, code)

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        name = host.rsplit(":", 1)[0] if ":" in host else host
        return name in ALLOWED_HOSTS

    def _route(self):
        path = self.path.split("?", 1)[0]
        for method, pat, name in ROUTES:
            m = pat.match(path)
            if m and method == self.command:
                return name, m.groups()
        return None, ()

    def _dispatch(self) -> None:
        try:
            if not self._host_ok():
                host = (self.headers.get("Host") or "")[:80]
                log.warning("review rejected Host %r (allowed: %s)", host, sorted(ALLOWED_HOSTS))
                return self._send(400, render_error(400, "Ungültige Anfrage."))
            name, args = self._route()
            if name is None:
                return self._send(404, render_error(404, "Nicht gefunden."))
            getattr(self, f"h_{name}")(*args)
        except Exception:  # never leak internals
            log.exception("review handler failed")
            self._send(500, render_error(500, "Fehler beim Speichern. Nichts wurde geändert."))

    do_GET = do_POST = _dispatch

    def do_PUT(self):  # noqa: N802
        self._send(404, render_error(404, "Nicht gefunden."))

    do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_PUT

    def _db(self) -> Database:
        return Database(self.db_path)

    def _form(self) -> dict[str, str] | None:
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if ctype != "application/x-www-form-urlencoded" or length > MAX_BODY:
            return None
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    # -- handlers -------------------------------------------------------------------------------
    def h_list(self) -> None:
        db = self._db()
        conn = db.connect()
        try:
            latest = conn.execute(
                "SELECT v.*, t.working_title FROM script_version v "
                "JOIN script s ON s.id = v.script_id "
                "JOIN topic t ON t.id = s.topic_id WHERE v.version_no = (SELECT max(version_no) "
                "FROM script_version WHERE script_id = v.script_id) ORDER BY v.id DESC"
            ).fetchall()
            pending, decided = [], []
            for v in latest:
                dec = store.latest_decision(conn, v["sha256"])
                item = {
                    "sha": v["sha256"],
                    "title": v["working_title"],
                    "version_no": v["version_no"],
                }
                if dec:
                    decided.append(item | {"decision": dec["decision"]})
                else:
                    res = gate(db, v["id"], conn=conn)
                    state = (
                        "Blocker"
                        if res.blockers
                        else f"{len(res.needs_ack)} offen"
                        if res.needs_ack
                        else "bereit"
                    )
                    pending.append(item | {"state": state})
            recs = []
            for r in conn.execute(
                "SELECT r.*, t.working_title FROM recording r "
                "JOIN script_version v ON v.id = r.script_version_id "
                "JOIN script s ON s.id = v.script_id JOIN topic t ON t.id = s.topic_id "
                "ORDER BY r.id DESC LIMIT 20"
            ):
                rdec = rgate.latest_recording_decision(conn, r["transcript_sha256"])
                recs.append(
                    {
                        "sha": r["transcript_sha256"],
                        "title": r["working_title"],
                        "state": rdec["decision"]
                        if rdec
                        else rgate.banner(rgate.recording_gate(db, r["id"], conn=conn)),
                        "pending": rdec is None,
                    }
                )
        finally:
            conn.close()
        self._send(200, render_list(pending, decided[:10], recs, len(_due_items())))

    def _review_page(
        self, sha: str, code: int = 200, flash: str | None = None, note_error: str | None = None
    ) -> None:
        db = self._db()
        conn = db.connect()
        try:
            v = conn.execute("SELECT * FROM script_version WHERE sha256 = ?", (sha,)).fetchone()
            if v is None:
                return self._send(404, render_error(404, "Nicht gefunden."))
            topic = conn.execute(
                "SELECT t.working_title, t.pillar, t.condition FROM script s JOIN topic t "
                "ON t.id = s.topic_id WHERE s.id = ?",
                (v["script_id"],),
            ).fetchone()
            latest = latest_version_of(conn, v)
            stale_link = None if latest["id"] == v["id"] else f"/r/{latest['sha256']}"
            res = gate(db, v["id"], conn=conn)
            cs = cards(conn, v["id"])
            dec = store.latest_decision(conn, sha)
        finally:
            conn.close()
        html = render_review(
            title=topic["working_title"],
            meta_line=f"{topic['pillar']} · {topic['condition']} · {v['word_count']} Wörter "
            f"(Ziel 140–190)",
            sha=sha,
            version_no=v["version_no"],
            res=res,
            cards_sorted=sorted_cards(cs),
            script_cards=cs,
            decision=dec,
            nonce=issue_nonce(sha),
            stale_link=stale_link,
            flash=flash,
            note_error=note_error,
        )
        self._send(code, html)

    def h_review(self, sha: str) -> None:
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        flash = parse_qs(q).get("ok", [None])[0]
        self._review_page(
            sha,
            flash=flash if flash in ("approved", "changes_requested", "rejected", "ack") else None,
        )

    def _checked_form(self, sha: str) -> dict | None:
        form = self._form()
        if (
            form is None
            or form.get("script_sha") != sha
            or not check_nonce(form.get("nonce", ""), sha)
        ):
            self._send(
                400,
                render_error(400, "Formular abgelaufen. Seite neu laden und nochmal versuchen."),
            )
            return None
        return form

    def _stale(self, sha: str) -> bool:
        conn = self._db().connect()
        try:
            v = conn.execute("SELECT * FROM script_version WHERE sha256 = ?", (sha,)).fetchone()
            if v is None:
                self._send(404, render_error(404, "Nicht gefunden."))
                return True
            latest = latest_version_of(conn, v)
        finally:
            conn.close()
        if latest["id"] != v["id"]:
            self._send(
                409,
                render_error(
                    409,
                    "Diese Version ist veraltet — es gibt eine neuere.",
                    f"/r/{latest['sha256']}",
                ),
            )
            return True
        return False

    def h_ack(self, sha: str) -> None:
        form = self._checked_form(sha)
        if form is None or self._stale(sha):
            return
        try:
            n = int(form.get("sentence", ""))
            store.ack(self._db(), sha, n, note=None, channel="web")
        except (ValueError, store.ReviewRefused) as exc:
            return self._review_page(sha, code=422, note_error=str(exc))
        self._send(303, "", location=f"/r/{sha}?ok=ack#s{n}")

    def h_decide(self, sha: str) -> None:
        form = self._checked_form(sha)
        if form is None or self._stale(sha):
            return
        decision = form.get("decision", "")
        if decision not in store.DECISIONS:
            return self._send(400, render_error(400, "Ungültige Anfrage."))
        try:
            store.decide(self._db(), sha, decision, note=form.get("note"), channel="web")
        except store.ReviewRefused as exc:
            return self._review_page(sha, code=422, note_error=str(exc))
        self._send(303, "", location=f"/r/{sha}?ok={decision}")

    # -- recordings ------------------------------------------------------------------------------
    def _rec_page(self, sha: str, code: int = 200, flash=None, note_error=None) -> None:
        db = self._db()
        conn = db.connect()
        try:
            rec = conn.execute(
                "SELECT * FROM recording WHERE transcript_sha256 = ?", (sha,)
            ).fetchone()
            if rec is None:
                return self._send(404, render_error(404, "Nicht gefunden."))
            topic = conn.execute(
                "SELECT t.working_title FROM script_version v JOIN script s ON s.id = v.script_id "
                "JOIN topic t ON t.id = s.topic_id WHERE v.id = ?",
                (rec["script_version_id"],),
            ).fetchone()
            res = rgate.recording_gate(db, rec["id"], conn=conn)
            rows = rstore.sentences(conn, rec["id"])
            dec = rgate.latest_recording_decision(conn, sha)
        finally:
            conn.close()
        self._send(
            code,
            render_recording(
                title=topic["working_title"],
                rec=rec,
                res=res,
                rows=rows,
                decision=dec,
                nonce=issue_nonce(sha),
                flash=flash,
                note_error=note_error,
            ),
        )

    def h_rec(self, sha: str) -> None:
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        flash = parse_qs(q).get("ok", [None])[0]
        self._rec_page(
            sha,
            flash=flash if flash in ("approved", "changes_requested", "rejected", "ack") else None,
        )

    def _rec_stale(self, sha: str) -> bool:
        db = self._db()
        conn = db.connect()
        try:
            rec = conn.execute(
                "SELECT id FROM recording WHERE transcript_sha256 = ?", (sha,)
            ).fetchone()
            if rec is None:
                self._send(404, render_error(404, "Nicht gefunden."))
                return True
            res = rgate.recording_gate(db, rec["id"], conn=conn)
        finally:
            conn.close()
        if any(i.kind == "block_stale" for i in res.blockers):
            self._send(
                409, render_error(409, "Skriptversion ist veraltet — neue Aufnahme nötig.", "/")
            )
            return True
        return False

    def h_rec_ack(self, sha: str) -> None:
        form = self._checked_form(sha)
        if form is None or self._rec_stale(sha):
            return
        try:
            n = int(form.get("sentence", ""))
            rgate.ack(self._db(), sha, n, channel="web")
        except (ValueError, rstore.RecordingError) as exc:
            return self._rec_page(sha, code=422, note_error=str(exc))
        self._send(303, "", location=f"/rec/{sha}?ok=ack#s{n}")

    def h_rec_decide(self, sha: str) -> None:
        form = self._checked_form(sha)
        if form is None or self._rec_stale(sha):
            return
        decision = form.get("decision", "")
        if decision not in store.DECISIONS:
            return self._send(400, render_error(400, "Ungültige Anfrage."))
        try:
            rgate.decide(self._db(), sha, decision, note=form.get("note"), channel="web")
        except rstore.RecordingError as exc:
            return self._rec_page(sha, code=422, note_error=str(exc))
        self._send(303, "", location=f"/rec/{sha}?ok={decision}")

    # -- due snapshots ---------------------------------------------------------------------------
    def h_due(self) -> None:
        data = _due_payload()
        self._send(200, render_due(data.get("due", []), data.get("generated_at")))


def _due_payload() -> dict:
    """Read the constant due-list file (written by `ndc metrics due --write`); never a request
    path."""
    import json
    from pathlib import Path

    p = Path(DUE_PATH)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _due_items() -> list:
    return _due_payload().get("due", []) or []


def make_server(db_path: str, host: str = "127.0.0.1", port: int = 8090) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"db_path": db_path})
    return ThreadingHTTPServer((host, port), handler)
