---
phase: 02-grounded-script-pipeline
reviewed: 2026-10-26T19:40:00Z
reviewer: inline (operator asked for no subagents)
depth: standard
files_reviewed: 9
critical: 0
warnings: 2
info: 4
---

# Phase 2 Code Review

## Summary
Read in full: `src/ndc/llm.py`, `script/draft.py`, `script/verify.py`, `script/edit.py`, `script/editor.py`, `review/gate.py`, `review/store.py`, `review/web.py`, `sources/idcheck.py` (≈2 000 lines, the grounding/approval/security core). Greps over the rest: no model-ID literals in `src/`, immutability triggers on all snapshot/sentence/version/citation tables, no file I/O in the web modules, draft≠verify≠editor model enforced in `load_llm_config`. Full suite 505 passed, ruff check + format clean.

The core invariants hold in code, not just in prompts: `cited_text` must equal the stored sentences or the draft is discarded (`draft.py:150`); uncited non-framing and hidden claims are forced `unsupported` (`verify.py:118`); approvals re-run the gate inside `BEGIN IMMEDIATE` and key on the sha (`store.py:75-91`); ID checks fail closed before any LLM spend (`idcheck.py:163`); the web server has four regex routes, a Host allow-list, HMAC nonces and no path-derived I/O.

## Critical Issues
None.

## Warnings

### WR-01: `hidden_claim` forces `unsupported` even when the model judged the sentence supported
- `src/ndc/script/verify.py:120`
- Live example: topic-2 v9 sentence 16 („Aber: mit Vorsicht zu lesen." ⟦11:64⟧) — `model_verdict=supports`, final `unsupported`, blocker. The sentence quoted the source's own caution.
- Impact: extra edit cycles (≈0.03 USD + operator time) for sentences that are actually grounded; the rule is deliberately conservative (D-15), so this is a tuning question, not a bug.
- Suggestion: force only when `model_verdict != "supports"` **or** the sentence has no citations; keep the forced path for uncited framing that smuggles a claim.

### WR-02: `--query` overrides tag candidates `custom`, bypassing the required-facet warning
- `src/ndc/sources/search.py:116-117, 205-215`
- Live example: topic 2 corpus lock gave no „keine help-Quelle" warning although facets were unknown.
- Impact: the one guard that stops a script without a cited „was hilft" payoff is silent on every overridden search.
- Suggestion: treat `custom` as "unknown" and warn „Facetten unbekannt (--query)", or let `source pick` accept `--facet help`.

## Info

### IN-01: request artifact without `llm_run` row when the API call raises
- `src/ndc/llm.py:174-182` — the request JSON is persisted before `messages.create`; a network/4xx exception leaves an orphan artifact and no ledger row. Acceptable (artifacts are content-addressed), but `ndc doctor` could count orphans.

### IN-02: rejected POST bodies are not drained
- `src/ndc/review/web.py:138` — wrong content type or body > 8 KB returns 400 without reading `rfile`. Harmless with HTTP/1.0 close semantics; would matter if keep-alive were enabled.

### IN-03: `check_source` writes one row per identifier without a transaction
- `src/ndc/sources/idcheck.py:131-140` — a crash between the PMID and DOI inserts leaves a half-recorded check; `latest_status` takes the worst per identifier so it fails safe.

### IN-04: stale tests after config commits
- `tests/sources/test_search.py` fixture matched the old help clause (`[tiab]` vs `[ti]`, commit 042ef27) and `tests/test_llm.py` relied on Sonnet having no price. Both fixed this session; lesson: run the suite after config-only commits too.

## Follow-ups filed
WR-01, WR-02 and the "uncited tip survived the prompt ban" observation are listed in `02-10-SUMMARY.md` → Follow-ups for a Phase-3 prompt/rule pass.
