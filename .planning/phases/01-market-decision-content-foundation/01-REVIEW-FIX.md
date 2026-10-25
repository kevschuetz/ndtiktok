---
phase: 01-market-decision-content-foundation
fixed_at: 2026-10-25T00:00:00Z
review_path: .planning/phases/01-market-decision-content-foundation/01-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-10-25
**Source review:** .planning/phases/01-market-decision-content-foundation/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (operator scope "Fix critical + high now": CR-01, HI-01..05, plus ME-02 and LO-03)
- Fixed: 8
- Skipped: 0
- Suite: 381 passed, 0 failed; ruff clean

## Fixed Issues

### CR-01: Safety matcher false negatives
**Files modified:** `config/safety.yaml`, `src/ndc/checks/_match.py`, `src/ndc/checks/text.py`, `src/ndc/checks/rules.py`, `tests/checks/test_safety.py`
**Commit:** 73e9854
**Applied fix:** safety.yaml v2 (revised_at + revision_note, approval fields kept; operator should glance at the extended list). New patterns for diagnosis listicles/modal questions/tests/"wie bekomme ich … Diagnose", drug words (drugs, prescri*, Psychopharmaka, Arznei*, Neurolepti*, verschreib*), more drug names with trailing genitive s, self harm/self-injury with a space, "end my life", "want to die", umbringen, "nicht mehr leben", supplements (vitamins, magnesium, zinc, CBD, iron, fish oil; DE equivalents), lowercase "aba therapy", "Binge Eating" with a space. Soft hyphen/zero-width chars are stripped before matching, and spans map back to the original text. All 23 probes and variants are pinned as regression tests, and approved wording is pinned block-free. Precision corpora still have no block findings.

### ME-02: Topic safety frozen at insert
**Files modified:** `src/ndc/topics.py`, `src/ndc/topics_cli.py`, `tests/test_topics.py`
**Commit:** e287e00
**Applied fix:** `select` re-checks under the current rules. New `ndc topic recheck [id]`. Ran on the live DB under v2 after a backup (`/data/ndc.db.bak-pre-safety-v2-20261025`): 0 topics changed. All 65 backlog topics stay ok with no hits; the 7 rejected topics stay blocked.

### HI-01: Evidence guard accepts trivial evidence
**Files modified:** `src/ndc/scan/judging.py`, `src/ndc/scan/queue.py`, `tests/scan/test_judging.py`
**Commit:** 0cb2727
**Applied fix:** `supported_level()` sets minimum lengths per level (8/12/15 chars) and requires at least 2 words. Level 3 also needs a DOI/PMID/link/year, and level 2 a named source. Evidence that fails drops to the level it supports and is counted as downgraded. DE accounts with text level >= 2 are queued for the operator. Status: fixed, requires human verification (heuristic thresholds).

### HI-02: On-screen citations unverified
**Files modified:** `src/ndc/scan/judging.py`, `src/ndc/scan/queue.py`, `tests/scan/test_judging.py`
**Commit:** 2b17952
**Applied fix:** the import refuses the whole file on an unknown or non-ok video_id, or an unknown post_id. A score >= 2 that rests only on on-screen citations is queued for EN and DE.

### HI-03: decide runs on an unapproved rule
**Files modified:** `src/ndc/scan/cli.py`, `src/ndc/scan/decide.py`, `src/ndc/scan/prereg.py`, `src/ndc/schema/007_decision_provenance.sql`, `tests/scan/test_prereg.py`, `tests/scan/test_decide_db.py`
**Commit:** fb7a5a6
**Applied fix:** the lock is checked first. If it is not ok and no `--amend` is given, decide exits 3 and writes nothing, including any amendment row. The log section and the new language_decision columns now record lock status, amendment id/reason and input source (with the CSV sha256). The rule, its lock and the existing decision row are unchanged.

### HI-04: Quiet hours checked only at start
**Files modified:** `src/ndc/scan/quiet_hours.py`, `src/ndc/scan/fetch.py`, `src/ndc/scan/analyze.py`, `src/ndc/scan/discover.py`, tests
**Commit:** 877de23 (discover test in 23c0a51)
**Applied fix:** per-item `quiet_hours.entered()` checks in analyze, fetch and discover. When quiet hours start mid-run, the run stops cleanly with a `stopped_quiet_hours` note and can be resumed. `--force` still keeps running.

### HI-05: analyze marks never-attempted accounts analyzed
**Files modified:** `src/ndc/scan/analyze.py`, `tests/scan/test_analyze.py`
**Commit:** ea95cf4
**Applied fix:** not-attempted videos are stored as `skipped` with analyzed_at NULL. An account whose videos were all not attempted is not stored. An account now counts as done only with at least one ok video. Status: fixed, requires human verification (logic change).

### LO-03: test_discover coupled to live config
**Files modified:** `tests/scan/test_discover.py`
**Commit:** 23c0a51
**Applied fix:** autouse fixture config with pinned discovery knobs/queries.

---

_Fixed: 2026-10-25_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
