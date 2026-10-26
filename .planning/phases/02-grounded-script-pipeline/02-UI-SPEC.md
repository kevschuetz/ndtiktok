---
phase: 2
slug: grounded-script-pipeline
status: draft
shadcn_initialized: false
preset: none
created: 2026-10-26
---

# Phase 2 — UI Design Contract

> Phone-first review page served by `ndc review serve` (stdlib HTTP server, server-rendered HTML, no JS framework, no external assets). Written inline by the orchestrating session (operator: no subagents). Language of all UI copy: German.

---

## Scope

Three screens, nothing else:

1. **Liste** (`GET /`) — scripts awaiting review (latest version per script, not yet decided), plus the last 10 decided.
2. **Prüfung** (`GET /r/<script_sha>`) — one script version: header, gate status, full script text, claim cards sorted by risk, decision bar.
3. **Ergebnis** — the same Prüfung page re-rendered after a POST, with a one-line confirmation banner (POST → 303 redirect → GET; no separate page).

Out of scope: editing script text, regenerating, source search, any login screen (access = SSH tunnel to 127.0.0.1).

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (hand-written HTML + one inline `<style>` block) |
| Preset | not applicable |
| Component library | none |
| Icon library | none — Unicode only (✓ ✗ ⚠ ●) |
| Font | system stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`; source sentences in the same stack, italic |

No external CSS/JS/fonts/images (no network requests from the page; also keeps the server free of a static handler).
JavaScript: none required. Every action is a plain `<form method="post">`. Pages must work with JS disabled.

---

## Layout

- Single column, `max-width: 640px`, centered, `padding: 16px`. Designed at 375px width first; desktop just gets the centered column.
- `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- Tap targets ≥ 44×44px. Form buttons full-width on phone.

### Prüfung page (top → bottom)

1. **Header**: topic working title (h1), pillar · condition, `Version N`, short hash (first 10 hex chars), created time, word count with target `150–190` (⚠ chip if outside).
2. **Gate banner** (sticky top, one line):
   - red: `Nicht freigebbar — 2 Blocker` (count)
   - amber: `Noch 3 Bestätigungen offen`
   - green: `Bereit zur Freigabe`
   - grey: `Bereits entschieden: freigegeben am …` / `veraltet — neuere Version vorhanden` (with link to the latest)
3. **Warnungen** (if any): AWMF expired/under revision, verdicts reused from previous version, ID-check problems — one line each with ⚠.
4. **Skript** (collapsible `<details open>`): the full German script as spoken text, each sentence prefixed with a small number `[3]` matching its card.
5. **Claim cards**, sorted by risk: contradicts → unsupported → overstated → partial → escalation → supports → framing. `supports` and `framing` groups are inside a collapsed `<details>` ("12 gestützte Aussagen, 4 Rahmensätze anzeigen") so the operator's attention goes to the risky ones.
6. **Decision bar** (bottom, not sticky): note textarea (optional; required for "Änderungen anfordern" and "Ablehnen"), then three buttons.

### Claim card

```
┌──────────────────────────────────────┐
│ [3] ● ÜBERZOGEN   ↑ Sicherheit erhöht │  ← verdict chip + escalation chip
│ „Erwachsene mit ADHS greifen häufiger │  ← German claim (bold, 17px)
│  zu wenig hilfreichen Strategien …"   │
│ ── Quelle ─────────────────────────── │
│ Soler-Gutiérrez et al. 2023 · Results │  ← source short cite · section/page
│ "Adults with ADHD show a more frequent│  ← verbatim stored sentence(s), italic
│  use of non-adaptive emotion …"       │
│ ── Prüfer ─────────────────────────── │
│ Die Quelle spricht von „non-adaptive" │  ← verifier note (DE)
│ Vorschlag: „… greifen eher …"          │  ← suggested fix if present
│ [ ✓ Bestätigen ]                       │  ← only on needs-ack cards
└──────────────────────────────────────┘
```

- Blocker cards (contradicts/unsupported, forced or not) have no button — text: `Blockiert — im CLI bearbeiten: ndc script export <hash>`.
- Acknowledged cards show `✓ bestätigt` + the note instead of the button; acks are per script hash.
- Uncited non-framing sentences show `Keine Quelle` in the source section.
- Multiple cited sentences: stacked, each with its own short cite.

