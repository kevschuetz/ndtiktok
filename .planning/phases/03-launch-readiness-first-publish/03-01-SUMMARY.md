---
phase: 03-launch-readiness-first-publish
plan: 01
subsystem: publish
tags: [readout, pre-registration, publish-log, metrics, csv, cron]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "review.latest_decision (approval), sources_list.render, launch_sets (hashtags, crisis lines)"
provides:
  - "config/readout_rule.yaml v1 + config/readout_rule.lock; readout.py (lock/check_locked/amend) + readout_rule table; ndc readout show|lock|amend [--lock-out]"
  - "schema 013: readout_rule, publication, metric_snapshot (append-only)"
  - "publish/store.py: log_publication (approval + readout lock + PUBLISH_GATES hooks + host allow-list + TikTok-first cross-posts), render_caption/render_pinned (DB rows + config only); ndc publish log|caption|list"
  - "publish/metrics.py: add_snapshot, import_csv (config/metrics.yaml header map, raw_json), due (tolerance windows, platform scope), write_due (/data only); ndc metrics add|import|due|show"
affects: [03-03, 03-04, 03-05, 04]
key-decisions:
  - "Readout rule locked on the live DB 2026-10-29T19:59:50Z (sha dcf1855343b0…) — before any publication exists; lock file written on the host because /app/config is a read-only mount (code now writes the file before the DB row and offers --lock-out)"
  - "PUBLISH_GATES hook list: plan 03-03 appends the recording-approval check; until then a publication only needs an approved script + readout lock"
  - "Cross-posts must follow the TikTok row of the same script (replication, D-06); YouTube/Instagram are due for 7 d views only"
  - "Pinned comment gets the crisis short form for domains emotion_regulation, energy_burnout, late_identification (config/metrics.yaml)"
  - "Tolerant number parsing for TikTok exports (2.345 / 38,2 %); CSV headers mapped via config, unknown columns kept in raw_json; first real export (03-05) confirms the map"
requirements-completed: [MEAS-01, MEAS-02, MEAS-03]
duration: 70min
completed: 2026-10-29
---

# Phase 3 Plan 01: Readout rule, publish log, metric snapshots Summary

**The measurement side exists before video 1: a hash-locked, pre-registered go/no-go rule; an append-only publish log that refuses anything unapproved, unlocked or off-platform; fixed-age snapshots with a TikTok CSV import and a due-list file for the phone.**

## Live result
- `ndc readout lock` → `readout_rule` row 1, sha `dcf1855343b0…`, committed 2026-10-29T19:59:50Z; `config/readout_rule.lock` committed in git. `ndc readout show` → locked.
- `ndc publish caption fd07bd2c` (topic-3 v7) → caption with 2 cited sources + `#ADHS #Neurodivergent #ADHSbeiErwachsenen #Wissenschaft`; pinned comment `Quellen: Faraone 2019 (PMID 29624671); Soler-Gutiérrez 2023 (PMID 36608036)` + crisis short form (emotion_regulation).
- `ndc publish log … --script ce791e58` (unapproved v2) → „Skriptversion ist nicht freigegeben". `ndc metrics due --write /data/due.json` → `{"due": []}` written.
- Migration 013 applied on the live DB. Full suite 526 passed (21 new), ruff clean.

## Deviations from Plan
1. **[Rule 1] Read-only config mount** — `lock()` wrote the DB row and then failed on the lock file. Fixed: file first, then row; `--lock-out DIR` for containers; the live lock file was written on the host from the row values (same sha).
2. `config/metrics.yaml` created in Task 2 (needed for `pinned_crisis_domains`) and extended in Task 3.
3. Number parsing made tolerant of German formatting after the first CSV test failed (`2.345` parsed as 2).

## Follow-ups
- Install the host cron line (docs in 03-04) — operator/host action; the writer refuses paths outside `/data`.
- Hashtag selection is deterministic (broad by condition, first two niche tags, first pillar tag); the operator may swap tags in-app, the caption text stays the source of truth.
