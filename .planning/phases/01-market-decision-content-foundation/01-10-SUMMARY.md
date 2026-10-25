---
phase: 01-market-decision-content-foundation
plan: 10
subsystem: competitor-scan
tags: [mkt-01, judging, in-session, dach, evidence-guard]
requires: [01-08]
provides:
  - "llm_session judgments for all 12 accounts of batch de-2 (scan_run 30)"
  - "docs/judging/de-2.md batch report (guard downgrades, operator queue, level distribution)"
affects: [01-13, 01-15]
tech-stack:
  added: []
  patterns:
    - "Judgments generated from a per-account spec by a scratch script that asserts every evidence string is a literal substring of the bundle text before writing"
key-files:
  created:
    - docs/judging/de-2.md
    - /home/nd-content-volumes/data/judging/de-2/judgments.json (data volume, not in git)
  modified: []
decisions:
  - "Photo-carousel accounts (adhs.reise, gedankenflut.fuehlen, lebenmitadhs) recorded as format text_on_screen with low confidence, per the de-1 precedent, so they reach the operator queue"
  - "Named, findable legal/policy sources (Pflegereform-Regierungsentwurf, § 48a SchulG NRW) scored L2 under the rubric's 'named findable source' definition, noted as policy rather than scientific evidence"
  - "adhs_deutschland (ADHS Deutschland e.V.) scored text 2 for habitually naming interviewed experts + institutions; flagged as an institutional account the operator should include or exclude from N_DE / S_DE"
metrics:
  duration: "~20 min"
  completed: 2026-10-25
  tasks: 2
---

# Phase 1 Plan 10: In-session judging of batch de-2 Summary

All 12 DACH accounts in batch de-2 were judged in-session against rubric v1 and imported through the evidence guard with provenance `llm_session`, with no API call. The guard checked 182 citation entries and downgraded none. 7 accounts are queued for the operator. Only **adhs_deutschland** reaches score 2 (text 2, video 0), and it is the patient association's institutional account rather than a peer creator. All 12 accounts are German-language.

## Task 1: judgments (data volume)

- `/data/judging/de-2/judgments.json` uses the rubric wrapper form and holds 12 judgments. `load_file` validated it inside the container, and the count matches the manifest.
- 22 citations at level >= 1 (21 caption, 1 speech) were each asserted as literal substrings of the bundle text at build time. There is 1 on-screen L2 citation: the Prof. Philipsen lower third.
- `grep -rn anthropic src` finds no match.
- There is no git commit for this task, because its artifact lives on the data volume by design.

## Task 2: import and report (commit dbb1764)

- `ndc scan import-judgments` ran as scan_run 30: 12 imported, 0 downgraded, 7 queued.
- A read-only DB check found 0 batch accounts missing a `llm_session` `source_text_level`.
- `docs/judging/de-2.md` contains the import summary, "Guard downgrades" (none), "Queued for operator" with reasons, the level distribution and the per-account table.

| Account | Score (t/v) | Face | Voice (pitch) | Format |
|---|---|---|---|---|
| neuronbird | 0 (0/0) | faceless | male | animation |
| gedankenflut.fuehlen | 0 (0/0) | unknown | female | carousel→text_on_screen |
| adhs_positiv | 0 (0/0) | face | male | talking_head |
| adhs.reise | 0 (0/0) | unknown | female | carousel→text_on_screen |
| kopfkino.mit.untertitel | 0 (0/0) | face | male | text_on_screen |
| robin.haegle | 0 (0/0) | face | male | talking_head |
| bene_adhso | 0 (0/0) | face | female (visible male) | skit |
| daily.katze | 0 (0/0) | faceless | male | animation |
| jannes_patrick | 0 (0/0) | face | unknown | talking_head |
| leoniemachtsachen | 0 (0/0) | face | female | talking_head |
| adhs_deutschland | 2 (2/0) | face (interviewees) | unknown | talking_head |
| lebenmitadhs | 0 (0/0) | unknown | male | carousel→text_on_screen |

Queued accounts:
- **Carousels** (adhs.reise, gedankenflut.fuehlen, lebenmitadhs): faces and slides are not visible.
- **adhs_deutschland**: score 2. Queued on low voice confidence, and its institutional status is flagged.
- **bene_adhso**: the pitch estimate says female but the visible speaker is male.
- **daily.katze**: a generalist channel; ND relevance is doubtful.
- **jannes_patrick**: pitch only.

DACH rules:
- No account's speech or on-screen evidence lifts its score to >= 2.
- No faceless, male-voiced account scores >= 2. neuronbird and daily.katze score 0.

## Deviations from Plan

- **The plan's automated verify snippet expects a bare list.** As in de-1, the rubric's wrapper object fails that snippet. Validation went through `load_file` instead, with the count asserted against the manifest.
- **Carousel has no schema value.** It is recorded as `text_on_screen` with low confidence.

## Known Stubs

None.

## Threat Flags

None. No new code or network surface was added.
- Bundle content was treated as data (T-10-01).
- The guard ran with 0 downgrades (T-10-02).
- There is no API path (T-10-03).
- Brand-safety note: adhs_positiv's bio has a "therapeutic mushroom" affiliate code. This is recorded in the report.

## Self-Check: PASSED

- docs/judging/de-2.md: FOUND
- /home/nd-content-volumes/data/judging/de-2/judgments.json: FOUND
- commit dbb1764: FOUND
