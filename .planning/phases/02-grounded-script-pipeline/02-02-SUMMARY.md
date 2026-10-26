---
phase: 02-grounded-script-pipeline
plan: 02
subsystem: llm
tags: [anthropic, citations, opus-5-5, logging]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-01 ledger tables, locked corpus"
provides:
  - "src/ndc/llm.py: load_llm_config, load_prompt, call(stage, request, prompt_sha, input_shas, subject, client, parse_model) — sole anthropic caller, llm_run + artifacts"
  - "ndc script draft <topic>, ndc script show <id|sha>"
  - "draft.map_citations, run_mechanical_checks, store_version, PRE_DRAFT_HOOKS"
affects: [02-03, 02-07, 02-08]
tech-stack:
  added: [anthropic 2.3.0 (in use)]
  patterns: ["prompt = config/prompts/<x>.md + verbatim append_files, hashed together", "PRE_DRAFT_HOOKS for gates that must run before LLM spend"]
key-files:
  created: [src/ndc/llm.py, src/ndc/script/draft.py, src/ndc/script/cli.py, config/llm.yaml, config/prompts/draft_de.md]
key-decisions:
  - "Draft system prompt = draft_de.md + style_guide.md verbatim (style guide says Phase-2 prompts read it unchanged)"
  - "word_range 140–190 from style_guide §1 (research had 150–190)"
  - "parse_model support added to llm.call now (plan 03 uses it)"
requirements-completed: [SCR-01, SCR-06]
duration: 30min
completed: 2026-10-26
---

# Phase 2 Plan 02: Grounded draft Summary

**A locked corpus becomes a German TikTok script whose cited sentences resolve to stored English source sentences; every call is logged with prompt hash, tokens, cost and replayable artifacts.**

## Live result
- Topic 3, script version 1, sha256 34277f36dab464a403b76b9ba4ee731e9644b305c29f9a1e7fd7e0b143f29e82: 10 sentences, 160 words, checks ok; 6 cited sentences (Soler-Gutiérrez 2023 ×3, Graziano 2016 ×2… ), hook + positioning + "keine erfundenen Tipps" framing uncited.
- llm_run 1: claude-opus-5-5, prompt_sha256 793b995a…, in 141 (+cache write) / out 5167 of which **4538 thinking**, cost $0.135, stop end_turn, request id captured; request/response artifacts exist, no key material.

## Deviations from Plan
1. **[Rule 1] word_range 140–190** (style guide is authoritative over research's 150–190).
2. **[Rule 3] Draft prompt appends style_guide.md verbatim** via `append_files` (style guide header requires it).
3. **[Rule 2] `parse_model` added to llm.call here** instead of plan 03 (same file, avoids churn).
4. **[Rule 3] Offline fake client instead of a recorded cassette** (consistent with 02-01).

## Issues / follow-ups
- Thinking dominates cost at effort `high` (~$0.13/draft vs $0.05 estimate). Try `effort: medium` during the live run (plan 10) if quality holds.
- Sentence [6] "Was im Alltag konkret hilft, beantworten diese beiden Arbeiten nicht direkt." is an uncited meta-claim — exactly what the verifier's hidden-claim check (plan 03) must judge.

## Next
Ready for 02-05 (same wave) / 02-03.
