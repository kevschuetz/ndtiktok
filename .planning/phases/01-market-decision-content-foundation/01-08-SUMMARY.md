---
phase: 01-market-decision-content-foundation
plan: 08
subsystem: competitor-scan
tags: [mkt-01, collection, posts, faster-whisper, contact-sheet, judging-bundles]
requires: [01-06, 01-07]
provides:
  - "competitor_post rows for all 59 selected accounts (1681 posts, 861 in the reach window)"
  - "competitor_video rows for 58/59 selected accounts (172 ok, 2 unavailable), transcripts, pitch voice estimates, 48 contact sheets"
  - "judging batches de-1 (12), de-2 (12), en-1 (18), en-2 (17) under /data/judging/<batch>/manifest.json"
  - "import-candidates now propagates a language relabel to competitor_account"
affects: [01-09, 01-10, 01-11, 01-12, 01-13, 01-15]
tech-stack:
  added: []
  patterns:
    - "Collection in resumable per-language chunks; heavy analysis only in ndc-heavy"
key-files:
  created:
    - .planning/phases/01-market-decision-content-foundation/01-08-SUMMARY.md
  modified:
    - docs/scan-run-log.md
    - src/ndc/scan/fetch.py
    - tests/scan/test_select.py
    - .planning/phases/01-market-decision-content-foundation/deferred-items.md
decisions:
  - "Candidate language (operator-relabelled) is the truth; competitor_account.language is synced to it on re-import"
  - "Photo-carousel TikTok posts (audio-only format) get no contact sheet; recorded as a format signal for judging, not worked around"
metrics:
  duration: "~1 h 45 min"
  completed: 2026-10-25
  tasks: 2
---

# Phase 1 Plan 08: Post collection, local analysis and judging batches Summary

All 59 selected accounts now have post-level stats. 58 have locally analyzed videos (transcript,
pitch voice estimate and, for 48, a contact sheet). The four judging bundles that plans 09–12
read are packed. Usable mid-tier TikTok accounts (≥ 8 reach-window posts): **DE 8, EN 11**.
DE sits exactly on the validity floor.

## Pre-registration and politeness

- The rule commit b644eae (2026-10-24T21:03:08Z) precedes the first scan_run
  (2026-10-24T21:18:20Z). The rule and its lock were not touched.
- Every run happened between 07:45 and 09:25 UTC 2026-10-25, outside 00:15–06:00. No
  `--force` was used, and no scan_run note contains `quiet_hours_override`.
- Requests were single-threaded with 3–6 s jitter. There were no 429/403 platform stops, so no
  `add-manual` / `operator_entered` fallback was needed.

## Task 1: posts (scan_runs 25, 26)

- **DE** (07:45–07:51 UTC): ok 23, skipped fresh 1, failed 0.
- **EN** (07:56–08:16 UTC): ok 34, skipped fresh 1, failed 0.
- 1681 posts stored, 861 in the reach window.
- Accounts with ≥ 8 reach posts: DE 24/24, EN 34/35.
  - The one EN miss is **audhd30** (micro TikTok). All 30 listed posts are < 72 h old (about 30
    posts within one day), so none is eligible.
  - neuropinguin has exactly 8.
- Mid-tier TikTok, all with ≥ 8 reach posts:
  - DE 8: susis_synapsensalat, adhsabenteuer, neuroceline, adhs.reise, robin.haegle, bene_adhso,
    daily.katze, jannes_patrick.
  - EN 11: neuroduck0 has 13 reach posts, the rest have 15.

## Task 2: analysis (scan_runs 27, 28) and batches

| Platform | accounts with videos | ok | unavailable |
|---|---|---|---|
| TikTok | 46 / 47 | 137 | 1 (unique_adhd: no video formats) |
| YouTube | 12 / 12 | 35 | 1 (@SquirrelDad: HTTP 403) |

- 129 of the ok videos have a non-empty transcript; the rest are music-only.
- Mean wall-clock is ~23 s per video attempt, pacing included. DE ran 30 min, EN 35 min.
- Host memory stayed at ~4.5 GB available. The container peaked at ~1.15 / 3 GiB.
- No media files remain under `/home/nd-content-volumes/data/media`.
- Batch sizes: **de-1 12, de-2 12, en-1 18, en-2 17** (59 accounts). `scan queue`: queued 12,
  clear 74.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Language relabel never reached competitor_account**
- **Found during:** Task 2, while reading `bundle._accounts` before `prepare-judging`.
- **Issue:** `import-candidates` updated only `competitor_candidate.language`. Plan 07
  relabelled 3 selected channels (@PashaMarlowe, @AllAboutSpeechTherapy, @sociallyausome) from
  de to en. The account rows kept `de`, and the sheet (`v_competitor_sheet`) and the judging
  bundles group by account language. Those 3 EN channels would have counted toward DE and gone
  into the DE batches.
- **Fix:** the re-import now also updates `competitor_account.language` by candidate_id. Added
  a regression test, verified red without the fix and green with it. The fix was applied live
  by re-importing the unchanged `scan/candidates.csv`: 86 updated, 0 mismatches, selection
  unchanged (DE 22 TT + 2 YT, EN 25 TT + 10 YT).
- **Files modified:** src/ndc/scan/fetch.py, tests/scan/test_select.py
- **Commit:** 056a77f

### Known gaps (not fixed)

- **audhd30** has no competitor_video row. It has no eligible (≥ 72 h old) post, which conflicts
  with the "every selected account has a video row" criterion. The account drops out of reach
  metrics per the rule, and it is micro-tier, so the mid-tier floor is unaffected.
- **10 TikTok accounts have no contact sheet:** adhdsciences, adhdventurers, adhdautism4,
  myadhdventure, adhsabenteuer, meinadhsleben, gedankenflut.fuehlen, adhs.reise, adhdminds111,
  lebenmitadhs.
  - A one-request probe showed yt-dlp offers only an audio-only format for these posts. They are
    photo carousels with no video stream.
  - Transcripts and pitch exist for them.
  - Plans 09–12 should treat carousel as a format value and queue face/on-screen-citation fields
    when unsure.
  - adhsabenteuer and adhs.reise are DE mid-tier, so they are decision-relevant.
- **Pre-existing test failures (deferred-items.md):** test_discover.py has 2 failures that occur
  with or without this plan's change. 292 passed, 2 failed.

## Known Stubs

None.

## Threat Flags

None. No new network surface; the media deletion check (T-08-03) passed with 0 files.

## Self-Check: PASSED

- docs/scan-run-log.md contains "Collection — posts" and "Collection — analysis".
- All four manifests exist; media dir has 0 files.
- Commits 7d76cfc, 056a77f, 987fba0 exist.
