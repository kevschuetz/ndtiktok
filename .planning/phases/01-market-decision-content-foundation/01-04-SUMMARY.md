---
phase: 01-market-decision-content-foundation
plan: 04
subsystem: competitor-scan
tags: [mkt-01, scraping, yt-dlp, provenance, discovery, polite-fetch]
requires: [01-01, 01-03]
provides:
  - "ndc scan import-candidates | discover youtube | discover modash | fetch --stage profile|posts | add-manual | select | export --csv|--accounts-csv"
  - "schema 004_competitor.sql: competitor_candidate, competitor_account, competitor_post, competitor_field_obs, v_competitor_sheet"
  - "ndc.scan.handles (validate before URL), ndc.scan.tiktok / ndc.scan.youtube (network split from pure parsers), ndc.scan.quiet_hours"
  - "ndc.scan.fetch: gate() (rule lock -> quiet hours -> scan_run), Polite (3-6 s jitter, tenacity backoff, stop after 3), run_fetch, import_candidates, add_manual"
  - "ndc.scan.select.select(db, lang) and ndc.scan.sheet.export_sheet / export_accounts (AccountRow CSV for decide)"
  - "config/scan.yaml (seeds, queries, quotas, politeness, quiet hours); scan/candidates.csv (D-04 seeds)"
  - "docs/scan-discovery-sources.md: live verdict per discovery source"
affects: [01-06, 01-07, 01-08, 01-13]
tech-stack:
  added: []
  patterns:
    - "Every network scan command: assert_rule_approved -> quiet-hours check -> one scan_run under the rule sha256 (exit 3 / exit 4)"
    - "Network calls return before any DB transaction opens; each account's rows are written in one short transaction after the fetcher returns"
    - "Per-field provenance in competitor_field_obs; v_competitor_sheet picks operator_verified > operator_entered > llm_session/auto > scraped, then newest"
    - "Field-obs names for later plans: source_citing_score (final/operator), source_text_level, source_video_level, face, voice_gender, format, pillars, audiences, monetization_signals, needs_operator_check"
key-files:
  created:
    - config/scan.yaml
    - scan/candidates.csv
    - docs/scan-discovery-sources.md
    - src/ndc/schema/004_competitor.sql
    - src/ndc/scan/handles.py
    - src/ndc/scan/tiktok.py
    - src/ndc/scan/youtube.py
    - src/ndc/scan/quiet_hours.py
    - src/ndc/scan/fetch.py
    - src/ndc/scan/select.py
    - src/ndc/scan/sheet.py
    - src/ndc/scan/discover.py
    - tests/scan/test_parse.py
    - tests/scan/test_fetch.py
    - tests/scan/test_quiet_hours.py
    - tests/scan/test_select.py
    - tests/scan/test_sheet.py
    - tests/scan/test_discover.py
    - tests/fixtures/scan/tt_flat.json
    - tests/fixtures/scan/tt_profile.html
    - tests/fixtures/scan/yt_shorts_flat.json
    - tests/fixtures/scan/yt_video.json
    - tests/fixtures/scan/ytsearch.json
  modified:
    - src/ndc/scan/cli.py
decisions:
  - "Discovery verdicts: ytsearch and Modash public pages scripted; TikTok Creative Center, Exolyt and Favikon operator-browser (JS app shell / login / Cloudflare interstitial); TikTok in-app search stays the documented fallback"
  - "Posts stage targets selected accounts by default (or --only HANDLE); profile stage targets all non-excluded candidates"
  - "Selection order inside a tier pool is a deterministic sha256 of platform:handle (reproducible, not size-biased); seeds under 1000 followers are not selected but recorded"
  - "Final source_citing_score in the sheet = operator value if present, else max(source_text_level, source_video_level), per the approved rule"
  - "A discovered handle already listed under the other language is flagged in notes for the operator, never relabelled automatically"
metrics:
  duration: "~20 min"
  completed: 2026-10-24
  tasks: 4
  tests: "216 passed (full suite); 108 in tests/scan/"
---

# Phase 1 Plan 04: Competitor-scan collection tooling Summary

Competitor collection for MKT-01 now works end-to-end on real data. Candidates come from the D-04 seeds plus scripted discovery: YouTube `ytsearch` and Modash public pages. Public TikTok and YouTube Shorts stats are fetched politely, behind the pre-registered rule lock and the quiet-hours guard. Each language gets a tier-stratified sample of ~40, and the sheet exports every MKT-01 field with per-field provenance.

## What was built

- **Parsers (Task 1).** `handles.py` validates handles before any URL is built. TikTok handles must match `^[A-Za-z0-9._]{2,24}$`; YouTube accepts a `UC…` id or an `@handle`. `tiktok.py` gets the flat listing through the yt-dlp Python API and the profile through one plain GET (20 s timeout, 5 MB cap, no cookies). `youtube.py` reads the Shorts flat listing, then per-video metadata including the uploader's pinned comment. The newest-15 rule is pinned by synthetic fixtures: posts ≥ 72 h old, sorted by timestamp, pinned posts excluded, fewer than 8 → None.
- **Fetch (Task 2).** Schema 004, `config/scan.yaml` and candidate import with handle rejection. `fetch --stage profile|posts` is gated: exit 3 when the rule is unapproved, exit 4 in quiet hours, `--force` override logged. It runs single-threaded with 3–6 s jitter, tenacity backoff on 429/403/5xx, and stops a platform after 3 consecutive failures (`stopped_failures`). It resumes via `fresh_hours`. `add-manual` stores operator-typed followers and views as `operator_entered`.
- **Select and sheet (Task 3).** `select` applies operator include/exclude first, then seeds, then tier quotas (mid ≥ 12, micro/macro ~10, mega ≤ 5, TikTok-weighted 28/12). A mid shortfall such as "mid tier shortfall: 7 of 12" is stored in a `select` scan_run and printed. `v_competitor_sheet` plus `export --csv` and `export --accounts-csv` produce the sheet; the second writes exactly the AccountRow columns, which load back through `scan decide`'s reader.
- **Discovery and smoke run (Task 4).** `discover youtube` and `discover modash`, the live source verification doc, and a real end-to-end fetch.

