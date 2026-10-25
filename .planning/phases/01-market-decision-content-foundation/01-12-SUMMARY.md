---
phase: 01-market-decision-content-foundation
plan: 12
subsystem: competitor-scan
tags: [mkt-01, judging, in-session, en, evidence-guard]
requires: [01-08]
provides:
  - "llm_session judgments for all 17 accounts of batch en-2 (scan_runs 32, 33)"
  - "docs/judging/en-2.md batch report (guard downgrades, operator queue, level distribution, S_EN candidates)"
affects: [01-13, 01-15]
tech-stack:
  added: []
  patterns:
    - "Judgments generated from a per-account spec by a scratch script that asserts every evidence string is a whitespace-normalised substring of the bundle text before writing (en-1 pattern)"
key-files:
  created:
    - docs/judging/en-2.md
    - /home/nd-content-volumes/data/judging/en-2/judgments.json (data volume, not in git)
  modified: []
decisions:
  - "Caption repost/clip credits ('Credit: <speaker> | <talk>', 'Credit @ADHD Chatter Podcast') scored L2 by the letter of the rubric (named, findable source) but with low source_citing confidence, so the operator rules on them; this makes theautismspectrum and hypeneo1 trip the S_EN rule"
  - "No-frame accounts with ok downloads and empty transcripts (adhdautism4, myadhdventure, adhdminds111) treated as photo carousels: format text_on_screen, face unknown, low confidence (precedent); applied in a second import run"
  - "audhd30 has no video row: judged from text only, face unknown, format mixed, all low"
  - "Off-niche lix.psl (looksmax/gym edits) judged normally at 0 and recommended for exclusion; brand accounts propeladhd and unique_adhd flagged"
metrics:
  duration: "~30 min"
  completed: 2026-10-25
  tasks: 2
---

# Phase 1 Plan 12: In-session judging of batch en-2 Summary

All 17 English TikTok accounts in batch en-2 were judged in-session against rubric v1 with no API call and imported through the evidence guard with provenance `llm_session`. The guard checked 255 citation entries and downgraded none; 10 accounts are queued for the operator. Two faceless, male-pitched accounts reach score 2 (text 2) and are queued as **S_EN candidates**, but both rest only on caption repost credits scored L2 with low confidence: **theautismspectrum** (TEDx clip reposts; the male pitch is a reposted speaker) and **hypeneo1** (voiceover reposts crediting "@ADHD Chatter Podcast"). If the operator rules that repost credits are not source citing, en-2 contributes no S_EN candidate.

## Task 1: judgments (data volume)

- `/data/judging/en-2/judgments.json`, wrapper form, 17 judgments; `load_file` validated it in the container and the count matches the manifest.
- 25 citations at level >= 1: 23 caption L2 (repost credits), 1 caption L1 ("Research shows ..."), 1 speech L1 ("According to psychology"); plus one on-screen L2 (tim.adhd, "FDA approved", single video, not score-deciding).
- No pinned comments exist in this batch's bundles.
- `grep -rn anthropic src`: no match. No git commit (artifact on the data volume by design).

## Task 2: import and report (commit 4cd23fe)

- Run 1 scan_run 32 and run 2 scan_run 33: 17 imported, 0 downgraded, 10 queued. Run 2 only switched the three no-frame accounts to `text_on_screen`.
- Read-only DB check: 0 batch accounts missing an `llm_session` `source_text_level`.
- `docs/judging/en-2.md` has the import summary, "Guard downgrades" (none), "Queued for operator" with reasons, S_EN candidates, the level distribution and a per-account table.

| Account | Score (t/v) | Face | Voice (pitch) | Flag |
|---|---|---|---|---|
| raising_happy_homes | 0 | face | female | clinician-adjacent |
| adhd.partner.support | 0 | faceless | male | queued (format low) |
| adhdvision | 0 | face | male | queued |
| raisingkevin_ | 0 | face | female | |
| adhdautism4 | 0 | unknown | female | carousel, queued |
| theautismspectrum | 2 (2/0) | faceless | male | S_EN queue, repost credits |
| myadhdventure | 0 | unknown | unknown | carousel, queued |
| tim.adhd | 0 | face | male | partly off-niche |
| propeladhd | 0 | face | female | brand, queued |
| messagetodaniel | 0 | faceless | unknown | queued |
| diplomaduck | 0 | faceless | male | format match, no sources |
| audhd30 | 0 (0/-) | unknown | - | no video row, queued |
| neuroduck0 | 0 | faceless | male | format match, no sources |
| adhdminds111 | 0 | unknown | male | carousel, queued |
| unique_adhd | 0 | face | female | brand |
| hypeneo1 | 2 (2/0) | faceless | male | S_EN queue, repost credits |
| lix.psl | 0 | faceless | male | off-niche, exclude |

## Deviations from Plan

- **Verify snippet expects a bare list.** As in de-1/de-2/en-1, the rubric wrapper fails it; validation went through `load_file` with the count asserted against the manifest.
- **Second import run.** The carousel precedent was applied to three no-frame accounts after the first import; both runs are recorded in the report.
- **No vocabulary value for apps/coaching.** Apps mapped to `shop`/`course` with low or medium confidence, noted in `notes`.

## Known Stubs

None.

## Threat Flags

None. No code or network surface added. Bundle content treated as data (T-12-01); guard ran, 0 downgrades (T-12-02); no API path (T-12-03).

## Self-Check: PASSED

- docs/judging/en-2.md: FOUND
- /home/nd-content-volumes/data/judging/en-2/judgments.json: FOUND
- commit 4cd23fe: FOUND
