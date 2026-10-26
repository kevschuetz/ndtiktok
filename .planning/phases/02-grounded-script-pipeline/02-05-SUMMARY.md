---
phase: 02-grounded-script-pipeline
plan: 05
subsystem: retrieval
tags: [pubmed, europepmc, jats, ranking]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-01 store_snapshot/pick, pubmed client"
provides:
  - "ndc source search <topic> [--query] [--json]; ndc source pick <topic> <ranks...>"
  - "search_run/source_candidate (010, append-only); sources/search.py, europepmc.py, fulltext.py"
  - "config/retrieval.yaml (mesh, domain/audience terms, filters, tiers, fulltext sections, title_flag_terms)"
affects: [02-06, 02-10]
key-files:
  created: [config/retrieval.yaml, src/ndc/schema/010_candidates.sql, src/ndc/sources/search.py, src/ndc/sources/europepmc.py, src/ndc/sources/fulltext.py]
  modified: [src/ndc/sources/pubmed.py, src/ndc/sources/cli.py]
key-decisions:
  - "Query = condition MeSH AND domain terms [AND audience terms] (topics carry English-mappable domain keys; German titles are not translated)"
  - "Only safety-filter findings + retrieval title_flag_terms set the ⚠ flag; terminology warns ('disorder') are not candidate problems"
requirements-completed: [SRC-01]
duration: 35min
completed: 2026-10-26
---

# Phase 2 Plan 05: Retrieval Summary

**Topic → MeSH+domain PubMed query → ranked, filtered, cached shortlist; picking stores the abstract and, when open access, a clean full-text snapshot.**

## Live result (topic 3)
- Query: `("Attention Deficit Disorder with Hyperactivity"[MeSH] AND ("emotion regulation"[tiab] OR …)) NOT "Retracted Publication"[pt] NOT ("animals"[MeSH] NOT "humans"[MeSH])` → 22 candidates; every SR/MA ranks above every primary study.
- Medication papers flagged (rank 10 `any.medication_names`, rank 13 `en.medication`); title flags added for "Pharmacological …" etc.
- `ndc source pick 3 3` → abstract snapshot 1 (reused) + full-text snapshot 3 (180 sentences: Abstract 16, Introduction 39, Results 66, Discussion 59); 0 "Funding", 0 bracket citation markers, 0 empty brackets.

## Deviations from Plan
1. **[Rule 1] Safety flag scoped to safety findings** — the first live run flagged 19/22 titles via terminology warns.
2. **[Rule 2] `title_flag_terms`** in retrieval.yaml — "Systematic Review…: Efficacy of Pharmacological Interventions" was not caught by safety.yaml (Phase-1 config left unchanged).
3. **[Rule 3] Domain-term query instead of a German→English term_map** for titles.
4. **[Rule 1] JATS tail-text bug** fixed during live verification (removed xref tails were being moved to the paragraph start).
5. Tests use monkeypatched API functions + a recorded full-text fixture (no VCR), consistent with 02-01.

## Notes
- PubMed `sort=relevance` order differs between identical calls; each search_run is cached, picks resolve against the newest run.

## Next
Ready for 02-03 (verify).
