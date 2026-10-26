"""The single place that decides whether a script version is approvable (SCR-03, D-14).

Pure over DB state: blockers (contradicts/unsupported, blocked checks, unoverridden warns, not
verified, not latest), needs_ack (overstated/partial/escalation without an ack for THIS sha),
warnings. GATE_HOOKS lets later plans add AWMF warnings / ID-check blockers.
"""

from dataclasses import dataclass, field
from types import SimpleNamespace

from ndc import llm
from ndc.db import Database
from ndc.script.draft import run_mechanical_checks

RISK_ORDER = {
    "contradicts": 0,
    "unsupported": 1,
    "overstated": 2,
    "partial": 3,
    "escalation": 4,
    "supports": 5,
    "not_applicable": 6,
}

VERDICT_LABELS_DE = {
    "supports": "GESTÜTZT",
    "partial": "TEILWEISE",
    "overstated": "ÜBERZOGEN",
    "unsupported": "UNGESTÜTZT",
    "contradicts": "WIDERSPRICHT",
    "not_applicable": "RAHMEN",
    "escalation": "↑ Sicherheit erhöht",
    "hidden_claim": "versteckte Aussage",
}

BLOCKING = {"contradicts", "unsupported"}
NEEDS_ACK = {"overstated", "partial"}


@dataclass
class Issue:
    kind: str
    sentence_ordinal: int | None
    message_de: str


@dataclass
class GateResult:
    approvable: bool
    blockers: list[Issue] = field(default_factory=list)
    needs_ack: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)


@dataclass
class Cited:
    short_cite: str
    section: str | None
    page: int | None
    text: str


@dataclass
class Card:
    ordinal: int
    text: str
    verdict: str | None
    kind: str | None
    escalation: bool
    hidden_claim: bool
    forced_reason: str | None
    note_de: str | None
    suggested_fix_de: str | None
    reused: bool
    cited: list[Cited]
    acked: bool
    ack_note: str | None
    risk_class: str


GATE_HOOKS: list = []


def _sentence_rows(conn, version_id: int) -> list:
    return conn.execute(
        "SELECT ss.id, ss.ordinal, ss.text, cv.verdict, cv.kind, cv.certainty_escalation, "
        "cv.hidden_claim, cv.forced_reason, cv.note_de, cv.suggested_fix_de, cv.reused_from_id, "
        "cv.id AS cv_id FROM script_sentence ss LEFT JOIN claim_verdict cv "
        "ON cv.script_sentence_id = ss.id WHERE ss.script_version_id = ? ORDER BY ss.ordinal",
        (version_id,),
    ).fetchall()


def risk_class(verdict: str | None, escalation: bool) -> str:
    if verdict is None:
        return "unsupported"
    if verdict == "supports" and escalation:
        return "escalation"
    return verdict


def is_latest(conn, version) -> bool:
    mx = conn.execute(
        "SELECT max(version_no) FROM script_version WHERE script_id = ?", (version["script_id"],)
    ).fetchone()[0]
    return version["version_no"] == mx


def latest_version_of(conn, version):
    return conn.execute(
        "SELECT * FROM script_version WHERE script_id = ? ORDER BY version_no DESC LIMIT 1",
        (version["script_id"],),
    ).fetchone()


