---
phase: 01-market-decision-content-foundation
plan: 02
subsystem: content-checks
tags: [terminology, safety, simplemma, overrides, style-guide]
requires: [01-01]
provides:
  - "ndc check FILE|--text --lang de|en --level topic|script|claim (exit 0 ok / 1 blocked / 2 needs_override)"
  - "ndc.checks.engine: check(text, lang, level, db=None) -> CheckResult; Finding; record_override(db, text, rule_id, level, reason)"
  - "config/terminology.yaml v1 (two tiers, DE+EN), operator-approved 2026-10-24"
  - "config/safety.yaml v1 (blacklisted subjects, all block, levels topic/script/claim), operator-approved 2026-10-24"
  - "config/style_guide.md: fixed 60–75 s template consumed by Phase 2 prompts"
  - "check_override table (002_checks.sql), bound to text_sha256"
affects: [01-05, phase-2]
tech-stack:
  added: []
  patterns:
    - "Lemma (simplemma) + regex hybrid matcher on NFC/dash/quote-normalized text with offset-preserving quote stripping"
    - "Rule files parsed with yaml.safe_load into pydantic models that forbid unknown keys"
    - "Warn overrides keyed on (text_sha256, rule_id); any edit to the text voids them; block tier never overridable"
key-files:
  created:
    - config/terminology.yaml
    - config/safety.yaml
    - config/style_guide.md
    - src/ndc/checks/text.py
    - src/ndc/checks/rules.py
    - src/ndc/checks/models.py
    - src/ndc/checks/_match.py
    - src/ndc/checks/terminology.py
    - src/ndc/checks/safety.py
    - src/ndc/checks/engine.py
    - src/ndc/schema/002_checks.sql
    - tests/checks/test_terminology.py
    - tests/checks/test_safety.py
    - tests/checks/test_overrides.py
    - tests/test_cli_check.py
    - tests/test_style_guide.py
    - tests/fixtures/sample_script_de.txt
    - tests/fixtures/sample_script_en.txt
    - tests/fixtures/precision_de.txt
    - tests/fixtures/precision_en.txt
  modified:
    - src/ndc/checks/cli.py
decisions:
  - "Operator approved terminology.yaml, safety.yaml and style_guide.md as-is (D-15), no changes requested"
  - "ASCII ' and typographic U+2019 are treated as apostrophes, not quote marks, so \"Asperger's\" / \"don't\" never open a quoted span"
  - "Finding/CheckResult live in models.py and shared lemma/regex matching in _match.py so terminology.py and safety.py stay thin and identical in behaviour"
metrics:
  duration: ~45min (excluding operator review)
  completed: 2026-10-24
---

# Phase 1 Plan 02: Terminology + Safety Checker Summary

`ndc check` runs one `check(text, lang, level)` over a two-tier DE+EN terminology table (block: functioning labels, ABA framing; warn: superpower, leidet an, Asperger outside quotes, person-first autism phrasing, …) and a block-only safety blacklist that behaves identically at topic, script and claim level; warn findings pass only with a reason recorded against the exact NFC text hash. Both rule files and the 60–75 s style guide are operator-approved.

## Tasks

| Task | Name | Commit |
|---|---|---|
| 1 | `ndc check` terminology + safety (TDD) | 2bb7f64 (RED), 1c73e00 (GREEN) |
| 2 | Hash-bound overrides + style guide (TDD) | f3fb115 (RED), 896acc3 (GREEN) |
| 3 | Operator approval checkpoint | 5a04013 (approved_by/approved_at set) |

## Operator approval (Task 3)

Operator reply: **"Approved"**, all three files as-is. `approved_by: operator`, `approved_at: 2026-10-24` set in `config/terminology.yaml` and `config/safety.yaml`.

## Verification

- `bash scripts/test.sh tests/checks/ tests/test_cli_check.py tests/test_style_guide.py` → 102 passed (after approval edit).
- Full suite `bash scripts/test.sh` → 108 passed.
- `docker compose run --rm ndc check tests/fixtures/sample_script_de.txt --lang de --level script` → exit 1; output contains `de.leiden_an`, `de.hochfunktional`, `any.asperger`.
- Task 1/2 acceptance greps (no `tier: warn` in safety.yaml, "Person im Autismus-Spektrum" documented, `check_override` in 002, style guide ≥ 60 lines with "60–75" and flash/Blitz) passed at their commits.

## Deviations from Plan

**1. [Rule 3 - Blocking] Typer callback with `allow_interspersed_args`**
- The `check` sub-app was registered in plan 01 as a Typer group (`ndc check`), so a plain `@app.command("check")` would have produced `ndc check check FILE`. Implemented as `@app.callback(invoke_without_command=True)` with `context_settings={"allow_interspersed_args": True}`, so `ndc check FILE --lang de` and `ndc check --text ... --lang de` both work without touching `cli.py`. Commit 1c73e00.

**2. [Rule 1 - Bug] Apostrophes are not quote marks**
- Treating ASCII `'` and typographic `’` (U+2019) as quote pairs made "Asperger's" / "don't" open an unbalanced quoted span and could hide or mis-place findings. They are excluded from the quote-pair list (documented in `text.py`). Commit 1c73e00.

**3. [Plan ordering] DB wiring landed in Task 2**
- `check(..., db=None)` accepts the DB parameter from Task 1 (contract), but override lookup and the CLI's `Database(db_path())` wiring were implemented in Task 2 together with `002_checks.sql`, since the table only exists from then. Commit 896acc3.

**4. [Rule 3 - Structure] Added `models.py` and `_match.py`**
- Not in `files_modified`: `models.py` holds `Finding`/`CheckResult` (avoids a circular import between engine and the two checkers), `_match.py` holds the shared lemma-window/regex matcher used by both terminology and safety, which is what makes the safety result identical across levels. Commit 1c73e00.

## Threat model

T-02-01..04 mitigated as planned (block override raises + CLI exit 1; reason CHECK ≥ 5 chars bound to text_sha256; safe_load + extra-forbid models; simple patterns, 10k-char input test under 1 s). T-02-05 accepted (paraphrase gap; Phase 2 adds LLM second opinion + operator review).

## Known Stubs

- Style guide references `config/crisis_lines.yaml`, which is created in plan 09 (intentional forward pointer).

## Self-Check: PASSED

All created files exist; commits 2bb7f64, 1c73e00, f3fb115, 896acc3, 5a04013 present in `git log`.
