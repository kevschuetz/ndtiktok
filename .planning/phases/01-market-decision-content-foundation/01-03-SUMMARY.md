---
phase: 01-market-decision-content-foundation
plan: 03
subsystem: scan-decision
tags: [pre-registration, decision-rule, mkt-02, sha256-lock]
requires: [01-01]
provides:
  - "docs/language-decision-rule.md: pre-registered rule (definitions, ordered V/R1-R4 table, account score), operator-approved 2026-10-24T21:02:55Z"
  - "config/decision_rule.yaml v1 (approved) + config/decision_rule.lock (sha256 ea401c5d7fd18e598fa8f18e759b75c45cbae982e066261c4e90df0b1f904b04)"
  - "ndc.scan.decide: AccountRow, DecisionResult, decide(accounts, rule) (pure), current_language(db), decision-log writer"
  - "ndc.scan.prereg: rule_sha256, lock_status, assert_rule_approved, record_scan_run, check_rule_unchanged (RuleNotApproved / RuleChanged)"
  - "ndc scan rule show; ndc scan decide --accounts-csv --log-path --amend"
  - "schema 003_decision.sql: scan_run, rule_amendment, language_decision"
affects: [01-04, 01-06, 01-08, 01-13]
tech-stack:
  added: []
  patterns:
    - "Pre-registration: sha256 lock written only after operator approval; scan_run stores the hash; changed rule -> exit 2 unless --amend (logged)"
    - "decide() evaluates only whitelisted conditions from the YAML, first match wins, verdict always de|en"
    - "One creator counts once per language for N/S (rows merged by lower-cased handle across TikTok/YouTube)"
key-files:
  created:
    - docs/language-decision-rule.md
    - config/decision_rule.yaml
    - config/decision_rule.lock
    - src/ndc/scan/decide.py
    - src/ndc/scan/prereg.py
    - src/ndc/schema/003_decision.sql
    - tests/scan/test_decide.py
    - tests/scan/test_prereg.py
  modified:
    - src/ndc/scan/cli.py
decisions:
  - "Rule approved by the operator exactly as drafted (V/R1/R2/R3/R4 per D-20, TikTok-only Q, YouTube reach reported only)"
  - "Operator approved counting one creator once across TikTok and YouTube (handle matching) for N_lang and S_lang"
  - "D-20 overrides the research table: research-draft extras in V, R2 and R3 were dropped"
metrics:
  completed: 2026-10-24
  tasks: 3
  tests: "135 passed (full suite)"
---

# Phase 1 Plan 03: Pre-registered language decision rule Summary

The D-20 language rule (validity floor 8 → German; German if N_DE ≤ 4 and Q ≤ 10; English if Q > 15; English if N_DE ≥ 8 and S_DE ≥ 1 and S_EN = 0; else German) is written, operator-approved and committed with a sha256 lock, before any scan data exists. `ndc scan decide` computes the verdict from account rows and refuses a silently changed rule.

## Pre-registration record

- Commit: `b644eae` — "docs(01-03): pre-register language decision rule (operator approved)"
- Commit time (`git log -1 --format=%cI -- config/decision_rule.lock`): **2026-10-24T21:03:08+00:00**. Plan 08 must find this earlier than the first `scan_run.started_at`.
- approved_by: operator, approved_at: 2026-10-24T21:02:55Z
- Rule sha256: `ea401c5d7fd18e598fa8f18e759b75c45cbae982e066261c4e90df0b1f904b04`
- `ndc scan rule show` prints `lock: ok` and the matching sha256.
- At approval no scan data existed. `/data/ndc.db` did not have the `scan_run` table yet (schema 003 had never been applied), so there were zero scan_run rows.

## Operator approval (verbatim)

Operator reply to the Task 2 checkpoint: **"Rule approved"**. The rule was approved exactly as drafted: V/R1/R2/R3/R4 per D-20, Q from TikTok mid-tier accounts only, and YouTube Shorts reach reported but never used in Q. The operator also explicitly approved counting one creator once across TikTok and YouTube, matched by handle, for N and S. Both points are recorded in the doc's Approval section.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 (RED) | Failing tests for decide() and the pre-registration guard | b413c5e |
| 1 (GREEN) | Rule doc + YAML, decide(), prereg, CLI, schema 003 | f35160c |
| 2 | Operator approval checkpoint | — (approved "Rule approved") |
| 3 | Approval recorded, lock written, dedicated commit | b644eae |

## Deviations from Plan

**1. [D-20 precedence] Dropped the research-draft extras in V, R2 and R3**
- **Found during:** Task 1
- **Issue:** The 01-RESEARCH.md table had three extra clauses that D-20 does not contain:
  - V had a fallback that recomputed Q over micro+mid combined before declaring the result inconclusive.
  - R2 had an "unless S_EN ≥ 3 and S_DE = 0 → inconclusive" exception.
  - R3 had an extra `Q ≤ 15` condition.
- **Fix:** The plan says D-20 is authoritative, so the YAML and the doc encode D-20 exactly: V checks mid-tier only and goes straight to German; R2 is plain Q > 15; R3 has no Q term. In R3 the Q ≤ 15 term is redundant anyway, because R2 already caught Q > 15 by the time R3 is evaluated. The operator approved this version.
- **Files:** config/decision_rule.yaml, docs/language-decision-rule.md

**2. [Clarification] Handle-merge counting** — The YAML/doc state that a creator is counted once per language, merging rows by lower-cased handle. The operator explicitly confirmed this at approval.

## TDD Gate Compliance

RED `test(01-03)` b413c5e → GREEN `feat(01-03)` f35160c. No refactor commit.

## Known Stubs

None. `docs/language-decision.md` (the decision log) is deliberately not created here. `ndc scan decide` writes it when plan 13 makes the decision.

## Requirements

MKT-02 stays **Pending**. This plan covers its first half (the rule is written down and approved before the scan). The decision from scan data is made in plan 13.

## Self-Check: PASSED

- FOUND: config/decision_rule.lock, config/decision_rule.yaml, docs/language-decision-rule.md, src/ndc/scan/decide.py, src/ndc/scan/prereg.py, src/ndc/schema/003_decision.sql
- FOUND commits: b413c5e, f35160c, b644eae
- Lock sha256 matches sha256(config/decision_rule.yaml); full test suite 135 passed