## Live smoke run (2026-10-24, 21:18–21:26 UTC, real `/data/ndc.db`)

| Command | Result |
|---|---|
| `scan import-candidates scan/candidates.csv` | inserted 11, rejected 0 |
| `scan fetch --stage profile --only kirmesimkopf` | followers 5046, tier micro (scan_run 1) |
| `scan fetch --stage posts --only kirmesimkopf` | 30 posts, 15 in reach window, median 1181, saves/1k 2.54, shares/1k 10.71 (scan_run 2) |
| `scan fetch --stage profile/posts --only @HowtoADHD` | 1.96 M subscribers, mega; 18 per-video calls, median 9473, 1 uploader pinned comment (scan_runs 3–4) |
| `scan discover youtube --lang de` | 10 queries, 100 channels seen, 5 new (scan_run 5) |
| `scan discover youtube --lang en` | 10 queries, ~101 channels seen, 0 new; @SensoryBlum flagged for language (scan_runs 6–7) |
| `scan export --csv / --accounts-csv` | 2 rows each, provenance `scraped`, cadence 1.06 and 0.93 posts/week |

Row counts after the run:
- scan_run 7, all under rule sha256 `ea401c5d…04b04`
- competitor_candidate 16
- competitor_account 2
- competitor_post 60 (30 per account)
- competitor_field_obs filled for both accounts

TikTok did not block the plain profile GET or the yt-dlp listing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Language mislabelling of discovered YouTube channels**
- **Found during:** Task 4 live run.
- **Issue:** a channel is inserted under the language of the query that found it first. "Tourette" and "AuDHD" are the same term in DE and EN, so English channels (e.g. @SensoryBlum, @PashaMarlowe) were listed as `de`. The EN run then silently counted them as "already listed".
- **Fix:** `fetch.note_language_conflict` appends "also found by <lang> ytsearch queries: check language" to the candidate's notes, and the CLI prints the conflict. Nothing is relabelled automatically, so the operator decides. Regression test `test_other_language_match_is_flagged`.
- **Files modified:** src/ndc/scan/fetch.py, src/ndc/scan/discover.py, src/ndc/scan/cli.py, tests/scan/test_discover.py
- **Commit:** e55f929

**2. [Rule 2 - Missing critical] Extra account/post columns beyond the plan's list**
- **Issue:** resumability and the reach rule need per-stage timestamps and the reach window.
- **Fix:** added `attempted_at`, `posts_fetch_status`, `posts_captured_at`, `reach_median`, `n_reach_posts`, `channel_id` and `fetch_error` on competitor_account. Added `pinned`, `in_reach_window` and `provenance` on competitor_post. A failed fetch never sets `captured_at`, so failures retry and successes are skipped.
- **Commit:** ce70065

### Process notes

- Task 2 was implemented together with its tests, so no separate RED commit exists for it. Tasks 1 and 3 have test-then-feat commit pairs.
- The YouTube live fetch of @HowtoADHD went beyond the plan's single kirmesimkopf smoke run (19 requests, same politeness). It confirmed the YouTube code path on real data.

## Findings for plan 07 (operator decisions, not changed here)

- With `discovery.min_niche_shorts: 3`, ytsearch keeps very few channels: 5 DE, 0 new EN. Most channels appear only 1–2 times across a language's queries. Consider 2.
- EN TikTok seed handles (howtoadhd, danidonovan, adhd_alien, adhddude) and YouTube `@ADHDDude` are unverified guesses, marked in the CSV notes. The profile fetch will confirm or reject them.
- Modash public pages are generic top-20 lists. No ADHD/neurodivergence topic page was confirmed within the 3-GET cap.

## Known Stubs

These sheet columns are NULL by design until later plans fill them: `source_citing_score` and its levels, `face`, `voice_gender`, `format`, `pillars`, `audiences`, `monetization_signals` and `needs_operator_check`. Plans 06 and 08–12 write them as competitor_field_obs rows using the field names listed in the frontmatter. They do not block this plan's goal, which is collection tooling.

## Threat Flags

None. All new network surface (TikTok profile/listing, YouTube Shorts/video, ytsearch, Modash public pages) is covered by T-04-01..T-04-04 in the plan.

## Self-Check: PASSED

- All files in key-files exist.
- Commits found: 27407f4, 6610b1f, ce70065, a6964d8, b207e1b, e55f929.
- `bash scripts/test.sh tests/` → 216 passed. The grep gates (no subprocess/evasion libraries, no Instagram, no captcha/solve/bypass in discover.py) return no match. `scan_run` count on `/data/ndc.db` is 7.
