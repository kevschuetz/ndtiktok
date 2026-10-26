---
phase: 02-grounded-script-pipeline
plan: 10
subsystem: pipeline
tags: [live-run, runbook, docs, costs]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-01..02-09, 02-11 (store, retrieval, draft, editor, verify, gate, edit flow, phone UI, id check)"
provides:
  - "02-LIVE-RUN.md: evidence for ROADMAP Phase 2 success criteria 1–5 on topic 2 (adult ADHD task initiation)"
  - "docs/script-pipeline.md operator runbook (commands, verdict table, phone review, edit flow, costs, Fehlerbehebung, AWMF import)"
  - "README.md command/service overview; CLAUDE.md 'Script pipeline (Phase 2)' section outside GSD markers; .env.example NCBI_EMAIL/NCBI_API_KEY"
  - "config/llm.yaml Sonnet 5.5 prices → verify cost_usd logged"
affects: [03]
key-decisions:
  - "Verifier rubric NOT tuned: 2 of 8 cited sentences arguably over-flagged (25 % < 30 % threshold); hidden_claim forcing a *supports* model verdict to unsupported noted as a follow-up, not changed"
  - "AWMF snapshot not in this run (operator PDF still pending, 02-06 Task 2); criterion 1 import path remains test-covered only"
  - "Operator keeps v11 despite judging it 'a little clumsy, technical, detailed' — craft follow-up for prompts, not a re-run"
requirements-completed: [SRC-01, SRC-02, SRC-03, SRC-04, SCR-01, SCR-02, SCR-03, SCR-04, SCR-06]
duration: 50min
completed: 2026-10-26
---

# Phase 2 Plan 10: Live end-to-end run Summary

**A fresh whitelisted topic went from PubMed search to an operator-approved, fully cited German script in one sitting: 4 verified sources, 5 logged LLM calls (0.46 USD), 3 blockers caught by the verifier and fixed through the edit flow, phone approval in 2 minutes, source list rendered from DB rows only.**

## Live result (topic 2, corpus 3)
| Step | Result |
|---|---|
| search ×2 | run 7 (26, child-heavy) → run 8 with `--query adult*` (28 candidates, 7 SR/MA in top 11) |
| pick 9 10 11 6 | Boonstra 2005, Lopez 2018 (Cochrane), Cortese 2012, Kim 2025 (+ OA full text 127 sentences); all `id_check` ok |
| draft --punch | v8 draft → v9 punched: 23 sentences, gate ✗ 3 blockers (2 hidden claims, 1 **uncited invented tip**), 1 partial |
| import #1 | v10: cited Cochrane "what helps" line, explicit caution, tip removed; ✗ terminology blocker „Symptome", 209 words |
| import #2 | v11 `4299e91a…`: 190 words, 0 blockers, 1 ack (S17 partial) |
| phone review | **approved, 2 min**, channel web, ack S17; operator: "a little clumsy/technical/detailed, keep it for now" |
| sources | caption (4 DOIs) + comment (4 PMIDs, ≤150 chars) rendered; `NotApproved` before approval |
| negative case | scratch DB, fake DOI → `check-ids` unresolvable → `script draft` refused before the LLM (llm_run count unchanged) |

Costs: draft 0.225 (87 % thinking) · editor 0.125 · verify 0.067 · 2 import re-verifies 0.047 → **0.464 USD**.

## Deviations from Plan
1. **[Rule 1] Query override** — the topic's domain terms returned children/concussion/pregnancy papers; `--query` with `adult*[tiab]` fixed it. Facet tagging falls back to `custom` for overrides, which silently bypasses the corpus-lock "help" warning (follow-up).
2. **No AWMF snapshot** in the corpus: PDF not yet uploaded (02-06 Task 2, operator action).
3. The verifier rubric was not tuned (threshold not met); instead two edit cycles fixed the script. Drafting again on the same corpus was unnecessary.
4. Docs (Task 3) were written before the operator's approval arrived, since they did not depend on it.

## Follow-ups (not blocking Phase 2)
- Draft/editor still produced an uncited tip despite the prompt ban → sharpen "kein Tipp ohne Marker" in `draft_de.md` / `editor_de.md`.
- Operator finds the output too technical/detailed → craft iteration (fewer numbers and test names, more everyday language) in a Phase-3 prompt pass.
- `hidden_claim` rule overrides a *supports* model verdict (v9 S16); consider requiring `model_verdict != supports` before forcing.
- `custom` facet candidates should count toward / be exempted explicitly from the `required_facets` warning.
- Consider `draft.effort: medium` (draft cost is mostly thinking).