---

## Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | chip padding vertical, gap between chips |
| sm | 8px | chip padding horizontal, gap inside card sections |
| md | 16px | page padding, card padding |
| lg | 24px | gap between cards |
| xl | 32px | gap before decision bar |

Exceptions: none.

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 16px | 400 | 1.5 |
| Claim text | 17px | 600 | 1.45 |
| Source sentence | 15px | 400 italic | 1.45 |
| Label / chip | 13px | 600, uppercase, letter-spacing .03em | 1.2 |
| Heading (h1) | 20px | 700 | 1.3 |

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#ffffff` | page background |
| Secondary (30%) | `#f4f5f7` | cards; `#e3e5e8` borders |
| Text | `#1b1d21` primary, `#5b616b` secondary |
| Accent (10%) | `#1f6feb` | "Freigeben" button, links |
| Destructive | `#c62828` | contradicts/unsupported chips, red gate banner, "Ablehnen" button outline |
| Warning | `#b26a00` on `#fff4e0` | overstated/partial/escalation chips, amber banner, ⚠ lines |
| Success | `#1e7b34` on `#e6f4ea` | supports chip, ✓ bestätigt, green banner |
| Neutral chip | `#5b616b` on `#eceef1` | framing chip |

Accent reserved for: primary "Freigeben" button and links only. Dark mode: `@media (prefers-color-scheme: dark)` swaps background `#121417`, cards `#1d2026`, text `#e7e9ec`; chips keep hue.
Verdict is never conveyed by color alone — chips always carry text.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | `Freigeben` (disabled + label `Freigeben (gesperrt)` when gate not green) |
| Secondary CTA | `Änderungen anfordern` |
| Destructive CTA | `Ablehnen` |
| Ack button | `Bestätigen` |
| Verdict chips | `GESTÜTZT`, `TEILWEISE`, `ÜBERZOGEN`, `UNGESTÜTZT`, `WIDERSPRICHT`, `RAHMEN`, escalation `↑ Sicherheit erhöht`, hidden claim `versteckte Aussage` |
| Empty state heading | `Nichts zu prüfen` |
| Empty state body | `Neue Skripte erscheinen hier nach „ndc script verify". Zuletzt entschieden: siehe unten.` |
| Error: stale version (409) | `Diese Version ist veraltet — es gibt eine neuere. Zur aktuellen Version →` |
| Error: invalid form/nonce (400) | `Formular abgelaufen. Seite neu laden und nochmal versuchen.` |
| Error: not found (404) | `Nicht gefunden.` (no detail, no path echo) |
| Error: server (500) | `Fehler beim Speichern. Nichts wurde geändert.` (no traceback) |
| Note required | `Bitte kurz begründen.` |
| Confirm banner after decision | `Freigegeben ✓` / `Änderungen angefordert` / `Abgelehnt` · time |
| Destructive confirmation | `Ablehnen`: no extra dialog; requires a non-empty note (≥5 chars) — the note is the confirmation |

---

## Interaction Rules

- Every POST carries hidden fields `script_sha` and `nonce`; server re-checks gate + latest-version inside the write transaction.
- After any POST: 303 redirect to `GET /r/<sha>#<anchor>` (ack → card anchor; decision → top).
- "Freigeben" only rendered as enabled when the gate is green; the server enforces regardless of what the page showed.
- No auto-refresh; a "Neu laden" link in the header.
- Page weight target < 60 KB for a 20-sentence script.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| none | — | no third-party UI code; no CDN |

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS (all states, German, no jargon beyond verdict labels)
- [x] Dimension 2 Visuals: PASS (single column, risk-first ordering, collapsed low-risk groups)
- [x] Dimension 3 Color: PASS (60/30/10, text-labelled verdicts, dark mode)
- [x] Dimension 4 Typography: PASS (5 roles, ≥15px body on phone)
- [x] Dimension 5 Spacing: PASS (multiples of 4)
- [x] Dimension 6 Registry Safety: PASS (no external assets)

Self-checked inline (no gsd-ui-checker subagent, per operator).

**Approval:** pending operator review
