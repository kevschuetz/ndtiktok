---
phase: 01-market-decision-content-foundation
plan: 07
subsystem: competitor-scan
tags: [mkt-01, discovery, candidate-selection, operator-review]
requires: [01-04]
provides:
  - "Real competitor_candidate / competitor_account rows: 77 candidates, 50 selected (DE 20, EN 30), 12 excluded, 15 below-min/no-data"
  - "scan/candidates.csv with discovery_source per row and operator include/exclude decisions"
  - "docs/scan-run-log.md: discovery, profile fetch, candidate selection, operator review, final sample"
affects: [01-08]
tech-stack:
  added: []
  patterns:
    - "TikTok pool comes from operator in-app collection (tiktok_app); no scripted TikTok source is niche-specific"
    - "Executor suggests exclude/relabel in notes; operator decides; operator-added rows are flagged, never excluded by the executor"
key-files:
  created:
    - docs/scan-run-log.md
  modified:
    - scan/candidates.csv
    - config/scan.yaml
decisions:
  - "config/scan.yaml discovery.min_niche_shorts 3 -> 2 and ytsearch_results 30 -> 60 (decision rule untouched)"
  - "Modash public pages not run: no ND/mental-health pages, only generic top-20 influencer lists"
  - "Operator: 'list edited' — applied 12 excludes + 5 de->en relabels, added 36 TikTok handles (18 de / 18 en); 4 'check niche' YouTube rows left to quota"
  - "Off-niche-looking operator rows (daily.katze, le0zs, goxlr__, user8445982006957, @Gossipduckling) flagged in the log, not excluded"
metrics:
  duration: "~30 min executor time across two sessions (plus operator collection)"
  completed: 2026-10-25
---

# Phase 1 Plan 07: Candidate discovery and final sample Summary

The live sample has 50 operator-reviewed accounts (DE 20, EN 30) with fetched followers. Mid-tier TikTok is 7 per language, below the validity floor of 8. TikTok's niche pool depends entirely on handles the operator collects in the app.

## Tasks

| Task | Name | Commit |
|---|---|---|
| 1 | Discover candidates, fetch followers, propose sample | 7a6f165 |
| 2 | Operator confirms/edits list ("list edited") | 48f0b68, 704bd89 (orchestrator) |
| 3 | Apply edits and finalize the sample | 7dccb3a |

## Final sample

| Language | Platform | micro | mid | macro | mega | total |
|---|---|---|---|---|---|---|
| de | tiktok | 9 | 7 | 2 | 0 | 18 |
| de | youtube | 2 | 0 | 0 | 0 | 2 |
| en | tiktok | 6 | 7 | 6 | 1 | 20 |
| en | youtube | 4 | 2 | 3 | 1 | 10 |
| **total** | | **21** | **16** | **11** | **2** | **50** |

- The target was ~40 per language (~80). The result is 50. Every row with ≥ 1000 followers that is not excluded is selected, so the pool size is the limit, not the quota.
- Mid-tier shortfall from `scan select`: DE 7 of 12, EN 9 of 12.
- **Mid-tier TikTok against the floor of 8:** DE 7 and EN 7. Six per language are clearly ND by bio; the other two, daily.katze (DE) and le0zs (EN), are unclear. Both languages fall short by 1–2.
- 0 mismatches between operator_decision and status.
- All 36 operator TikTok handles resolved. Seeds verena_eisbrenner and guardianofmind remain "not on platform".

## Deviations from Plan

- None in Task 3.
- Task 1 config changes (min_niche_shorts and ytsearch_results) are already documented in the run log.
- The run log's earlier mention of a `quiet_hours_override` column is inaccurate: `scan_run` has no such column. The real guarantee is that no `--force` was used and every run was outside 00:15–06:00 UTC, as the scan_run timestamps confirm.

## Known Stubs

None.

## Open items for the operator

Before plan 08 starts post collection:
- Decide whether to keep the flagged rows: daily.katze, le0zs, goxlr__, user8445982006957 and @Gossipduckling.
- Optionally add 2–4 more mid-tier ND TikTok handles per language to reach the floor of 8.

## Self-Check: PASSED

- FOUND: docs/scan-run-log.md (contains "Final sample")
- FOUND: scan/candidates.csv (78 lines)
- FOUND commits: 7a6f165, 48f0b68, 704bd89, 7dccb3a
