"""Pure HTML builders for the phone review page (02-UI-SPEC.md). No JS, no external assets;
every dynamic string goes through html.escape."""

from html import escape as e

from ndc.review.gate import VERDICT_LABELS_DE, Card, GateResult

CSS = """
:root{--bg:#fff;--card:#f4f5f7;--line:#e3e5e8;--text:#1b1d21;--muted:#5b616b;--accent:#1f6feb;
--bad:#c62828;--badbg:#fdecea;--warn:#b26a00;--warnbg:#fff4e0;--ok:#1e7b34;--okbg:#e6f4ea;
--neu:#5b616b;--neubg:#eceef1}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--card:#1d2026;--line:#2c3038;
--text:#e7e9ec;--muted:#9aa1ab;--neubg:#2c3038;--badbg:#3a1d1d;--warnbg:#3a2c12;--okbg:#16301e}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:640px;margin:0 auto;padding:16px}
h1{font-size:20px;line-height:1.3;margin:0 0 4px}
a{color:var(--accent)}
.meta{color:var(--muted);font-size:13px}
.banner{position:sticky;top:0;padding:8px 16px;margin:0 -16px 16px;font-weight:600;z-index:2}
.banner.bad{background:var(--badbg);color:var(--bad)}.banner.warn{background:var(--warnbg);color:var(--warn)}
.banner.ok{background:var(--okbg);color:var(--ok)}.banner.neu{background:var(--neubg);color:var(--neu)}
.warnline{color:var(--warn);font-size:15px;margin:4px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px;margin:0 0 24px}
.claim{font-size:17px;font-weight:600;line-height:1.45;margin:8px 0}
.src{font-size:15px;font-style:italic;line-height:1.45;margin:4px 0 8px}
.lbl{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);
margin-top:8px}
.chip{display:inline-block;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.03em;
padding:4px 8px;border-radius:4px;margin:0 4px 4px 0}
.c-bad{color:var(--bad);background:var(--badbg)}.c-warn{color:var(--warn);background:var(--warnbg)}
.c-ok{color:var(--ok);background:var(--okbg)}.c-neu{color:var(--neu);background:var(--neubg)}
button{font:inherit;font-weight:600;min-height:44px;width:100%;border-radius:8px;padding:8px 16px;
border:1px solid var(--line);background:var(--bg);color:var(--text);margin:8px 0}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.danger{border-color:var(--bad);color:var(--bad)}
button:disabled{opacity:.45}
textarea{width:100%;min-height:88px;font:inherit;border-radius:8px;border:1px solid var(--line);
padding:8px;background:var(--bg);color:var(--text)}
details{margin:0 0 24px}summary{cursor:pointer;min-height:44px;padding:8px 0;color:var(--accent)}
.script p{margin:4px 0}.num{color:var(--muted);font-size:13px;margin-right:4px}
.decide{margin-top:32px}
.flash{background:var(--okbg);color:var(--ok);padding:8px 16px;border-radius:8px;margin-bottom:16px}
"""

