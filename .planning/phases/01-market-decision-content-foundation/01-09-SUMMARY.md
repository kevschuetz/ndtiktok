---
phase: 01-market-decision-content-foundation
plan: 09
subsystem: competitor-scan
tags: [mkt-01, judging, in-session, dach, evidence-guard]
requires: [01-08]
provides:
  - "llm_session judgments for all 12 accounts of batch de-1 (scan_run 29)"
  - "docs/judging/de-1.md batch report (guard downgrades, operator queue, level distribution)"
affects: [01-13, 01-15]
tech-stack:
  added: []
  patterns:
    - "Evidence strings pre-checked as literal substrings of bundle text before import, then re-checked by the importer guard"
key-files:
  created:
    - docs/judging/de-1.md
    - /home/nd-content-volumes/data/judging/de-1/judgments.json (data volume, not in git)
  modified: []
decisions:
  - "Photo-carousel accounts are recorded as format text_on_screen with low confidence (the schema has no carousel value), so they reach the operator queue"
  - "English-language channel @VisualKnowledge in the DE batch is flagged low-confidence on pillars/audiences so the operator can check its language label before it counts toward N_DE"
metrics:
  duration: "~25 min"
  completed: 2026-10-25
  tasks: 2
---

# Phase 1 Plan 09: In-session judging of batch de-1 Summary

All 12 DACH accounts in batch de-1 were judged in-session against rubric v1 and imported through the evidence guard with provenance `llm_session`. No API call was made. The guard checked 181 citation entries and downgraded none. 5 accounts are queued for the operator, and none of them was queued by the DACH decision rules. Only **luciemenow** cites sources habitually: text 3, video 2, score 3.

## Task 1: judgments (data volume)

- `/data/judging/de-1/judgments.json` is in the rubric's wrapper form and holds 12 judgments. `load_file` validated it inside the container, and the count matches the manifest.
- Every caption and pinned comment got a level; each transcript-analyzed video got speech levels plus face and format from the contact sheet.
- The 15 citations at level >= 1 were each asserted to be a literal substring of the bundle text when the file was built.
- No on-screen citation of level >= 1 appeared in any contact sheet.
- `grep -rn anthropic src` finds no match.
- There was no git commit for this task: its artifact lives on the data volume by design.

## Task 2: import and report (commit 512f882)

- `ndc scan import-judgments` ran as scan_run 29: 12 accounts imported, 0 downgraded, 5 queued.
- A read-only DB check found 0 batch accounts missing a `llm_session` `source_text_level`.
- The report `docs/judging/de-1.md` has the import summary, "Guard downgrades" (none), "Queued for operator" with reasons, the level distribution and a per-account table.

| Account | Score (t/v) | Face | Voice (pitch) | Format |
|---|---|---|---|---|
| kirmesimkopf | 0 (0/0) | face | female | talking_head |
| nessadhs | 0 (0/0) | face | female | skit |
| @adhsautismus | 0 (0/0) | faceless | female | mixed |
| @VisualKnowledge | 0 (0/0) | face | male | talking_head |
| susis_synapsensalat | 0 (0/0) | mixed | female | text_on_screen |
| adhsabenteuer | 0 (0/0) | unknown | unknown | carousel→text_on_screen |
| christian_durstewitz | 0 (0/0) | faceless | unknown | voiceover_broll |
| user8445982006957 | 0 (0/0) | faceless | unknown | voiceover_broll |
| neuroceline | 0 (0/0) | face | female | talking_head |
| meinadhsleben | 0 (0/0) | unknown | female | carousel→text_on_screen |
| neuropinguin | 0 (0/0) | faceless | male | animation |
| luciemenow | 3 (3/2) | face | female | talking_head |

Queued accounts:
- adhsabenteuer and meinadhsleben: carousels; face and slide text can't be seen.
- @VisualKnowledge: English content in the DE batch.
- user8445982006957: dark-psychology dating channel, doubtful as an ND competitor.
- christian_durstewitz: pitch estimate only.

## Deviations from Plan

- **The plan's automated verify snippet assumes a bare JSON list.** It iterates `json.load(...)` directly, which fails on the rubric's wrapper object (`{"batch", "rubric_version", "provenance", "judgments"}`). The file follows the rubric (the authoritative output contract), and `load_file` accepts both forms. Validation ran through `load_file`, with the count asserted against the manifest.
- **Carousel has no schema value.** It is recorded as `text_on_screen`, with low confidence and a note.

## Known Stubs

None.

## Threat Flags

None. No new code or network surface. Bundle content was treated as data (T-09-01). The guard ran with 0 downgrades (T-09-02). No API path (T-09-03).

## Self-Check: PASSED

- docs/judging/de-1.md: FOUND
- /home/nd-content-volumes/data/judging/de-1/judgments.json: FOUND
- commit 512f882: FOUND
