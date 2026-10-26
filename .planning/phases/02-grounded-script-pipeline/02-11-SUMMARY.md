---
phase: 02-grounded-script-pipeline
plan: 11
subsystem: script
tags: [prompts, editor, retrieval, tiktok]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-07 id check, 02-08 export/import_edit (selective re-verify), 02-09 phone review UI"
provides:
  - "config/prompts/engagement_playbook.md (evidence-based hook/retention rules), draft_de.md v2, editor_de.md, hook_examples_de.md"
  - "script/editor.py punch(db, version_id) -> new version; ndc script punch <sha>; ndc script draft <topic> --punch"
  - "Facet-based literature search (phenomenon / mechanism / help) in retrieval.yaml + sources/search.py; corpus lock warns when no 'help' source"
affects: [02-10, 03]
key-decisions:
  - "Editor output may only reuse citation markers already present in its input; it enters as a new version through import_edit and is re-verified (D-21)"
  - "In-script disclaimer dropped; positioning lives in bio + caption only (D-22)"
  - "A topic corpus needs a 'what helps' source, otherwise the save-worthy payoff has no citation; drug-trial terms excluded from the help facet"
  - "Uncited relatable framing stays in 'du' form without a population claim ('Vielleicht kennst du das.' instead of 'Manche Menschen mit ADHS kennen …')"
requirements-completed: [SCR-01]
duration: 4h (across two sessions, incl. operator refinement)
completed: 2026-10-26
---

# Phase 2 Plan 11: Script craft v2 Summary

**Scripts now open with a 2-second hook and carry tension → payoff, while every claim still traces to a stored sentence: the editor pass can only move citations it was given, and its output is re-verified like any edit.**

## What was built
- **Engagement playbook** (`config/prompts/engagement_playbook.md`): hook tactics, open loop, story arc, save/share payoff, drawn from peer-reviewed engagement research and our own 113 ranked competitor transcripts. Hook examples are abstracted patterns, never competitor lines.
- **Draft prompt v2** (`config/prompts/draft_de.md`): four allowed hook tactics, first sentence ≤ 2 s, short spoken sentences, hedges where the source hedges, no positioning line. Style guide §1/§3 updated.
- **Editor pass** (`src/ndc/script/editor.py`, stage `editor`, claude-opus-5-5): exports the marker format, calls the LLM, rejects any marker not in the input and any Markdown, imports via `import_edit` (origin `edit`), then verifies. `ndc script punch <sha>` and `ndc script draft <topic> --punch`. Tests in `tests/script/test_editor.py`.
- **Facet search** (commits 1487171, 042ef27): each topic is searched per facet (phenomenon / mechanism / help); candidates carry facets; `ndc corpus lock` warns without a 'help' source. Title-level intervention terms were needed to find the real psychosocial / mindfulness / CBT reviews.

## Live result (topic 3, "Starke Gefühle bei ADHS")
| Script | Corpus | Versions | Outcome |
|---|---|---|---|
| 1 (dry, prompt v1) | 1 (2 sources) | v1 draft → v2 edit | approved by operator on the phone (02-09) |
| 2 (prompt v2 + punch) | 1 | v1 draft → v2 editor | 2 blockers; no 'help' source → payoff unbacked |
| 3 (prompt v2 + punch) | 2 (5 sources, 3 'what helps' reviews) | v1 draft → v2 editor → **v3 operator edit** | **v3 fd07bd2c…: 0 blockers, 1 open ack** |

Operator refinement of script 3 (Task 3, this session): sentence 3 "Manche Menschen mit ADHS kennen genau dieses Gefühl." → "Vielleicht kennst du das." (uncited population claim → framing); sentence 6 "Symptome" → "Schwierigkeiten" (terminology warning); sentence 16 dropped "also" so the hypothesis stays a hypothesis (verifier now rates it GESTÜTZT). Import re-verified 3 sentences, reused 16 verdicts. Remaining open item: sentence 15 (Achtsamkeitstraining, TEILWEISE; the verifier notes the script is *more* cautious than the source) awaits the operator's ack and approval on the phone (http://10.0.0.213:8090).

Costs this plan (from `llm_run`): draft ≈ $0.13–0.22, editor ≈ $0.10 per pass; verify cost NULL because `config/llm.yaml` has no Sonnet 5.5 price yet.

## Verification
- `grep "kein Therapeut" config/prompts/draft_de.md` → no match.
- Editor tests: new marker refused, Markdown refused, output becomes latest version and is verified. Full suite 505 passed, ruff clean (end of previous session).
- Checkpoint Task 3: operator chose the proposed fixes ("Apply all four proposed fixes"); the TikTok-ready verdict is given by approving v3 on the phone.

## Deviations from Plan
1. **[Rule 2] Facet search added** (not in the plan's task list): the single query found only problem-describing papers, so the punched script had no citation for its payoff. Retrieval was split per facet and the corpus lock now warns.
2. **[Rule 1] A third draft on a new corpus** was needed (script 3, corpus 2) before the editor output could be fixed by small edits rather than redrafted.
3. Operator refinements were applied via export → edit → import instead of a redraft, so the plan's "draft --punch" result was kept and only three sentences changed.

## Open for 02-10
- Fill Sonnet 5.5 prices in `config/llm.yaml` (verify cost_usd is NULL).
- Consider `draft.effort: medium` (draft cost is mostly thinking tokens).
