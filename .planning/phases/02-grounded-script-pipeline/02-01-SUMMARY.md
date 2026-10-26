---
phase: 02-grounded-script-pipeline
plan: 01
subsystem: database
tags: [sqlite, pubmed, pysbd, sha256]
requires:
  - phase: 01-market-decision-content-foundation
    provides: topic matrix (whitelist), Database migrations, CLI app
provides:
  - "008_ledger.sql: source/source_snapshot/source_sentence, topic_pick, corpus/corpus_source, script/script_version/script_sentence/script_citation (append-only triggers), llm_run extension"
  - "ndc source add|show|list|pick-snapshot|unpick, ndc corpus lock|show"
  - "artifacts.put/path (write-once content-addressed store)"
affects: [02-02, 02-05, 02-06, 02-07]
tech-stack:
  added: [pysbd 0.3.4, anthropic 2.3 (dependency only)]
  patterns: ["offline HTTP tests via httpx.MockTransport + recorded fixture bodies", "append-only ledger tables enforced by RAISE(ABORT) triggers"]
key-files:
  created: [src/ndc/schema/008_ledger.sql, src/ndc/artifacts.py, src/ndc/sources/split.py, src/ndc/sources/pubmed.py, src/ndc/sources/store.py, src/ndc/sources/cli.py]
  modified: [src/ndc/cli.py, pyproject.toml, uv.lock, tests/scan/test_judging.py]
key-decisions:
  - "Script versions live under a separate `script` table so script_version can be fully immutable"
  - "Phase-1 test_no_anthropic_anywhere narrowed to allow anthropic only in src/ndc/llm.py (D-01 supersedes D-21)"
requirements-completed: [SRC-03]
duration: 25min
completed: 2026-10-26
---

# Phase 2 Plan 01: Source store Summary

**PubMed abstracts become sha256-addressed, append-only sentence snapshots, grouped per topic into a locked 2–5-source corpus.**

## Performance
- Started 2026-10-26T06:34Z, completed ~07:00Z; 1 task; 14 files.

## Accomplishments
- Live: topic 3 ("Starke Gefühle bei ADHS…") — snapshot 1 = PMID 36608036 (16 sentences, sha256 cd696a12…), snapshot 2 = PMID 27180913 (10 sentences); re-add returns the same snapshot; corpus 1 sha256 a9074b24272a5ea3d4f10c273ff92e7faf384668c5e2f7ffb86bfa513e28b174.
- 12 ABORT triggers (snapshots, sentences, script tables, corpus_source).
- Full suite 397 passed (the two pre-existing tests/scan/test_discover failures no longer reproduce).
- Live DB backed up to /home/nd-content-volumes/data/ndc.db.bak-pre-phase2-20261026 before the first Phase-2 migration.

## Deviations from Plan
1. **[Rule 3 - Blocking] Offline HTTP fixtures instead of VCR cassettes.** Recorded raw response bodies in tests/fixtures/sources and served them via httpx.MockTransport — deterministic, and no request headers/keys are ever persisted. `tests/cassettes/` not created.
2. **[Rule 1 - Bug] Phase-1 guard test contradicted D-01.** Narrowed as noted above.
3. **[Rule 2] Extra commands** `source list`, `source unpick`, `source pick-snapshot`, `corpus show` (pick-snapshot was planned for plan 06; added here since it's a 5-line wrapper).

**Total deviations:** 3 auto-fixed. **Impact:** none on scope.

## Next
Ready for 02-02 (draft).
