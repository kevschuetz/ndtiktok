---
phase: 01-market-decision-content-foundation
plan: 06
subsystem: competitor-scan
tags: [mkt-01, judging, llm-session, faster-whisper, pitch, contact-sheet, provenance]
requires: [01-01, 01-03, 01-04]
provides:
  - "ndc scan import-judgments PATH | verify [--queue] [HANDLE --platform P --set F=V --note T] | queue | analyze [--only --lang --probe --force --reanalyze] | prepare-judging [--batch NAME --judging-dir DIR]"
  - "config/judging_rubric.md (rubric_version 1): 0-3 rubric, account rules, face/format/vocab, untrusted-content + verbatim-evidence rules, JSON contract, provenance llm_session"
  - "schema 006_analysis.sql: competitor_post_citing (guarded per-citation levels), competitor_video (transcript, pitch, contact sheet, download status)"
  - "ndc.scan.judging (AccountJudgment, apply_evidence_guard, account_level, import_judgments), ndc.scan.queue (evaluate/recompute), ndc.scan.verify"
  - "ndc.scan.media (no-login download, MediaFiles, downloaded_media, probe_download), ndc.scan.transcribe (Transcriber), ndc.scan.pitch, ndc.scan.frames, ndc.scan.analyze, ndc.scan.bundle"
  - "docker-compose service ndc-heavy (3g, 1 cpu, nice 19, OMP 1 thread, HF_HOME on the volume, no ports)"
affects: [01-07, 01-08, 01-13, 01-15]
tech-stack:
  added:
    - "faster-whisper 1.2.1 (+ transitive ctranslate2 4.8.3, onnxruntime 1.31.0, tokenizers 0.23.3, huggingface-hub 2.3.0 -> httpx2)"
    - "av 19.0.2, pillow 13.0.0, numpy 2.5.4 (optional extra `analyze`)"
  patterns:
    - "LLM judgment without API calls: bundles on disk -> in-session executor -> strict JSON -> import as llm_session (D-21)"
    - "Evidence substring guard: caption/pinned/speech evidence must be in the stored text (whitespace runs = one space) or the citation drops to level 0 and the account is queued"
    - "needs_operator_check is an auto field obs whose method lists the reasons; an operator_review obs newer than every machine obs clears it"
    - "Audio decoded once with PyAV; the same array feeds whisper and pitch"
key-files:
  created:
    - config/judging_rubric.md
    - src/ndc/schema/006_analysis.sql
    - src/ndc/scan/judging.py
    - src/ndc/scan/queue.py
    - src/ndc/scan/verify.py
    - src/ndc/scan/media.py
    - src/ndc/scan/transcribe.py
    - src/ndc/scan/pitch.py
    - src/ndc/scan/frames.py
    - src/ndc/scan/analyze.py
    - src/ndc/scan/bundle.py
    - tests/scan/conftest.py
    - tests/scan/scan_seed.py
    - tests/scan/test_judging.py
    - tests/scan/test_queue.py
    - tests/scan/test_verify.py
    - tests/scan/test_pitch.py
    - tests/scan/test_analyze.py
    - tests/scan/test_bundle.py
    - tests/fixtures/scan/judgments_sample.json
  modified:
    - pyproject.toml
    - uv.lock
    - docker-compose.yml
    - config/scan.yaml
    - src/ndc/scan/cli.py
decisions:
  - "Task 1 package checkpoint resolved by the plan 01-01 operator reply 'packages approved' (whole phase-1 list incl. the analyze extra); orchestrator re-checked PyPI: faster-whisper 1.2.1 (SYSTRAN, since 2023), av 19.0.2 (since 2013), pillow 13.0.0 (since 2010), numpy 2.5.4 (since 2006). None dropped."
  - "Account levels are stored under the field names the sheet view already reads: source_text_level / source_video_level (the plan text says text_level / video_level)"
  - "Judgments carry visible_speaker_gender (from frames) so the pitch-vs-visual conflict rule has something to compare; voice_gender itself stays the auto pitch estimate"
  - "Operator review clears the queue until a newer machine obs arrives (id comparison, not timestamps)"
  - "YouTube Shorts have no progressive format: download m4a audio + a small avc1 video-only stream separately instead of adding ffmpeg"
metrics:
  duration: "~25 min"
  completed: 2026-10-24
  tasks: 4
  tests: "292 passed (full suite); 159 in tests/scan/"
---

