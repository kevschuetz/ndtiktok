---
phase: 02-grounded-script-pipeline
plan: 06
subsystem: retrieval
tags: [awmf, pdf, pymupdf, guidelines]
requires:
  - phase: 02-grounded-script-pipeline
    provides: "02-01 store_snapshot/pick, 02-04 GATE_HOOKS"
provides:
  - "sources/awmf.py: extract_pages (lazy pymupdf), clean_pages (header/footer ≥50 % removal, hyphenation join), import_awmf, awmf_gate_issues"
  - "ndc source import-awmf <pdf> --register --version --valid-until --status --title [--topic] [--new-version]; ndc source pick-snapshot <topic> <snapshot_id>"
  - "Gate warning for expired / in-revision guidelines (D-13, D-13a reverted: warn only); id_check status 'manual' for AWMF"
affects: [02-07, 02-10, 03]
key-decisions:
  - "Expired AWMF guidelines WARN with 'abgelaufen seit <date> — Aussagen bewusst prüfen'; they never block drafting or approval (operator reverted D-13a: 'we will use this S3 thing')"
  - "pymupdf imported lazily inside extract_pages — top-level import pulled onnxruntime and OOM'd the 256 MB review container"
  - "Task 2 (real 028-045 PDF) deferred by the operator on 2026-10-26 ('close it without pdf for now and move on'); tracked as a deferred item for Phase 3"
requirements-completed: [SRC-02, SRC-03]
duration: 40min (Task 1) + deferred Task 2
completed: 2026-10-26
---

# Phase 2 Plan 06: AWMF S3 PDF import Summary

**Operator-downloaded AWMF guideline PDFs import as page-numbered, immutable German sentence snapshots with register number, version and validity; the gate warns when a cited guideline is expired. The real 028-045 PDF has not been imported yet (deferred).**

## Task 1 — code (commits 584b801, aaffc54)
- PyMuPDF 2.0 smoke-tested on a synthetic PDF fixture: text + page numbers extracted; running headers/footers on ≥ 50 % of pages removed; end-of-line hyphenation joined before sentence splitting; section labels from `retrieval.yaml awmf.section_pattern`.
- Validation: register `^\d{3}-\d{3}[A-Za-z]?$`, `--valid-until` must parse, file must start with `%PDF-` and be ≤ 50 MB, else exit 1 without writing. Same bytes → existing snapshot; same register+version with different bytes → refused unless `--new-version`.
- `awmf_gate_issues` appended to `GATE_HOOKS`; `idcheck` returns `manual` for kind `awmf` and never blocks. Tests in `tests/sources/test_awmf.py` (incl. facet changes from 02-11) green in the 505-test suite.

## Task 2 — operator PDF: DEFERRED
register.awmf.org sits behind an Anubis JS bot challenge; per Phase-1 D-16 the download is never scripted. The operator has not uploaded `028-045l_S3_ADHS_2018-06-abgelaufen.pdf` to `/home/nd-content-volumes/data/awmf/` and decided on 2026-10-26 to close Phase 2 without it. Consequences:
- Phase-2 success criterion 1 ("imports an AWMF S3 PDF with its version/validity recorded") is demonstrated by tests, not by a live import.
- The 02-10 live run used PubMed sources only; German guideline statements are not yet citable.
- Runbook §7 (`docs/script-pipeline.md`) documents the exact import command for when the PDF arrives.

**Deferred item:** "Import real AWMF 028-045 PDF (operator browser download → scp → `ndc source import-awmf … --status abgelaufen`), sanity-check 10 sample sentences" → Phase 3, before the first ADHS guideline claim is scripted.

## Deviations from Plan
1. **[Rule 1] D-13a amendment and same-day reversal** — expired guidelines briefly blocked drafting/approval, then went back to warn-only at the operator's request.
2. **[Rule 1] Lazy pymupdf import** to keep the review container under its memory limit.
3. Task 2 not executed (human-action checkpoint deferred by the operator).
