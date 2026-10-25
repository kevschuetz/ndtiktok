---
phase: 01-market-decision-content-foundation
plan: 13
subsystem: competitor-scan
tags: [mkt-01, mkt-02, language-decision, operator-spot-check, pre-registration]
requires: [01-09, 01-10, 01-11, 01-12]
provides:
  - "language_decision row 1: verdict de, row R1 (2026-10-25T11:07:11Z)"
  - "docs/language-decision.md (Validation week 1 section: metrics, matched row, S_DE answer, rule sha, pre-registration evidence, reasoning, operator rulings)"
  - "scan/competitor_sheet.csv (86 accounts, every MKT-01 field + per-field provenance)"
  - "ndc scan decide reads the selected sample from the DB by default (sheet.account_rows); --rule-committed-at logs the pre-registration check"
  - "ndc scan verify HANDLE --platform P --accept (operator review without changing values)"
affects: [01-14, 01-15]
tech-stack:
  added: []
  patterns:
    - "decide input = sheet.account_rows(db), the same rows export_accounts writes, so the DB and CSV paths give the same DecisionResult"
    - "accepted-unknown = an operator_review obs with method '(accepted as is)'; values stay as judged"
key-files:
  created:
    - tests/scan/test_decide_db.py
    - docs/language-decision.md
    - scan/competitor_sheet.csv
  modified:
    - src/ndc/scan/cli.py
    - src/ndc/scan/decide.py
    - src/ndc/scan/sheet.py
    - src/ndc/scan/verify.py
    - scan/candidates.csv
    - docs/scan-run-log.md
decisions:
  - "Milestone 1 language: German (rule row R1, decisive)"
  - "Operator: institutional accounts count as source-citing; repost credits do not"
  - "Operator: 4 off-niche English accounts excluded; daily.katze kept"
  - "Operator: carousel / uncertain face-voice-format fields accepted as unknown, no manual checks"
metrics:
  duration: "~30 min"
  completed: 2026-10-25
  tasks: 2
  tests: "296 passed, 2 deselected (pre-existing test_discover failures, deferred-items.md)"
---

# Phase 1 Plan 13: Language decision Summary

The pre-registered rule picked **German** (row R1). `ndc scan decide` read the 55 selected accounts from the DB
after the operator's spot-check rulings. Q = R_EN / R_DE = 4,722 / 8,423 = 0.56, and only 2 German accounts
cite sources (N_DE = 2). The competitor sheet is exported to `scan/competitor_sheet.csv`.

## Decide output (verbatim)

```
source: DB (selected sample); 55 accounts
R_DE: 8423.00
R_EN: 4722.00
Q: 0.56
n_mid_de: 8
n_mid_en: 9
N_DE: 2
N_EN: 1
S_DE: 0
S_EN: 0
youtube_R_DE: n/a  youtube_R_EN: 5984.50  (reported only, not in Q)
sourced DE: tiktok:adhs_deutschland, tiktok:luciemenow
sourced EN: youtube:@additudemag
slot (faceless+male) DE: none
slot (faceless+male) EN: none
pre-registration: lock committed 2026-10-24T21:03:08+00:00, first scan_run 2026-10-24T21:18:20Z, precedes: yes
matched row: R1
verdict: de
rule sha256: ea401c5d7fd18e598fa8f18e759b75c45cbae982e066261c4e90df0b1f904b04
logged to docs/language-decision.md
```

The rule was not amended: no `--amend` was used and `rule_amendment` is empty. The lock commit (b644eae,
2026-10-24T21:03:08Z) is earlier than the first scan_run (2026-10-24T21:18:20Z).

## Task 1: operator spot-check (resolved by operator rulings, 2026-10-25)

The queue held 32 accounts (12 DE, 20 EN). The operator ruled by category:

1. **"Institutional accounts COUNT as source-citing competitors."** tiktok:adhs_deutschland and
   youtube:@additudemag got `--set source_citing_score=2`. Only the TikTok adhs_deutschland exists in the
   sample; there is no YouTube one.
