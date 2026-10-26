---
phase: 02-grounded-script-pipeline
verified: 2026-10-26T19:45:00Z
status: passed
score: 5/5 roadmap success criteria verified (criterion 1 AWMF part by tests only — operator deferral); 11/11 plans with must_haves checked
overrides_applied: 1
notes:
  - "Operator decision 2026-10-26: close Phase 2 without the real AWMF 028-045 PDF (02-06 Task 2). The import path is test-covered (tests/sources/test_awmf.py) but no guideline snapshot exists in the live DB; recorded as a deferred item in STATE.md for Phase 3."
  - "Verification done inline (operator: no subagents). Evidence = live DB queries, CLI runs, code reads and the 02-LIVE-RUN.md log of the 2026-10-26 run on topic 2."
  - "Full test suite 505 passed, ruff check/format clean, after fixing two stale tests (see 02-REVIEW.md IN-04)."
---

# Phase 2: Grounded Script Pipeline Verification Report

**Phase Goal:** For any whitelisted topic, the operator can produce a script in which every claim traces to a stored source sentence. The script is adversarially checked, approved by the operator in ≤10 min, and ships with a source list that no model wrote.
**Verified:** 2026-10-26
**Status:** passed (1 operator deferral recorded)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Operator retrieves PubMed/Europe PMC candidates (reviews/guidelines first) and imports an AWMF S3 PDF with version/validity; each source an immutable, hashed, sentence-split snapshot with PMID/DOI | ✓ VERIFIED (AWMF live import DEFERRED) | Live: `ndc source search 2` → search_run 7/8, SR/MA ranked above reviews above primary (02-LIVE-RUN §K1); `source pick 2 9 10 11 6` → snapshots 7–11 (Kim 2025 OA full text 127 sentences with sections). Triggers `*_no_update/_no_delete` on `source_snapshot`, `source_sentence`, `script_version`, `script_sentence`, `script_citation` (`schema/008_ledger.sql:114-133`). AWMF: `ndc source import-awmf` with register/version/valid-until/status/title, page numbers, header/footer removal — tests green; no live PDF (operator deferral). |
| 2 | Script 60–75 s with hook from those sources only, each claim cited to source-sentence IDs; fake/mismatched DOI/PMID blocks the script | ✓ VERIFIED | Live: topic-2 v8–v11, 182–190 words, every cited sentence → `script_citation` rows (markers ⟦snapshot:ordinal⟧); `map_citations` raises `CitationMismatch` when `cited_text` ≠ stored sentences (`draft.py:150`). Negative case on scratch DB: DOI → 10.1371/journal.pone.9999999 → `check-ids` unresolvable → `script draft` "Quelle nicht verifizierbar" with `llm_run` count unchanged (13 → 13). Gate hook `block_idcheck` blocks approval. |
| 3 | Separate verifier labels supports/partial/overstated/unsupported/contradicts + certainty escalation; operator reviews risk-sorted pairs and approves; approval bound to hash, edit voids it | ✓ VERIFIED | `claude-sonnet-5-5` via `messages.parse(VerifyReport)`; `load_llm_config` raises if verify model equals draft/editor model. Live v9: 6 supports / 1 partial / 3 unsupported (2 forced hidden_claim, 1 uncited) / 13 framing. Review UI + CLI sort by `RISK_ORDER`. Approval of v11 `4299e91a…` written only after `gate()` inside `BEGIN IMMEDIATE` (`store.py:75-91`); `review`/`claim_ack` key on `script_sha256`; v10→v11 edit produced a new sha and v10 shows „veraltet". Operator approval 2 min (channel web). |
| 4 | Caption / pinned-comment source list rendered only from stored source records | ✓ VERIFIED | `ndc script sources 4299e91a --variant caption|comment` rendered 4 DOIs / 4 PMIDs from `source` rows 6,7,8,9 (all id_check ok); `NotApproved` before approval; Jinja templates in `config/source_list.yaml`, no LLM stage involved (`script/sources_list.py`). |
| 5 | Model IDs and prompts from config; each LLM call logged with model, prompt hash, inputs, output | ✓ VERIFIED | `grep -rn "claude-" src/ndc` → none. `config/llm.yaml` holds draft/editor/verify model, effort, max_tokens, prompts, prices. `llm_run` rows 11–15 carry stage, model, prompt_sha256, request_sha256, input_sha256s_json, tokens incl. cache/thinking, cost_usd (Sonnet price filled 2026-10-26), stop_reason, request_id; request/response artifacts exist on disk (checked). |

**Score:** 5/5 criteria verified; criterion 1's AWMF leg relies on tests (operator deferral, override recorded).

### Plan-Level Must-Haves (11 plans)

