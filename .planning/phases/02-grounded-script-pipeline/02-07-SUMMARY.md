---
phase: 02-grounded-script-pipeline
plan: 07
subsystem: retrieval
tags: [crossref, pubmed, doi, pmid, verification]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-02 draft, 02-04 GATE_HOOKS, 02-06 awmf sources"
provides:
  - "011_idcheck.sql; sources/idcheck.py (check_source, ensure_corpus_ok, idcheck_gate_issues, latest_status, summary)"
  - "ndc source check-ids --topic [--force]; add/pick report ID status"
affects: [02-10]
key-decisions:
  - "draft() calls idcheck.ensure_corpus_ok directly (before any LLM call), not via a hook"
  - "Offline test suites stub idcheck via autouse fixtures; tests/sources opt in with @pytest.mark.real_idcheck"
requirements-completed: [SRC-04]
duration: 25min
completed: 2026-10-26
---

# Phase 2 Plan 07: Identifier check Summary

**Every PMID/DOI is mechanically resolved against PubMed/Crossref; a fake, mismatched or unreachable identifier stops drafting before any LLM spend and blocks approval.**

## Live result
`ndc source check-ids --topic 3` → PMID 36608036 ok, PMID 27180913 ok (PubMed + Crossref title/year match).

## Tests (offline, recorded Crossref body)
ok; wrong title → mismatch; fake DOI 10.1371/journal.pone.9999999 → unresolvable; bogus PMID → unresolvable (esummary 200-with-error); year ±1 tolerance; PubMed DOI ≠ stored DOI → mismatch; transport error → error (fails closed); AWMF → manual; draft with a fake-DOI source raises before the client is touched; gate hook returns `block_idcheck`. Full suite 501 passed.

## Deviations from Plan
1. Live negative case demonstrated in tests rather than a scratch-DB CLI run.
2. pick() stays network-free; the CLI runs the check after add/pick.
