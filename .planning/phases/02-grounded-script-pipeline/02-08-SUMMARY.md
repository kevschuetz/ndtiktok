---
phase: 02-grounded-script-pipeline
plan: 08
subsystem: script
tags: [edit, versioning, reuse]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-03 verify(only_ordinals)/reuse_key, 02-04 gate/latest"
provides:
  - "script/edit.py export/parse_import/import_edit; ndc script export <sha> [-o]; ndc script import <file>"
affects: [02-09, 02-10]
key-decisions:
  - "Version sha stays sha256(NFC text) (what Phase 3 diffs the recording against); marker-only edits with identical text are refused explicitly"
requirements-completed: [SCR-03, SCR-01]
duration: 20min
completed: 2026-10-26
---

# Phase 2 Plan 08: Edit flow Summary

**Fixing a flagged sentence costs one small verify call: edits become new hashed versions, unchanged sentences keep their verdicts, nothing inherits an approval.**

## Live result
- Exported v1 (34277f36…) to /data/edits/v1.txt; replaced sentences 6 and 8 with the verifier's own suggested fixes (verbatim).
- `ndc script import` → version 2, sha 670ab1d6e951139290ca9044533d8c1ef83c1a36787b1ec8d123d4310c76bfe6: "2 neu geprüft · 8 übernommen"; gate: 0 blockers, 1 open ack (sentence 2, TEILWEISE — left for the operator).
- v1 is now stale (gate blocker "veraltet").

## Deviations from Plan
1. **[Rule 4-lite, resolved by design] Marker-only edits refused** — text-only sha would collide (UNIQUE). The "deleted marker → forced unsupported" path is tested together with a text change.
2. Live demo changed two sentences (the two blockers) instead of one word.

## Next
02-06 Task 1, 02-09 Tasks 1–2, then both operator checkpoints together.