| Plan | Representative must-have | Status | Evidence |
|---|---|---|---|
| 02-01 | Immutable snapshots, corpus lock 2–5 sources, retracted refused, whitelist only | ✓ | Triggers (above); `corpus lock 2` → corpus 3 with 5 snapshots; `draft()` refuses non-whitelist topics (`draft.py:277`). |
| 02-02 | Citations draft, cited_text equality, no Markdown/max_tokens stored, mechanical checks per version, llm_run logging | ✓ | `map_citations`, `has_markdown`, `LlmTruncated/LlmRefused` raised after logging (`llm.py:228-231`); `check_json` on every version (v10 `needs_override` on „Symptome"). |
| 02-03 | Different model, structured output, forced blockers in code, no auto-repair | ✓ | `verify.py:118-128 force()`; suggested fixes stored as text only; live v9 forced rows (`forced_reason` hidden_claim/uncited). |
| 02-04 | Pure gate, risk-sorted review, approval in same transaction, DB-only source list, GATE_HOOKS | ✓ | `gate.py`, `store.py`, `sources_list.py`; hooks `awmf_gate_issues`, `idcheck_gate_issues` registered. |
| 02-05 | Ranked search, evidence tiers, retraction/animal exclusions, ⚠ flags, OA full text, cached runs | ✓ | Live query text ends with the exclusions; ⚠ on `title:pharmacolog`/`en.supplements`; Kim 2025 full text snapshot; runs 7 and 8 both retained. |
| 02-06 | AWMF import validation, dedupe, pick-snapshot, expired → warning, id_check manual | ✓ code / DEFERRED live | tests green; D-13a reverted to warn-only; Task 2 deferred (STATE.md Deferred Items). |
| 02-07 | PMID/DOI resolution, title ≥0.90 + year ±1, fail-closed errors, pre-draft and gate enforcement | ✓ | `idcheck.py`; live 4/4 ok; scratch negative case. |
| 02-08 | Export/import markers, new version, stale parent refused, selective re-verify, reuse warning | ✓ | Live imports: „4 neu geprüft · 18 übernommen", „5 neu geprüft · 15 übernommen"; „keine Änderung am Text" refusal observed; „Bewertungen aus Vorversion übernommen" warning shown. |
| 02-09 | Four routes, no static handler, Host allow-list, HMAC nonce, stale → 409, secret-free container | ✓ | `web.py` read in full; compose `ndc-review`: 127.0.0.1:8090, no env_file, read_only, cap_drop ALL, 256m (02-09 live security checks). Operator used it twice today. |
| 02-10 | Live run, timed approval, LIVE-RUN per criterion, runbook, README/CLAUDE.md | ✓ | `02-LIVE-RUN.md` (5 „Kriterium" sections, Review-Zeit 2 min), `docs/script-pipeline.md` (Fehlerbehebung table), README, CLAUDE.md section outside GSD markers, `.env.example`. |
| 02-11 | Hook tactics, no disclaimer line, hook_examples from competitor transcripts, punch pass with marker restriction + re-verify, operator judgment | ✓ | `grep "kein Therapeut" config/prompts/draft_de.md` → none; `editor.py:70-72` refuses invented markers; v7 (topic 3) and v11 (topic 2) approved on the phone. |

### Required Artifacts
All plan artifacts exist and are substantive: `src/ndc/{llm,artifacts}.py`, `sources/{store,pubmed,europepmc,fulltext,search,split,awmf,idcheck,cli}.py`, `script/{draft,verify,edit,editor,sources_list,cli}.py`, `review/{gate,store,cli,web,web_render}.py`, schemas 008–012, `config/{llm,retrieval,source_list}.yaml`, `config/prompts/{draft_de,editor_de,verify_de,engagement_playbook}.md`, `docs/script-pipeline.md`, `02-LIVE-RUN.md`. Note: `config/prompts/hook_examples_de.md` named in plan 02-11 was folded into `engagement_playbook.md` (02-11 SUMMARY).

### Key Link Verification
| From | To | Via | Status |
|---|---|---|---|
| `script/draft.py` | `sources/idcheck.ensure_corpus_ok` | direct call before `llm.call` | ✓ WIRED (scratch negative case) |
| `review/gate.py GATE_HOOKS` | `awmf_gate_issues`, `idcheck_gate_issues` | `_register_default_hooks()` | ✓ WIRED |
| `review/web.py` | `review/store.ack/decide` | channel `web` | ✓ WIRED (review row 3, claim_ack row 3) |
| `script/editor.py` | `script/edit.import_edit` → `script/verify.verify` | marker-restricted import | ✓ WIRED (v8→v9) |
| `script/sources_list.py` | `source` rows of cited snapshots | SQL join, approval check | ✓ WIRED |

## Requirements Coverage
| Requirement | Status |
|---|---|
| SRC-01 retrieval cached with metadata | ✓ SATISFIED |
| SRC-02 AWMF import with version/validity | ✓ SATISFIED (code + tests; live PDF deferred) |
| SRC-03 immutable hashed sentence snapshots | ✓ SATISFIED |
| SRC-04 DOI/PMID auto-check blocks | ✓ SATISFIED |
| SCR-01 grounded 60–75 s script with hook | ✓ SATISFIED |
| SCR-02 adversarial structured verify | ✓ SATISFIED |
| SCR-03 risk-sorted review ≤10 min, hash-bound approval | ✓ SATISFIED (2 min) |
| SCR-04 DB-only source list | ✓ SATISFIED |
| SCR-06 config models/prompts, logged calls | ✓ SATISFIED |

## Anti-Patterns Found
| File | Pattern | Severity | Note |
|---|---|---|---|
| `script/verify.py:120` | hidden_claim overrides a `supports` model verdict | ⚠️ Warning | 02-REVIEW WR-01, follow-up |
| `sources/search.py:116` | `custom` facet bypasses required-facet warning | ⚠️ Warning | 02-REVIEW WR-02, follow-up |
| — | `TODO`/placeholder/stub | none | only `pass` bodies in exception classes |

## Human Verification Required
None outstanding. Operator-performed: phone approvals of topic-3 v7 and topic-2 v11 (timed 2 min), judgment „keep it for now". Deferred (not a verification gap): real AWMF PDF import.
