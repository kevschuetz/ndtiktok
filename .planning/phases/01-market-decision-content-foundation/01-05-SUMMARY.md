---
phase: 01-market-decision-content-foundation
plan: 05
subsystem: topic-matrix
tags: [topics, vocab, safety, review, cli]
requires: [01-01, 01-02]
provides:
  - "config/matrix.yaml v1: pillar (4, D-11), condition (8 with guideline_layer, D-10), domain (18, 3 sensitive), audience (6), angle (8); stable snake_case keys + de/en labels"
  - "ndc.topics: load_matrix, import_seed, add_topic, list_topics, keep, kill, select, stats, safety_check, TopicError"
  - "ndc topic import PATH | list (--pillar --condition --domain --audience --angle --tag --status --format table|csv) | review | keep IDS... | kill ID --reason | select ID | stats"
  - "topics.select(): the CONT-04 topic-level enforcement point (whitelist AND safety_status != blocked, enforced in the UPDATE WHERE clause)"
affects: [01-15, phase-2]
tech-stack:
  added: []
  patterns:
    - "Seed YAML -> yaml.safe_load -> strict pydantic (extra=forbid) -> vocab validation naming file position -> one BEGIN IMMEDIATE transaction with INSERT OR IGNORE"
    - "Every topic entering the DB runs check(title + summary, level='topic'); needs_override is stored as flagged, blocked as blocked"
    - "State transitions are single UPDATEs with the precondition in WHERE; rowcount decides success"
key-files:
  created:
    - config/matrix.yaml
    - tests/test_topics.py
    - tests/fixtures/topic_seed_small.yaml
  modified:
    - src/ndc/topics.py
    - src/ndc/topics_cli.py
    - tests/test_cli_topic.py
decisions:
  - "add_topic with no language yet (pre-decision operator adds) checks both de and en and keeps the worst safety result, so an English 'melatonin' title cannot slip past a German-only check"
  - "Seed `notes` is accepted for reviewer comments but not stored (the topic table has no notes column; no schema change for this)"
  - "keep is all-or-nothing across the given ids; kill is single-id; kept = backlog/selected/in_production/published"
  - "stats 'kept' counts whitelist topics with ok or flagged safety (flagged = warn-tier terminology hit, still selectable); target 7 per pillar"
  - "list output columns: id,pillar,condition,domain,audience,angle,working_title,list_tag,safety_status,source_likely,status (plan 01's header test updated to the new spec)"
metrics:
  duration: ~10min
  completed: 2026-10-24
  tasks: 2
  files: 6
---

# Phase 1 Plan 05: Topic matrix tooling Summary

Browsable topic matrix: `config/matrix.yaml` vocabulary, a vocab-validated and topic-level safety-checked seed import (no LLM), filters on every dimension with the whitelist/blacklist tag always shown, keep/kill review, and a select guard that never lets a blacklisted or safety-blocked topic reach production.

## What was built

- **Vocabulary** (`config/matrix.yaml`, version 1): the four D-11 pillars, the eight D-10 conditions (adhd/autism on `awmf_s3`, the rest on `pubmed_reviews`), the 18 research domains with `sleep`, `energy_burnout` and `late_identification` marked `sensitive` plus a note naming the adjacent blocked subject, six audiences and eight angles. Validated by a strict pydantic model (every condition must have a guideline_layer).
- **Import** (`ndc topic import PATH`): top-level `version`, `language` (de|en), `topics`; unknown keys rejected; an unknown vocab value (e.g. `condition: adhs`) fails with `<file>: topics[3].condition: 'adhs' is not a valid key; valid: ...` and inserts nothing. Re-importing is a no-op (UNIQUE(working_title, language) + INSERT OR IGNORE). Each topic gets `safety_status` and `safety_hits_json` (`rule_id`, `tier`, `matched_text`); `origin='matrix'`.
- **List**: all five dimensions plus `--tag` and `--status`, every value validated against the vocab (exit 2 with the valid keys otherwise) and passed as SQL parameters. `list_tag` and `safety_status` always shown; CSV header per the plan.
- **Review**: `topic review` (k/x/s/q, shows all five dimensions, tag, safety status and hits, prompts for a kill reason), plus non-interactive `keep`, `kill --reason`, `select`.
- **Select guard**: `UPDATE ... WHERE status='backlog' AND list_tag='whitelist' AND safety_status != 'blocked'`; a refusal names the reason (blacklist / blocked with rule ids / wrong status) and leaves the row unchanged. Tested by `test_select_refuses_blacklist_and_blocked`.
- **Stats**: pillar x status table, kept whitelist ok/flagged count per pillar, "below 7" marker.

## Verification

- `bash scripts/test.sh` -> 241 passed (full suite; 30 in the two topic test files).
- ruff check + format clean on touched files.
- `docker compose run --rm ndc topic stats` exits 0 against the live DB (all pillars 0, below 7: the real backlog is not imported yet).
- `grep -rn anthropic src/ndc/topics.py src/ndc/topics_cli.py` -> no match (D-19).
- Fixture safety results confirmed against the real engine: Melatonin title blocked (`any.medication_names`), "Ist mein Kind autistisch? Die Checkliste" blocked (`de.diagnosis_question`), "normale Menschen" flagged (`de.normal_kontrast`), the rest ok.

## Commits

- 87ae51e test(01-05): failing tests for seed import and filtered listing
- 801c7e1 feat(01-05): vocab-validated, safety-checked seed import and filtered topic listing
- b8bfbae test(01-05): failing tests for keep/kill review, selection guard and stats
- 07b5204 feat(01-05): keep/kill review, selection guard and per-pillar topic stats

## Deviations from Plan

None - plan executed as written. Small choices within scope are listed under decisions (dual-language check when language is unset, `notes` not stored). The real 60-80 topic seed was deliberately not created (plan 15, after the language decision).

## TDD Gate Compliance

Both tasks have a `test(...)` RED commit followed by a `feat(...)` GREEN commit. RED was confirmed each time (collection error / 9 failures).

## Known Stubs

None. The live DB topic matrix is empty until plan 15 imports the real seed; CONT-01 stays pending until then.

## Self-Check: PASSED

- FOUND: config/matrix.yaml, src/ndc/topics.py, src/ndc/topics_cli.py, tests/test_topics.py, tests/test_cli_topic.py, tests/fixtures/topic_seed_small.yaml
- FOUND commits: 87ae51e, 801c7e1, b8bfbae, 07b5204