2. **"Repost credits are NOT source citing."** tiktok:theautismspectrum and tiktok:hypeneo1 got
   `--set source_citing_score=0`. Both are faceless + male English accounts, so S_EN went 2 → 0 and N_EN 3 → 1.
3. **"Exclude off-niche English accounts."** youtube:@GenericArtDad, tiktok:le0zs, tiktok:goxlr__ and
   tiktok:lix.psl got `operator_decision=exclude` in scan/candidates.csv, followed by
   `ndc scan import-candidates` (status → excluded). `select` was not re-run, so no backfill entered the
   sample. The selected sample went from 59 to 55 accounts. daily.katze was **kept** by explicit operator
   choice.
4. **"Carousel accounts and uncertain fields accepted as unknown/low-confidence."** The other 28 queued
   accounts, including the 4 excluded ones, were closed with the new `ndc scan verify HANDLE --accept`.

Result: `scan verify --queue` prints `0 account(s) queued`, and `scan queue` reports queued 0 / clear 86. The DB
holds 36 operator_verified rows: 4 source_citing_score and 32 operator_review.

## Key competitor-sheet findings (55 selected)

- German mid-tier TikTok reach has a higher middle than English: DE median 8,423 vs EN 4,722. English has a few
  big outliers (adhdminds111 131,900, neuroduck0 65,100, adhdautism4 41,500).
- Source citing at ≥ 2 is rare in both languages: DE 2 of 24, EN 1 of 31. In German this is an open lane.
- **S_DE = 0.** German faceless + male accounts exist (daily.katze, neuronbird, neuropinguin), but none cites
  sources. The planned slot (sourced, male, faceless, German) is empty.
- Formats: talking_head leads (DE 9, EN 13), then text_on_screen (DE 7, EN 6). Faceless: DE 6, EN 7.
- Median cadence: DE 3.6 posts/week, EN 1.6.
- Monetization: mostly none (DE 11, EN 12). Book and course are more common in EN (7 and 6).
- Pillars: challenge_science_help dominates. men_dads_partners is nearly unused (DE 1, EN 4), which matches the
  early bet.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] No way to close a queue item without changing a value**
- **Issue:** ruling 4 accepts uncertain fields as they are. `verify` required at least one `--set`, so the only
  options were inventing operator values or hand-editing the DB, and both are forbidden.
- **Fix:** added `--accept`. It writes only the `operator_review` obs (method suffix "(accepted as is)") and
  recomputes the flag, so the values and their provenance stay untouched. A test covers it.
- **Commit:** f138f82

**2. [Rule 2] Exclusion mechanism**
- The CLI has no exclude flag. Instead, the existing supported path was used: `operator_decision=exclude` in
  scan/candidates.csv, then `scan import-candidates`. `select` was not re-run because it would have
  backfilled unjudged accounts.

**3. Pre-registration timestamp**
- The container has no git, so `decide` gained `--rule-committed-at`. The host passes
  `git log -1 --format=%cI -- config/decision_rule.lock` to it, and `decide` compares that with the first
  scan_run from the DB.

**4. scan/ not mounted**
- The export ran with `-v $PWD/scan:/app/scan` because the compose service mounts only docs and config.

## Deferred Issues

- `bash scripts/test.sh tests/scan/` is not green because of 2 pre-existing failures in
  tests/scan/test_discover.py. Those were already logged in deferred-items.md during plan 08: the tests read
  the live discovery config. They are unrelated to this plan. Everything else passes: 296 passed, 2 deselected.

## TDD Gate Compliance

RED ba5ad75 `test(01-13)` → GREEN f138f82 `feat(01-13)`. No refactor commit.

## Commits

- ba5ad75 test(01-13): add failing tests for DB-sourced scan decide and verify --accept
- f138f82 feat(01-13): scan decide reads the sample from the DB; verify --accept
- 3da1101 docs(01-13): language decision R1 -> German from the spot-checked DB sample

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: docs/language-decision.md, scan/competitor_sheet.csv (264 lines, 86 rows), tests/scan/test_decide_db.py
- FOUND commits: ba5ad75, f138f82, 3da1101
- language_decision latest verdict = de (row R1); queue empty; rule lock unchanged