def cards(conn, version_id: int) -> list[Card]:
    v = conn.execute("SELECT * FROM script_version WHERE id = ?", (version_id,)).fetchone()
    corpus_id = conn.execute(
        "SELECT corpus_id FROM script WHERE id = ?", (v["script_id"],)
    ).fetchone()[0]
    acks = {
        r["sentence_ordinal"]: r["note"]
        for r in conn.execute(
            "SELECT sentence_ordinal, note FROM claim_ack WHERE script_sha256 = ?", (v["sha256"],)
        )
    }
    out = []
    for r in _sentence_rows(conn, version_id):
        cited = [
            Cited(c["short_cite"], c["section"], c["page"], c["text"])
            for c in conn.execute(
                "SELECT cs.short_cite, src.section, src.page, src.text FROM script_citation sc "
                "JOIN source_sentence src ON src.id = sc.source_sentence_id "
                "JOIN corpus_source cs ON cs.snapshot_id = src.snapshot_id AND cs.corpus_id = ? "
                "WHERE sc.script_sentence_id = ? ORDER BY cs.position, src.ordinal",
                (corpus_id, r["id"]),
            )
        ]
        esc = bool(r["certainty_escalation"])
        out.append(
            Card(
                ordinal=r["ordinal"],
                text=r["text"],
                verdict=r["verdict"],
                kind=r["kind"],
                escalation=esc,
                hidden_claim=bool(r["hidden_claim"]),
                forced_reason=r["forced_reason"],
                note_de=r["note_de"],
                suggested_fix_de=r["suggested_fix_de"],
                reused=r["reused_from_id"] is not None,
                cited=cited,
                acked=r["ordinal"] in acks,
                ack_note=acks.get(r["ordinal"]),
                risk_class=risk_class(r["verdict"], esc),
            )
        )
    return out


def sorted_cards(cs: list[Card]) -> list[Card]:
    return sorted(cs, key=lambda c: (RISK_ORDER[c.risk_class], c.ordinal))


def gate(db: Database, version_id: int, conn=None) -> GateResult:
    own = conn is None
    conn = conn or db.connect()
    try:
        v = conn.execute("SELECT * FROM script_version WHERE id = ?", (version_id,)).fetchone()
        if v is None:
            return GateResult(False, [Issue("missing", None, "Version nicht gefunden")])
        res = GateResult(False)
        if not is_latest(conn, v):
            res.blockers.append(Issue("stale", None, "veraltet — es gibt eine neuere Version"))
        cs = cards(conn, version_id)
        unverified = [c.ordinal for c in cs if c.verdict is None]
        if unverified:
            res.blockers.append(
                Issue("unverified", None, f"nicht geprüft: Sätze {unverified} (ndc script verify)")
            )
        for c in cs:
            if c.verdict in BLOCKING:
                why = {"hidden_claim": " (versteckte Aussage)", "uncited": " (ohne Quelle)"}.get(
                    c.forced_reason or "", ""
                )
                res.blockers.append(
                    Issue(
                        c.verdict,
                        c.ordinal,
                        f"Satz {c.ordinal}: {VERDICT_LABELS_DE[c.verdict]}{why}",
                    )
                )
            elif (
                c.verdict in NEEDS_ACK or (c.verdict == "supports" and c.escalation)
            ) and not c.acked:
                res.needs_ack.append(
                    Issue(
                        c.risk_class,
                        c.ordinal,
                        f"Satz {c.ordinal}: {VERDICT_LABELS_DE[c.risk_class]} — bestätigen",
                    )
                )
        sents = [SimpleNamespace(ordinal=c.ordinal, text=c.text) for c in cs]
        status, _, words = run_mechanical_checks(db, v["text"], sents)
        if status == "blocked":
            res.blockers.append(
                Issue("check_blocked", None, "Begriffs-/Sicherheitsprüfung blockiert")
            )
        elif status == "needs_override":
            res.blockers.append(
                Issue(
                    "check_override", None, "Begriffswarnung ohne Override (ndc check … --override)"
                )
            )
        lo_hi = llm.load_llm_config().draft.word_range
        if lo_hi and not (lo_hi[0] <= words <= lo_hi[1]):
            res.warnings.append(
                Issue("word_count", None, f"{words} Wörter (Ziel {lo_hi[0]}–{lo_hi[1]})")
            )
        reused = sum(1 for c in cs if c.reused)
        if reused:
            res.warnings.append(
                Issue("reused", None, f"Bewertungen aus Vorversion übernommen: {reused}")
            )
        for hook in GATE_HOOKS:
            for issue in hook(conn, version_id):
                (res.blockers if issue.kind.startswith("block") else res.warnings).append(issue)
        res.approvable = not res.blockers and not res.needs_ack
        return res
    finally:
        if own:
            conn.close()
