---
phase: 01-market-decision-content-foundation
plan: 14
subsystem: launch-sets
tags: [mkt-03, hashtags, crisis-lines, operator-approval]
requires: [01-13, 01-02]
provides:
  - "ndc scan hashtags [--lang L] [--out scan/hashtag_harvest.yaml]: per-tag distinct accounts, post count, mid-tier median views; safety + community exclusions"
  - "config/hashtags.yaml v1 (de): 1 broad + 1-2 niche + 1 pillar (3-5 total), per-pillar tags + keywords, harvest stats, verified_in_app 2026-10-25"
  - "config/crisis_lines.yaml v1 (de): 12 AT/DE/CH entries with source_url + verified_at, pinned-comment short form, approved_at 2026-10-25"
  - "src/ndc/launch_sets.py: load_hashtags(), load_crisis_lines() pydantic loaders"
affects: [01-15, phase-02, phase-03]
tech-stack:
  added: []
  patterns:
    - "hashtag safety = worst checker status over the tag, the bare word and its camel-case split; any non-ok status excludes"
    - "crisis-line file is exempt from ndc check (names suicide-related services)"
key-files:
  created:
    - src/ndc/scan/hashtags.py
    - src/ndc/launch_sets.py
    - config/hashtags.yaml
    - config/crisis_lines.yaml
    - scan/hashtag_harvest.yaml
    - tests/scan/test_hashtags.py
  modified:
    - src/ndc/scan/cli.py
    - tests/test_config_files.py
decisions:
  - "Hashtag set approved as proposed (operator, 2026-10-25); stand-ins kept: #Neurodiversität/#Hyperfokus (strengths), #Beziehung/#Beziehungen (partners)"
  - "#ADHSPapa, #ADHSMänner, #ADHSStärken and #adhsdeutschland NOT added"
  - "Crisis-line set approved; 110 (DE police) and CH 144 accepted as standard emergency numbers without a dedicated official-page check"
metrics:
  duration: "~1 session + checkpoint"
  completed: 2026-10-25
  tasks: 2
  tests: "308 passed, 2 failed (pre-existing test_discover failures, deferred-items.md)"
---

# Phase 1 Plan 14: Hashtag and crisis-line sets Summary

German launch sets for the validation run: a harvest-backed hashtag scheme (1 broad + 1-2 niche + 1 pillar tag from 24 DE accounts / 683 posts, each tag justified by distinct-account and mid-tier-view stats) and 12 AT/DE/CH crisis lines re-verified against official pages, both approved by the operator on 2026-10-25.

## Tasks

| Task | Name | Commits |
| ---- | ---- | ------- |
| 1 | Hashtag harvest + sets + crisis lines (TDD) | c02d0c8 (RED), d722494 (GREEN) |
| 2 | Operator confirmation (checkpoint) | bb0f430 |

## What was built

- `ndc scan hashtags` harvests `#[\wäöüÄÖÜß]+` from the descriptions of the selected chosen-language accounts. Case variants merge case-insensitively. Each tag gets distinct accounts, post count and the mid-tier median views. Tags that fail the checker are excluded with the rule id, and #ActuallyAutistic is excluded as `community_self_id`. Output: `scan/hashtag_harvest.yaml`.
- `config/hashtags.yaml`: broad #ADHS / #Autismus; five niche tags; per-pillar lists for all four pillars; first-sentence keywords per pillar; an `excluded` block (medication names, #diagnose, #selbsttest, #therapie, #ActuallyAutistic, and others); a `not_chosen` block with reasons; and a `gaps` block for strengths and men/dads, where no fitting tag reached 2 accounts.
- `config/crisis_lines.yaml`: AT 142 / 147 / 116 123 (16-24 h only) / Männerinfo 0800 400 777 / 144; DE 0800 111 0 111 / 116 111 / Elterntelefon 0800 111 0 550 / 112; CH 143 / 147 / 144. Each entry carries a source_url and verified_at. The file also holds the short pinned-comment form.

## Operator decisions (Task 2)

- Hashtags were approved as proposed and confirmed in the app; `verified_in_app` and `approved_at` are set to 2026-10-25.
- The gap stand-ins stay. #ADHSPapa, #ADHSMänner and #ADHSStärken were not added, and neither was #adhsdeutschland. These decisions are recorded in the file.
- The crisis lines were approved (`approved_at` 2026-10-25). 110 and CH 144 are accepted as standard emergency numbers, and that is recorded in each entry's note.

## Deviations from Plan

**1. [Rule 2 - Safety] Any non-ok checker status excludes a tag, not only `blocked`**
- **Found during:** Task 1
- **Issue:** The plan's behavior only requires chosen tags to be "not blocked". Hashtags have no override flow, though, so a `warn` tag (#diagnose, #therapie, #ads, #autist, #asperger) would reach captions with no human override decision.
- **Fix:** The harvest excludes on any status other than `ok`, evaluated as the worst status over the tag, its bare word and its camel-case split. Every chosen tag has status `ok`.
- **Files:** src/ndc/scan/hashtags.py, config/hashtags.yaml
- **Commit:** d722494

## Deferred Issues

- `tests/scan/test_discover.py`: 2 failures that predate this plan, already logged in deferred-items.md. They are outside this plan's scope.

## Known Stubs

None. The pillar gaps are curated decisions the operator approved, not stubs.

## Threat Flags

None. No new network endpoints or trust-boundary surface. T-14-01, T-14-02 and T-14-03 are mitigated by the checker test, the official-source verification and the operator's in-app check.

## Self-Check: PASSED

- FOUND: config/hashtags.yaml, config/crisis_lines.yaml, scan/hashtag_harvest.yaml, src/ndc/launch_sets.py, src/ndc/scan/hashtags.py
- FOUND commits: c02d0c8, d722494, bb0f430
