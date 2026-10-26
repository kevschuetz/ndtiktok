---
phase: 02-grounded-script-pipeline
plan: 03
subsystem: llm
tags: [verifier, structured-output, sonnet-5-5]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-02 llm.call(parse_model), script tables"
provides:
  - "ndc script verify <id|sha>; script/verify.py (VerifyReport, force, reuse_key, verify(only_ordinals), verdict_counts)"
  - "009_review.sql: claim_verdict (+model_verdict audit column), review, claim_ack — all append-only"
affects: [02-04, 02-08]
key-files:
  created: [config/prompts/verify_de.md, src/ndc/schema/009_review.sql, src/ndc/script/verify.py]
key-decisions:
  - "claim_verdict stores both the forced verdict and the model's raw verdict (model_verdict) for audit"
  - "Verifier payload: sentence + cited stored sentences + ±1 neighbour context; no draft prompt"
requirements-completed: [SCR-02, SCR-06]
duration: 20min
completed: 2026-10-26
---

# Phase 2 Plan 03: Adversarial verifier Summary

**Sonnet 5.5 checks every sentence against its cited sources in one structured call; code forces uncited facts and claim-smuggling framing to "unsupported".**

## Live result (script version 1, 10 sentences)
supports 4 · partial 1 · not_applicable 3 · unsupported 2 (both `hidden_claim`: "these two works don't answer what helps" — the review does have a treatments section; "ehrlich den Stand der Forschung" — two papers aren't the state of research). Sentence 2 partial: a youth meta-analysis generalized to "Menschen mit ADHS". Omitted detail ("Negativität") correctly stayed `supports`.
llm_run: claude-sonnet-5-5, 4567 in / 2973 out (1424 thinking), cost NULL (Sonnet 5.5 price not configured — WARNING logged as designed).

## Deviations from Plan
1. **[Rule 2] `model_verdict` column** added to claim_verdict for auditability of forcing.
2. Fake client instead of a recorded cassette (consistent with 02-01/02).

## Issues
- Operator to fill `prices.claude-sonnet-5-5` in config/llm.yaml.

## Next
Ready for 02-04 (gate + review + source list).