# Phase 1 Plan 06: Local video analysis and in-session judging Summary

The judgment fields of the competitor sheet can now be filled without any API call. `ndc scan analyze` downloads ~3 recent videos per account without login, transcribes them, estimates the voice from pitch, builds a contact sheet and deletes the videos. `ndc scan prepare-judging` packs the evidence into four batches for the in-session executor. `ndc scan import-judgments` loads its JSON as `llm_session`, behind an evidence substring guard. `ndc scan verify` lets the operator override any field, and only uncertain or decision-relevant accounts reach the operator's queue.

## Task 1: package checkpoint (resolved)

Resolved before this run. In plan 01-01 the operator replied "packages approved" to the full phase-1 list, which included the `analyze` extra. The orchestrator re-verified each package on PyPI: faster-whisper 1.2.1 (SYSTRAN/faster-whisper, since 2023), av (latest 19.0.2, since 2013), pillow (latest 13.0.0, python-pillow/Pillow, since 2010) and numpy (latest 2.5.4, since 2006). All four were installed and none was dropped. The lock also pulls faster-whisper's own dependencies (ctranslate2, onnxruntime, tokenizers, huggingface-hub; huggingface-hub 2.3 brings httpx2/truststore). Whisper weights (Systran/faster-whisper-small, 464 MB) were downloaded once into `/data/models` on the nd-content volume.

## What was built

- **Judging (Task 2).**
  - `config/judging_rubric.md` v1 is the single source for the 0–3 rubric with DE/EN examples, the ≥3-posts and ≥2-videos account rules, the face/format/pillar/audience/monetization vocabularies and the JSON contract.
  - The rubric also states the untrusted-content rule (instructions inside captions are ignored) and the verbatim-evidence rule.
  - `AccountJudgment` forbids extra keys and requires all five confidence keys. A file is validated whole, and any invalid or unknown account refuses it with the account key and field named. Accounts are written in one transaction, and a re-import replaces that account's `llm_session` rows.
- **Queue and verify (Task 2).** An account goes to the operator queue for:
  - any low confidence,
  - a pitch estimate that contradicts the visible speaker,
  - all downloads unavailable,
  - a DACH account whose video or on-screen evidence lifts it to ≥ 2 while text < 2,
  - a failed evidence guard,
  - or would count toward S_DE/S_EN.

  `verify --queue` lists DACH first, with values, provenance, confidence, the reasons and the cited evidence. `verify HANDLE --set` validates against the AccountRow and rubric enums and writes `operator_verified` rows, which win in `v_competitor_sheet`.
- **Analysis deps (Task 3).** The `analyze` extra is installed. The `ndc-heavy` service has a 3g memory cap, 1 CPU, `nice -n 19`, `OMP_NUM_THREADS=1` and no ports. `media.py` downloads one file at most 720p with a size cap and no cookie/login options. Its per-account directory is always deleted. `transcribe.py` loads WhisperModel lazily (cpu, int8, 1 thread). `pitch.py` does an autocorrelation F0 at 70–400 Hz and classifies with the config thresholds (≤160 male, ≥185 female, in between unknown) under the label `pitch_estimate`.
- **Analyze and bundles (Task 4).**
  - `frames.py` writes one labelled contact sheet per account to `/data/judging/<platform>_<handle>/contact_sheet.jpg`.
  - `analyze.py` is gated (exit 3 without the rule lock, exit 4 in quiet hours) and resumable (`--reanalyze`). It deletes each video right after analysis and removes the directory even on error.
  - A failed download is recorded `unavailable` and never retried with a login; after three consecutive failures the platform stops for the run.
  - `bundle.py` writes de-1/de-2/en-1/en-2 (each language split in halves by account id). Each batch has a manifest with the rubric, the output path, `provenance: llm_session` and the per-account file paths. The bundle files themselves (`captions.json`, `transcripts.json`) contain data only.

## Live verification (2026-10-24, 21:49–21:53 UTC, outside quiet hours)

