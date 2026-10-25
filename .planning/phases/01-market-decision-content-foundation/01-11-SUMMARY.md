---
phase: 01-market-decision-content-foundation
plan: 11
subsystem: competitor-scan
tags: [mkt-01, judging, in-session, en, evidence-guard]
requires: [01-08]
provides:
  - "llm_session judgments for all 18 accounts of batch en-1 (scan_run 31)"
  - "docs/judging/en-1.md batch report (guard downgrades, operator queue, level distribution, S_EN candidates)"
affects: [01-13, 01-15]
tech-stack:
  added: []
  patterns:
    - "Judgments generated from a per-account spec by a scratch script that asserts every evidence string is a literal (whitespace-normalised) substring of the bundle text before writing"
key-files:
  created:
    - docs/judging/en-1.md
    - /home/nd-content-volumes/data/judging/en-1/judgments.json (data volume, not in git)
  modified: []
decisions:
  - "Photo-carousel accounts (adhdsciences, adhdventurers) recorded as format text_on_screen with low confidence (de-1/de-2 precedent), so they reach the operator queue"
  - "additudemag (ADDitude magazine) scored text 2 / video 2 for habitually naming interviewed experts and showing expert lower thirds; flagged as institutional for the operator, like adhs_deutschland"
  - "Off-niche accounts (GenericArtDad politics, le0zs gaming memes, goxlr__ fan edits) judged normally at score 0 with empty pillars/audiences and recommended for exclusion from the EN set"
  - "A YouTube Health reviewer disclaimer naming Patrick LaCount, PhD (HowtoADHD) scored L2 as a named credentialed reviewer; it occurs once, so it does not affect the account level"
metrics:
  duration: "~25 min"
  completed: 2026-10-25
  tasks: 2
---

# Phase 1 Plan 11: In-session judging of batch en-1 Summary

All 18 English accounts in batch en-1 were judged in-session against rubric v1 with no API call, and imported through the evidence guard with provenance `llm_session`. The guard checked 274 citation entries and downgraded none, and 10 accounts are queued for the operator. Only **additudemag** reaches score 2 (text 2, video 2), and it is the ADDitude magazine's institutional account. **No faceless, male-voiced account scores 2 or more, so batch en-1 contributes no S_EN candidate.**

## Task 1: judgments (data volume)

- `/data/judging/en-1/judgments.json` uses the rubric wrapper form and holds 18 judgments. `load_file` validated it inside the container, and the count matches the manifest.
- 16 citations are at level 1 or above: 15 in captions and 1 in speech. Each evidence string was asserted as a substring of the bundle text at build time. The 2 on-screen L2 citations are ADDitude lower thirds: "Patricia Quinn M.D." and "Melissa Orlov".
- `grep -rn anthropic src` finds no match.
- There is no git commit for this task, because its artifact lives on the data volume by design.

## Task 2: import and report (commit 01a1812)

- The import ran as scan_run 31: 18 imported, 0 downgraded, 10 queued.
- A read-only DB check found no batch account missing an `llm_session` `source_text_level`.
- `docs/judging/en-1.md` contains the import summary, "Guard downgrades" (none), "Queued for operator" with the reasons, S_EN candidates (none), the level distribution and a per-account table.

| Account | Score (t/v) | Face | Voice (pitch) | Flag |
|---|---|---|---|---|
| youtube:@HowtoADHD | 0 (0/0) | face | female | |
| tiktok:howtoadhd | 0 (0/0) | face | female | |
| tiktok:danidonovan | 0 (0/0) | mixed | female | |
| tiktok:adhddude | 0 (0/0) | mixed | male | clinician |
| youtube:@ADHDDude | 0 (0/0) | face | male | clinician |
| youtube:@PashaMarlowe | 0 (0/0) | face | unknown | clinician |
| youtube:@GenericArtDad | 0 (0/0) | face | unknown | off-niche |
| youtube:@Gossipduckling | 0 (0/0) | faceless | male | generalist |
| youtube:@SquirrelDad | 0 (0/0) | face | male | one L3 (Willcutt 2005), not habitual |
| youtube:@olivialutfallah | 0 (0/0) | face | female | |
| youtube:@AllAboutSpeechTherapy | 0 (0/0) | mixed | female | clinician/org |
| youtube:@sociallyausome | 0 (0/0) | face | female | |
| youtube:@additudemag | 2 (2/2) | face (interviewees) | female | institutional |
| tiktok:le0zs | 0 (0/0) | faceless | female | off-niche |
| tiktok:goxlr__ | 0 (0/0) | faceless | female | off-niche |
| tiktok:adhdsciences | 0 (0/0) | unknown (carousel) | male | |
| tiktok:adhdparenting_coachsue | 0 (0/0) | face | male (visible female) | |
| tiktok:adhdventurers | 0 (0/0) | unknown (carousel) | male | |

## Deviations from Plan

- **The plan's automated verify snippet expects a bare list.** As in de-1 and de-2, the rubric's wrapper object fails that snippet, so validation went through `load_file`, with the count asserted against the manifest.
- **There is no schema value for carousel.** Carousels are recorded as `text_on_screen` with low confidence.
- **Some signals have no vocabulary value.** Pasha Marlowe's coaching services, for example, are noted in `notes` only.

## Known Stubs

None.

## Threat Flags

None. No new code or network surface was added.

- Bundle content was treated as data (T-11-01).
- The guard ran with 0 downgrades (T-11-02).
- There is no API path (T-11-03).

## Self-Check: PASSED

- docs/judging/en-1.md: FOUND
- /home/nd-content-volumes/data/judging/en-1/judgments.json: FOUND
- commit 01a1812: FOUND
