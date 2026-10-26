---
phase: 02-grounded-script-pipeline
plan: 04
subsystem: review
tags: [gate, approval, sqlite, source-list]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-03 claim_verdict/review/claim_ack"
provides:
  - "review/gate.py: gate(db, version_id, conn=None), cards(), sorted_cards(), RISK_ORDER, VERDICT_LABELS_DE, GATE_HOOKS (hook(conn, version_id) -> [Issue]; kind starting 'block' = blocker)"
  - "review/store.py: ack/decide (BEGIN IMMEDIATE + gate re-check), latest_decision, version_by_sha, ReviewRefused"
  - "ndc review status|show|ack|decide; ndc script sources <sha> [--variant caption|comment]"
  - "script/sources_list.py render/pack_comments; config/source_list.yaml"
affects: [02-06, 02-07, 02-08, 02-09]
key-decisions:
  - "Gate re-runs the term/safety checks live (so a later recorded override clears needs_override) instead of trusting the stored check_status"
  - "GATE_HOOKS take (conn, version_id) — hooks run inside decide()'s transaction connection"
  - "Shared test helpers live in tests/<pkg>/<pkg>_helpers.py — never import from a module named conftest (collides across rootdir-less packages)"
requirements-completed: [SCR-03, SCR-04]
duration: 30min
completed: 2026-10-26
---

# Phase 2 Plan 04: Review gate + source list Summary

**One gate decides approvability; acks and approvals bind to the exact script hash inside the write transaction; the source list is rendered only from cited DB rows.**

## Live result
- `ndc review show 34277f36` renders banner "✗ Nicht freigebbar — 2 Blocker", the script, and risk-sorted cards (6, 8 blockers → 2 partial → supports → framing) with German claim, verbatim English source sentence, verifier note and fix.
- `ndc review decide 34277f36 approved` → exit 1: "nicht freigebbar: Satz 6 … Satz 8 … Satz 2: TEILWEISE — bestätigen"; no review row written.
- Rendering a live source list needs an approved version — demonstrated after the plan-08 edit cycle (test covers the exact output format).

## Deviations from Plan
1. **[Rule 1] Gate recomputes checks live** (see decisions).
2. **[Rule 3] Hook signature (conn, version_id)** instead of (db, version_id).
3. **[Rule 3] Test helper layout** (review_helpers.py); the render integration test lives in tests/review/test_review_store.py, the pure packer test in tests/script/test_sources_list.py.

## Next
Wave 5: 02-06 (AWMF), 02-08 (edits), 02-09 (web UI).