CHIP_CLASS = {
    "contradicts": "c-bad",
    "unsupported": "c-bad",
    "overstated": "c-warn",
    "partial": "c-warn",
    "escalation": "c-warn",
    "supports": "c-ok",
    "not_applicable": "c-neu",
}
FLASH = {
    "approved": "Freigegeben ✓",
    "changes_requested": "Änderungen angefordert",
    "rejected": "Abgelehnt",
    "ack": "Bestätigt ✓",
}


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{e(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>"
    )


def render_error(code: int, message: str, link: str | None = None) -> str:
    body = f"<h1>{e(message)}</h1>"
    if link:
        body += f'<p><a href="{e(link)}">Zur aktuellen Version →</a></p>'
    body += '<p><a href="/">Zur Liste</a></p>'
    return page(f"Fehler {code}", body)


def render_list(pending: list[dict], decided: list[dict]) -> str:
    body = '<h1>Skript-Prüfung</h1><p class="meta"><a href="/">Neu laden</a></p>'
    if not pending:
        body += (
            '<div class="card"><h1>Nichts zu prüfen</h1><p>Neue Skripte erscheinen hier nach '
            "„ndc script verify“. Zuletzt entschieden: siehe unten.</p></div>"
        )
    for p in pending:
        body += (
            f'<div class="card"><a href="/r/{e(p["sha"])}"><b>{e(p["title"])}</b></a>'
            f'<div class="meta">v{p["version_no"]} · {e(p["sha"][:10])} · {e(p["state"])}</div></div>'
        )
    if decided:
        body += '<div class="lbl">Zuletzt entschieden</div>'
        for p in decided:
            body += (
                f'<p><a href="/r/{e(p["sha"])}">{e(p["title"])}</a> '
                f'<span class="meta">v{p["version_no"]} · {e(p["decision"])}</span></p>'
            )
    return page("Skript-Prüfung", body)


def _banner(res: GateResult, decision, stale_link: str | None) -> str:
    if stale_link:
        return (
            f'<div class="banner neu">veraltet — neuere Version vorhanden · '
            f'<a href="{e(stale_link)}">zur aktuellen</a></div>'
        )
    if decision:
        return (
            f'<div class="banner neu">Bereits entschieden: {e(decision["decision"])} am '
            f"{e(decision['created_at'])}</div>"
        )
    if res.blockers:
        return f'<div class="banner bad">Nicht freigebbar — {len(res.blockers)} Blocker</div>'
    if res.needs_ack:
        return f'<div class="banner warn">Noch {len(res.needs_ack)} Bestätigungen offen</div>'
    return '<div class="banner ok">Bereit zur Freigabe</div>'


def _card(c: Card, sha: str, nonce: str, needs_ack: set[int], stale: bool) -> str:
    rc = c.risk_class
    chips = f'<span class="chip {CHIP_CLASS[rc]}">{e(VERDICT_LABELS_DE[rc if rc != "escalation" else "supports"])}</span>'
    if c.escalation:
        chips += f'<span class="chip c-warn">{e(VERDICT_LABELS_DE["escalation"])}</span>'
    if c.hidden_claim:
        chips += f'<span class="chip c-bad">{e(VERDICT_LABELS_DE["hidden_claim"])}</span>'
    out = [
        f'<div class="card" id="s{c.ordinal}"><div><span class="num">[{c.ordinal}]</span>{chips}</div>',
        f'<div class="claim">„{e(c.text)}“</div>',
    ]
    if c.cited:
        out.append('<div class="lbl">Quelle</div>')
        for q in c.cited:
            loc = q.section or ""
            if q.page:
                loc += f" · S. {q.page}"
            out.append(
                f'<div class="meta">{e(q.short_cite)} · {e(loc)}</div>'
                f'<div class="src">“{e(q.text)}”</div>'
            )
    elif c.kind != "framing":
        out.append('<div class="lbl">Quelle</div><div class="src">Keine Quelle</div>')
    if c.note_de:
        out.append(f'<div class="lbl">Prüfer</div><div>{e(c.note_de)}</div>')
    if c.suggested_fix_de:
        out.append(f'<div class="meta">Vorschlag: „{e(c.suggested_fix_de)}“</div>')
    if c.verdict in ("contradicts", "unsupported") or c.verdict is None:
        out.append(
            f'<p class="meta">Blockiert — im CLI bearbeiten: ndc script export {e(sha[:10])}</p>'
        )
    elif c.acked:
        note = f" — {e(c.ack_note)}" if c.ack_note else ""
        out.append(f'<p class="chip c-ok">✓ bestätigt</p><span class="meta">{note}</span>')
    elif c.ordinal in needs_ack and not stale:
        out.append(
            f'<form method="post" action="/r/{e(sha)}/ack">'
            f'<input type="hidden" name="nonce" value="{e(nonce)}">'
            f'<input type="hidden" name="script_sha" value="{e(sha)}">'
            f'<input type="hidden" name="sentence" value="{c.ordinal}">'
            f'<button type="submit">Bestätigen</button></form>'
        )
    out.append("</div>")
    return "".join(out)


def render_review(
    *,
    title: str,
    meta_line: str,
    sha: str,
    version_no: int,
    res: GateResult,
    cards_sorted: list[Card],
    script_cards: list[Card],
    decision,
    nonce: str,
    stale_link: str | None = None,
    flash: str | None = None,
    note_error: str | None = None,
) -> str:
    stale = stale_link is not None
    needs = {i.sentence_ordinal for i in res.needs_ack}
    body = [_banner(res, decision, stale_link)]
    if flash in FLASH:
        body.append(f'<div class="flash">{e(FLASH[flash])}</div>')
    body.append(
        f'<h1>{e(title)}</h1><div class="meta">{e(meta_line)} · v{version_no} · '
        f'{e(sha[:10])} · <a href="/r/{e(sha)}">Neu laden</a></div>'
    )
    for i in res.blockers:
        body.append(f'<div class="warnline">✗ {e(i.message_de)}</div>')
    for i in res.warnings:
        body.append(f'<div class="warnline">⚠ {e(i.message_de)}</div>')
    body.append('<details open><summary>Skript</summary><div class="script">')
    body += [f'<p><span class="num">[{c.ordinal}]</span>{e(c.text)}</p>' for c in script_cards]
    body.append("</div></details>")
    risky = [c for c in cards_sorted if c.risk_class not in ("supports", "not_applicable")]
    calm = [c for c in cards_sorted if c.risk_class in ("supports", "not_applicable")]
    body += [_card(c, sha, nonce, needs, stale) for c in risky]
    if calm:
        n_sup = sum(1 for c in calm if c.risk_class == "supports")
        body.append(
            f"<details><summary>{n_sup} gestützte Aussagen, {len(calm) - n_sup} Rahmensätze "
            "anzeigen</summary>"
        )
        body += [_card(c, sha, nonce, needs, stale) for c in calm]
        body.append("</details>")
    if not stale and decision is None:
        dis = "" if res.approvable else " disabled"
        label = "Freigeben" if res.approvable else "Freigeben (gesperrt)"
        err = f'<p class="warnline">{e(note_error)}</p>' if note_error else ""
        body.append(
            f'<form class="decide" method="post" action="/r/{e(sha)}/decide">{err}'
            f'<input type="hidden" name="nonce" value="{e(nonce)}">'
            f'<input type="hidden" name="script_sha" value="{e(sha)}">'
            '<label class="lbl" for="note">Notiz (Pflicht bei Ablehnen / Änderungen)</label>'
            '<textarea id="note" name="note"></textarea>'
            f'<button class="primary" type="submit" name="decision" value="approved"{dis}>{label}</button>'
            '<button type="submit" name="decision" value="changes_requested">Änderungen anfordern</button>'
            '<button class="danger" type="submit" name="decision" value="rejected">Ablehnen</button>'
            "</form>"
        )
    return page(title, "".join(body))
