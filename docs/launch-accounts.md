# Launch: Accounts, Bio, Einstellungen (OPS-02, Plan 03-02)

Stand 2026-10-29. Entscheidungen aus `.planning/phases/03-launch-readiness-first-publish/03-CONTEXT.md` (D-09, D-10, D-12, D-13).

## 1. Bio (alle drei Plattformen, wörtlich)

> ADHS & Autismus, erklärt aus Studien. Keine Diagnosen, keine Therapie – Quellen in jedem Video.

Das ist die Positionierung und der Disclaimer, der seit Phase 2 nicht mehr im Skript steht (D-22). Link-Text für später (Quellen-Hub, Phase 4+): „Alle Quellen: …“.

## 2. Handle

**Kriterien (D-12):** identisch auf TikTok, YouTube, Instagram · Kleinbuchstaben, ≤ 20 Zeichen · Deutsch · keine klinischen Wörter (kein „Dr“, „Therapie“, „Praxis“, „Diagnose“) · suggeriert keine Fachperson · leicht zu sprechen (wird im Video genannt).

**Kandidaten** (Verfügbarkeit prüft der Operator in jeder App – programmatische Prüfungen sind nicht erlaubt, Phase‑1 D‑16):

| Handle | Warum | TikTok | YouTube | Instagram |
|---|---|---|---|---|
| `quellenkopf` | „Quelle“ ist das Versprechen, „Kopf“ das Thema; kurz, merkbar | | | |
| `studienkopf` | gleiche Logik, betont Studien | | | |
| `nd.quellen` | Neurodivergenz + Quellen; nüchtern | | | |
| `adhs.belegt` | ADHS + „belegt“ (= mit Beleg); klar, aber ADHS-lastig | | | |
| `forschungskurz` | Forschung in kurz; passt zum Format | | | |
| `neurokurz` | kurz, neutral, nicht auf eine Diagnose festgelegt | | | |
| `adhs.erklaert` | sagt, was passiert; sehr generisch, evtl. vergeben | | | |
| `kopfsache.studien` | etwas länger; weicher Ton | | | |

Gewählt: *(Task 3)* → `config/accounts.yaml`.

## 3. Kontotypen

| Plattform | Typ | Warum |
|---|---|---|
| TikTok | **Personal** (nicht Business) | Creator-Tools bleiben; Creator-Rewards-Check in der App (LEGAL-02) |
| YouTube | Kanal mit Shorts | YPP-Weg in Österreich verfügbar (`docs/platform-eligibility.md`) |
| Instagram | **Professional → Creator** | Insights (Graph API) in Milestone 2 möglich |

## 4. Einstellungen vor dem ersten Post (pro Plattform)

- [ ] Kommentar-Keyword-Filter aktiv, Begriffe aus `docs/moderation-playbook.md` §4 eingetragen
- [ ] Spam-/Beleidigungsfilter aktiv („beleidigende Kommentare filtern“)
- [ ] DMs eingeschränkt (nur Follower / Anfragen); keine Beratung per DM
- [ ] **Keine Auto-Antworten**: keine automatischen Nachrichten, keine Begrüßungs-Bots, keine „gespeicherten Antworten“ im Auto-Versand (Instagram-Schnellantworten dürfen existieren, werden aber nur manuell gesendet)
- [ ] Duett/Stitch erlaubt (Reichweite), Download **aus**
- [ ] Posting-Slot festgelegt und in `config/accounts.yaml` eingetragen (bleibt die ganze Validierung konstant)
- [ ] TikTok Studio → Content Check (Lite) für sensible Themen bekannt

## 5. Cross-Posting-Regel

Auf YouTube und Instagram wird immer das **Original-Render** hochgeladen, nie der TikTok-Download (Wasserzeichen → Deprioritisierung). Reihenfolge im Publish-Log: zuerst TikTok, dann die Cross-Posts (`ndc publish log`).

## 6. MedienG §25 (Offenlegung) — bewusst aufgeschoben (D-09)

Die Recherche sagt: die Offenlegungspflicht gilt ab der ersten regelmäßigen Veröffentlichung, nicht erst ab Monetarisierung (PITFALLS Pitfall 9). **Operator-Entscheidung 2026-10-29:** das Risiko wird für den nicht-kommerziellen Validierungslauf weiter akzeptiert; keine Impressum-Seite, kein Adress-Service in Phase 3. Wiedervorlage in Phase 4 mit der WKO (LEGAL-01). Dieser Abschnitt ist die Dokumentation dieser Entscheidung, keine Rechtsberatung.

## 7. Nach dem Anlegen (Task 3)

1. `config/accounts.yaml` füllen (handle, URLs, posting_slot_local).
2. `docs/platform-eligibility.md` mit dem In-App-Ergebnis zu Creator Rewards ergänzen.
3. `ndc moderation check` → `approved_at` in `config/moderation.yaml` setzen → `ndc moderation render`.