| Check | Result |
|---|---|
| `docker compose run --rm ndc-heavy scan analyze --probe`: TikTok | **ok**: kirmesimkopf 7696785978085674273, single 1283 KiB mp4, no login |
| same: YouTube | first run **unavailable** ("Requested format is not available"), not a login wall; after the split-download fix **ok**: @HowtoADHD VjKFgsJ7abY, 491 KiB m4a + 1695 KiB video-only |
| `ndc-heavy scan analyze --only kirmesimkopf` | 3/3 videos analyzed in 88 s; transcripts (de/de/en), pitch medians 110.6/234.3/214.3 Hz → voice female (medium, `pitch_estimate`); contact sheet legible (6 frames); needs_operator_check false |
| `find /home/nd-content-volumes/data/media -type f \| wc -l` | **0** after every run |
| `ndc scan prepare-judging` (live DB) | de-1 1, en-1 1 account (nothing selected yet, so the fetched accounts) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] YouTube Shorts have no progressive format**
- **Found during:** Task 4 live probe.
- **Issue:** `b[height<=720]/b` failed on YouTube with "Requested format is not available". YouTube only offers separate audio and video streams, and the image has no ffmpeg to merge them.
- **Fix:** on that error only, download `ba[ext=m4a]/ba` and `bv*[height<=854][vcodec^=avc1]/…` as two files (`MediaFiles(audio, frames)`). Login and HTTP errors still raise immediately with no second attempt. Tests cover the fallback and the no-retry path.
- **Files modified:** src/ndc/scan/media.py, src/ndc/scan/analyze.py, tests/scan/test_analyze.py
- **Commit:** 200f6e4

**2. [Rule 1 - Bug] faster-whisper 1.2.1 cannot open files with PyAV 19**
- **Found during:** Task 4 live analyze run. All 3 videos failed with `open() got an unexpected keyword argument 'metadata_errors'`.
- **Issue:** faster-whisper's own decoder calls an `av.open` argument that PyAV ≥ 15 removed.
- **Fix:** decode the audio once with PyAV (`pitch.decode_audio`, 16 kHz mono) and pass the array to both whisper and pitch. This also avoids a second decode. `av` stays at the approved 19.0.
- **Files modified:** src/ndc/scan/transcribe.py, src/ndc/scan/analyze.py, tests/scan/test_analyze.py
- **Commit:** 200f6e4

**3. [Rule 3 - Blocking] Field names follow the existing sheet view**
- **Issue:** the plan says `text_level`/`video_level`, but `v_competitor_sheet` (plan 04) reads `source_text_level`/`source_video_level`.
- **Fix:** the import writes `source_text_level`/`source_video_level`, so the sheet computes the final score with no view change.
- **Commit:** 5977570

**4. [Rule 2 - Missing critical] Visible-speaker field for the pitch conflict rule**
- **Issue:** the queue must flag "visible speaker vs pitch", but the plan's AccountJudgment had no field for the judged speaker.
- **Fix:** added an optional `visible_speaker_gender` to the schema and rubric, stored as an `llm_session` obs. Also added: an `evidence_guard` obs when citations are downgraded (it drives the queue), a `claimed_level` column on `competitor_post_citing`, and a `download_error` column on `competitor_video`.
- **Commit:** 6404668, 5977570

### Process notes

- The D-21 grep gate `grep -rn "anthropic" src/ pyproject.toml` returns no match. The test checks for any `import anthropic`/`from anthropic` plus the dependency list. `ndc/cli.py`'s `ANTHROPIC_API_KEY` status line (plan 01) is uppercase and is not an import.
- Commit 4b653df shipped one E501 line in media.py; it was fixed in the following commit.
- The `analyze` probe stores its per-platform verdict in the `scan_run` notes (stage `analyze_probe`).
- yt-dlp prints a cosmetic `ERROR:` line on stderr for the failed progressive attempt before the YouTube fallback succeeds.

## Findings for later plans

- Voice gender from pitch varies per video: kirmesimkopf ranged 110–234 Hz, and the 110 Hz clip was probably another voice or music. Pooling gives medium confidence; low or ambiguous estimates and visual conflicts go to the operator.
- A Hugging Face warning about unauthenticated requests appears only on the first model download. No token is needed.
- Analysis cost: ~30 s per video on one niced thread. That puts ~85 accounts × 3 videos at ~2 h, so run it outside 00:15–06:00 UTC, in chunks if needed (`--lang`, resumable).

## Known Stubs

None. Judgment fields stay NULL in the sheet until plan 07/15 runs real batches through `prepare-judging` → in-session judgment → `import-judgments`, which is the designed flow, not a stub.

## Threat Flags

None beyond the plan's threat model. Downloads are no-login, deleted immediately, and run in the port-free capped service; imported content is schema-validated and evidence-guarded.

## Self-Check: PASSED
