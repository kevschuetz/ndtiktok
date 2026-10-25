---
phase: 01-market-decision-content-foundation
plan: 15
subsystem: topic-matrix
tags: [cont-01, cont-04, topic-seed, operator-review]
requires: [01-13, 01-05]
provides:
  - "config/topic_seed.yaml v1 (de): 72 in-session-drafted topics, 18 per pillar, 65 whitelist + 7 blacklist examples"
  - "Live DB: 65 topics in backlog (16/16/16/17 per pillar), 7 blacklist examples rejected with reason"
  - "docs/topic-backlog.csv: snapshot of the pruned backlog (65 rows)"
affects: [phase-02, phase-03]
tech-stack:
  added: []
  patterns:
    - "Seed is a reviewed YAML imported via `ndc topic import` (vocab validation + topic-level safety check); no runtime API call"
key-files:
  created:
    - config/topic_seed.yaml
    - tests/test_topic_seed.py
    - docs/topic-backlog.csv
  modified: []
decisions:
  - "Operator (2026-10-25): 'keep all' — all 65 whitelist topics kept; only the 7 blacklist examples killed with reason 'Beispiel ausgeschlossenes Thema'"
  - "matrix.yaml unchanged; AWMF coverage of LRS/Rechenstörung/UEMF is a Phase 2 follow-up (see below)"
metrics:
  duration: "~1 session + checkpoint"
  completed: 2026-10-25
  tasks: 3
---

# Phase 1 Plan 15: German topic seed and operator prune Summary

A 72-topic German seed spanning the full matrix was drafted in-session, imported through the safety-checked tooling, and pruned by the operator to a 65-topic backlog with every pillar at 16+ kept topics (target ≥ 7).

## Tasks

| Task | Name | Commits |
|------|------|---------|
| 1 | German topic seed + import (TDD) | 49b8c04 (RED), a8d8016 (GREEN) |
| 2 | Operator keep/kill (checkpoint) | — (DB state change only) |
| 3 | Backlog snapshot | 1947dba |

## Operator decision (Task 2)

Reply: "keep all". Applied:
- `ndc topic kill` 17, 18, 35, 36, 53, 54, 72 — reason "Beispiel ausgeschlossenes Thema" (medication choice, ADHD self-test, omega-3, "Autismus heilen durch Ernährung", "Ist mein Kind autistisch? Die Checkliste", ABA for toddlers, "Hat mein Partner ADHS? 10 Anzeichen"). All seven were already `safety_status=blocked` on import.
- `ndc topic keep` the other 65.
- `topic list --status proposed --format csv | wc -l` → 1 (header only).

## topic stats (after prune)

| pillar | proposed | backlog | rejected | kept (whitelist, ok/flagged) | target 7 |
|---|---|---|---|---|---|
| challenge_science_help | 0 | 16 | 2 | 16 | ok |
| strengths | 0 | 16 | 2 | 16 | ok |
| parents | 0 | 16 | 2 | 16 | ok |
| men_dads_partners | 0 | 17 | 1 | 17 | ok |

No pillar is below 7. Spread max−min = 1 (D-11).

## Filter check on real data (backlog)

| filter | rows |
|---|---|
| `--pillar parents` | 16 |
| `--condition dyslexia` | 5 |
| `--domain sensory` | 3 |
| `--audience dads` | 3 |
| `--angle myth_vs_research` | 9 |
| `--tag whitelist` | 65 |
| `--tag blacklist --status rejected` | 7 |

`docs/topic-backlog.csv` header: `id,pillar,condition,domain,audience,angle,working_title,list_tag,safety_status,source_likely,status`, 65 data rows.

## Operator finding — follow-up for Phase 2

The operator noted AWMF guidelines likely exist for non-ADHD/autism conditions the seed currently flags as `pubmed_reviews` (D-10):
- LRS (Lese-Rechtschreibstörung): AWMF 028-044
- Rechenstörung: AWMF 028-046
- UEMF (DCD/dyspraxia): AWMF 022-017

`config/matrix.yaml` and the seed's `source_likely`/notes were left unchanged; Phase 2 retrieval should check these guidelines and upgrade `source_likely` where they cover a topic.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: config/topic_seed.yaml (733 lines), tests/test_topic_seed.py, docs/topic-backlog.csv (66 lines)
- FOUND commits: 49b8c04, a8d8016, 1947dba
