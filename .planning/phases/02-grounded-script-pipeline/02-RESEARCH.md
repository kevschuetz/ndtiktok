# Phase 2: Grounded Script Pipeline - Research

**Researched:** 2026-10-26 (inline, operator request: no subagents)
**Domain:** biomedical retrieval → content-hashed sentence store → Claude Citations draft (DE over EN sources) → adversarial structured verify → hash-bound human review (phone web UI) → DB-rendered source list
**Confidence:** HIGH on API shapes (all probed live today), MEDIUM on prompt quality/verifier calibration (one probe only)

## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01..D-04: real Anthropic API; Opus 5.5 drafts with Citations, Sonnet 5.5 verifies via structured output; IDs + prompts in config; no auto-repair; every call logged (DB row + content-hashed full request/response artifact).
- D-05..D-08: German draft cites original-language sentences; verifier checks cross-lingual drift/certainty escalation; review shows DE claim + verbatim original + verdict/note (DE); source list = original citation with German labels, DB-rendered only.
- D-09..D-13: operator picks 2–5 sources from a ranked shortlist (guidelines/SR/MA first), corpus locked before drafting; abstract + Europe PMC OA full text; exclude retracted + non-human; NO recency cut-off, NO evidence-tier floor; AWMF validity recorded, expired → warn only. Unresolvable/mismatched DOI/PMID blocks.
- D-14..D-16: unsupported/contradicts block; overstated/partial/escalation need per-claim OK; framing lines tagged, verifier flags smuggled claims; edit → new hashed version, re-verify changed claims only.
- D-17..D-19: phone-first web UI in its own container, 127.0.0.1 only (operator SSH tunnel); approve/reject/request-changes + per-claim ticks; editing stays CLI; no arbitrary path serving, no secrets reachable, approvals bound to script hash.

### Claude's Discretion
Schema/CLI names, prompt wording, splitter, ranking formula, web framework, query building, hook handling, length enforcement.

### Deferred Ideas (OUT OF SCOPE)
Phone-side editing; Telegram approve card (M2); exposing the polymarkt UI.

## Phase Requirements

| ID | Description | Research support |
|----|-------------|------------------|
| SRC-01 | PubMed (reviews/guidelines first) + Europe PMC retrieval, cached with PMID/DOI | Probe 1, 2; §Retrieval |
| SRC-02 | Manual AWMF S3 PDF import with version/validity | Probe 5; §AWMF |
| SRC-03 | Immutable content-hashed snapshots split into addressable sentences | Probe 5 (pysbd); §Source store |
| SRC-04 | DOI/PMID checked against Crossref/PubMed; mismatch blocks | Probe 3; §ID check |
| SCR-01 | 60–75s script with hook, sources only, claims cited to sentence IDs | Probe 4; §Draft |
| SCR-02 | Separate model, structured, 5 verdicts + certainty escalation | Probe 4b; §Verify |
| SCR-03 | Risk-sorted review ≤10 min, approval bound to script hash | §Review, UI-SPEC |
| SCR-04 | Source list rendered from stored sources only | §Source list |
| SCR-06 | Model IDs/prompts in config; every LLM call logged | §LLM layer (existing `llm_run` table) |

## Summary

Every risky integration was probed live on 2026-10-26 and works:

1. **Cross-lingual Citations work.** Opus 5.5 given an English abstract as a *custom-content document* (one content block = one sentence) wrote a German script whose text blocks carry `content_block_location` citations (`document_index`, `start_block_index`, `end_block_index` — **end is exclusive**, a single sentence `i` comes back as `i..i+1`) with English `cited_text`. Those indices map 1:1 to `source_sentence.ordinal`. The response interleaves uncited text blocks (hook, transitions like " Das Ergebnis: ", CTA) between cited ones.
2. **Opus 5.5 always thinks.** `thinking` cannot be disabled (400). With `max_tokens=1500` the draft truncated (1239 thinking tokens). Use `max_tokens ≥ 8000` (non-streaming is fine at that size; ~16 s) and set `output_config.effort` explicitly (default is `medium`). Observed: 1.8k in / 1.8k out (≈960 thinking).
3. **The draft spontaneously produced a medication claim** ("…dass sowohl Medikamente als auch Verhaltenstherapien helfen können…") from an abstract that mentions psychopharmacology. The Phase 1 claim-level safety filter (`check(text,'de','claim')`) is therefore load-bearing, and the system prompt must exclude blacklisted subjects explicitly; sources that are mainly about medication should be down-ranked/flagged at the candidate stage.
4. **It also emitted Markdown headings** on the first try. The prompt must demand plain spoken prose; the parser must strip/reject Markdown.
5. **Structured verify works** with `client.messages.parse(model="claude-sonnet-5-5", output_format=PydanticModel)` (SDK 2.3.0): 8 claims, 10 s, 1.7k in / 1.3k out. It is *strict*: 4/8 claims came back `partial` purely because the German line omitted a detail of the source sentence. The rubric must separate **"claim says more than the source"** (overstated / partial-support → needs OK) from **"claim says less / omits detail"** (→ `supports`, optional note). Otherwise the operator acks noise and the 10-minute budget breaks.
6. **Retrieval APIs are fast and stable** (PubMed 0.3 s, Europe PMC 0.27 s, Crossref 0.5 s). Bogus DOI → Crossref HTTP 404; bogus PMID → esummary `"error":"cannot get document summary"` (HTTP 200 — must check the field, not the status).
7. **OA full text is large**: one PLOS ONE systematic review = 229 KB JATS XML, ~223 sentences in Introduction+Methods+Results+Discussion. Keep Abstract + Introduction + Results + Discussion (+ Conclusions), drop Methods/Supporting/Data/Funding/References/tables. 5 sources ≈ 1,000 sentences ≈ 35–45k tokens — fits easily; prompt caching makes regeneration cheap.

**Primary recommendation:** one custom-content document per source (blocks = stored sentences, title = short citation), Citations ON, Opus 5.5 at effort `high`; claims = the script's sentences, with citations attached by text-block overlap; one Sonnet 5.5 structured call per script version that verifies cited claims AND classifies every uncited sentence (framing vs hidden claim). This makes "claim extraction" a deterministic mapping rather than a third LLM call.

## Architectural Responsibility Map

| Capability | Tier | Owner module (proposed) |
|---|---|---|
| Candidate search + ranking + filters | CLI + network | `src/ndc/sources/search.py` |
| Fetch → normalize → snapshot → sentences | CLI + network | `src/ndc/sources/fetch.py`, `store.py`, `split.py` |
| AWMF PDF import | CLI (local file) | `src/ndc/sources/awmf.py` |
| Identifier verification (Crossref/PubMed) | CLI + network | `src/ndc/sources/idcheck.py` |
| LLM call + logging + artifacts | library | `src/ndc/llm.py` (extends existing `llm_run`) |
| Draft (Citations) | CLI + Anthropic | `src/ndc/script/draft.py` |
| Verify (structured) | CLI + Anthropic | `src/ndc/script/verify.py` |
| Edit → new version | CLI | `src/ndc/script/edit.py` |
| Gate logic (approvable?) | library, pure | `src/ndc/review/gate.py` |
| Review decisions | library + CLI + web | `src/ndc/review/store.py`, `cli.py`, `web.py` |
| Source-list renderer | library, pure | `src/ndc/script/sources_list.py` |

The web container runs ONLY `ndc.review.web` (reads DB, writes `review`/`claim_ack` rows). It never needs the Anthropic/NCBI keys.

## Standard Stack

### Core (add to pyproject)
| Package | Version (verified PyPI 2026-10-26) | Why |
|---|---|---|
| anthropic | 2.3.0 | Citations + `messages.parse`; probed live |
| pymupdf | 2.0 | AWMF PDF → text with page numbers; smoke-tested |
| pysbd | 0.3.4 | Rule-based sentence splitter, DE + EN; handles "z. B.", "Ca.", "vgl. Abb. 3" correctly (probe). Old (2021) and emits `SyntaxWarning` on 3.13 — harmless; filter the warning at import. |

Already present: httpx, tenacity, pydantic, typer, sqlite-utils, pyyaml, rich, pytest-recording.

### Alternatives considered
| Instead of | Could use | Why not |
|---|---|---|
| pysbd | regex splitter | German abbreviations ("z. B.", "bzw.", "ca.") break naive splits — every bad split becomes a bad citation unit |
| pysbd | spaCy/stanza | 100s of MB models; overkill for M1 |
| custom-content docs | plain-text docs (auto sentence chunking) | auto chunking returns `char_location`; we'd lose the 1:1 ordinal mapping to stored sentences |
| PDF document blocks for AWMF | custom content from PyMuPDF sentences | keeps ONE citation unit (stored sentence) across all source types; page number stored per sentence |
| web framework (FastAPI/Flask) | stdlib `http.server` + explicit route table | 3 routes, no static files; fewer deps, no accidental static handler (D-19). Jinja-free: `html.escape` templates in code. |

### Package Legitimacy Audit
anthropic (official), pymupdf (Artifex, long-established), pysbd (nipunsadvilkar/pySBD, ~800★, widely used). No postinstall scripts (Python wheels). No new JS.

## Retrieval (SRC-01)

**PubMed** (E-utilities, `tool=ndc&email=…`, optional `NCBI_API_KEY` → 10 req/s; else 3 req/s):
- `esearch` JSON, `sort=relevance`, term = topic query AND evidence filter AND exclusions:
  - evidence: `(systematic[sb] OR Meta-Analysis[pt] OR Review[pt] OR Practice Guideline[pt] OR Guideline[pt])` — ranking, not exclusion (D-12): run once with this filter, once without (top 10 primary studies), merge.
  - exclusions: `NOT "Retracted Publication"[pt] NOT ("animals"[MeSH] NOT "humans"[MeSH])` (standard human-only idiom; keeps untagged reviews).
- `esummary` JSON → title, pubdate, pubtype, articleids (doi, pmc).
- `efetch` XML → AbstractText (keep `Label` attr as section), MeSH, `CommentsCorrectionsList/CommentsCorrections[@RefType="RetractionIn"]` (second retraction guard — retraction notices can be added after indexing).
- Probe query (emotion dysregulation in ADHD) returned 50 hits; top 3 included a GWAS meta-analysis → ranking must weight topic relevance (PubMed relevance order) above publication type alone.

**Europe PMC** (`/webservices/rest/search?format=json&resultType=core`): use for (a) OA full-text availability (`isOpenAccess`, `pmcid`) of PubMed candidates and (b) extra candidates with `PUB_TYPE:"systematic-review"`. Full text: `/{PMCID}/fullTextXML` (JATS). Transient 503s were reported in Phase-1 research → tenacity retry. Results include medication-centric reviews ("Central Stimulants in a Stressed Brain") → run `check(title,'de'/'en','topic')`-style safety screen on candidate titles and flag (not drop) hits.

**Ranking formula (proposed, discretion):** `score = tier_weight(pubtype) + relevance_rank_bonus + oa_bonus`; tier: guideline 3 > SR/MA 2 > review 1 > primary 0; relevance bonus from PubMed order (top-5 +1); OA full text +0.5. Shown with type/year so the operator decides (D-09).

**Query building:** default from topic `working_title`/`summary` + condition MeSH map (`ADHS→"Attention Deficit Disorder with Hyperactivity"[MeSH]`, `Autismus→"Autism Spectrum Disorder"[MeSH]`, dyslexia → `"Dyslexia"[MeSH]`, …) in `config/retrieval.yaml`; the CLI prints the query and accepts `--query` override (operator can edit).

**Caching:** a `source_candidate` row per (topic, search_run, pmid/doi) with metadata JSON; raw API responses stored as content-hashed artifacts under `/data/artifacts/raw/`.

## Source store (SRC-03)

- `source` = identity (pmid, pmcid, doi, awmf_reg_no, title, authors_json, year, journal, pubtypes_json, kind {pubmed, awmf}, language).
- `source_snapshot` = immutable: `sha256` of the canonical JSON of the ordered sentence list `[{section, page, text}]` (NFC-normalized), `retrieved_at`, `origin` {pubmed_abstract, epmc_fulltext, awmf_pdf}, `raw_artifact_sha256`, `UNIQUE(sha256)`. A re-fetch with changed text = new snapshot, never an update.
- `source_sentence` = `(snapshot_id, ordinal)` UNIQUE, `section`, `page`, `text`. Ordinal is the Citations block index.
- Snapshot hash includes section/page so the citation context is frozen too. Enforce immutability with SQLite triggers (`BEFORE UPDATE/DELETE ON source_sentence/source_snapshot → RAISE(ABORT)`).
- Artifacts: `/data/artifacts/<sha256[:2]>/<sha256>.<ext>` (raw XML/PDF, LLM request/response JSON). Write-once (skip if exists).
- Splitting: pysbd (`language='en'|'de'`, `clean=False`); drop sentences < 3 words; JATS `<xref>` citation markers `[12]` removed before splitting; tables/figures excluded.

## AWMF (SRC-02)

AWMF has no API and a bot-stopper (Phase-1 research): the operator downloads PDFs by hand. Import: `ndc source import-awmf <pdf> --register 028-045 --version "…" --valid-until YYYY-MM-DD [--status gültig|in Überarbeitung|abgelaufen]`. PyMuPDF 2.0 (`pymupdf.open(p)[i].get_text()`) extracts text per page; split per page with pysbd(de), store page number per sentence. Real AWMF PDFs have headers/footers repeated on every page and hyphenated line breaks — strip repeated first/last lines that occur on ≥50% of pages and de-hyphenate `-\n` before splitting. **No real AWMF PDF was available for this probe**; the plan's live verification step needs one operator-supplied PDF (S3 ADHS 028-045 is mid-revision — record status). Expired → `review` shows a warning chip, never a block (D-13).

## Identifier check (SRC-04)

Mechanical, never LLM:
- PMID: esummary; `error` field present → `unresolvable`; else compare normalized title (casefold, strip punctuation, ≥0.9 token-set similarity via `difflib.SequenceMatcher` ratio) and year ±1 → `ok` / `mismatch`.
- DOI: `GET https://api.crossref.org/works/{doi}` with UA `ndc/0.x (mailto:…)`; 404 → `unresolvable`; title/year compare as above. Crossref's `issued` year can differ from PubMed pubdate by 1 (online vs print) — hence ±1.
- PMID↔DOI consistency: esummary's `articleids.doi` must equal the stored DOI if both exist.
- AWMF: no registry API → `manual` status (operator-entered fields); not a blocker.
- Run at source import (so bad metadata never enters a corpus) AND re-checked (cached ≤30 days) at draft time for every source of the corpus; any `unresolvable`/`mismatch` among cited sources blocks drafting and approval. Network failure → `error` → blocks (fail closed), retry later.

## Draft (SCR-01)

Request shape (probed):
- `model` from config (`claude-opus-5-5`), `max_tokens` 8000, `output_config={"effort": "high"}` (config), no `thinking` param (always adaptive).
- `system`: style guide extract (hook in first sentence, 60–75 s ≈ 150–190 spoken German words at ~2.5 words/s, hedged "manche Menschen", identity-first wording, no diagnosis, **no medication/diagnosis/ABA/"ist mein Kind autistisch" content even if the source mentions it**, plain spoken prose — no headings/Markdown/stage directions, every factual sentence must be grounded in the documents). Loaded from `prompts/draft_de.md` (hashed).
- `messages[0].content`: one `document` per corpus source `{"type":"document","source":{"type":"content","content":[{"type":"text","text":s} …]},"title":"<Author et al. Year, Journal>","citations":{"enabled":true}}` with `cache_control` on the last document (corpus is stable across regenerations), then the topic text block.
- Citations and `output_config.format` are mutually exclusive (400) — the draft returns prose only.

Mapping: concatenate response text blocks → script text; record each cited block's char span + `(document_index → corpus source, start_block_index..end_block_index-1 → sentence ordinals)`. Segment the script into sentences (pysbd de); a script sentence's citations = union of cited blocks overlapping its span. Validate every citation's `cited_text` equals the stored sentence text (exact after whitespace normalization) — mismatch = bug, abort (substring-guard pattern from Phase 1 `judging._contains`).

Post-draft mechanical checks (fail fast, before verify spend): Markdown present → reject/regenerate; word count outside config range [150, 190] → warning shown in review (not a block); `check(script,'de','script')` and `check(sentence,'de','claim')` per sentence → `blocked` makes the version unapprovable (Phase 1 D-12 semantics, warn-tier needs recorded override).

Hook: one hook per draft (discretion: no variants in M1 — keeps the review ≤10 min); the first sentence is the hook and is classified like any other sentence.

## Verify (SCR-02)

One `messages.parse` call per script version (Sonnet 5.5; prompt `prompts/verify_de.md`). Input: every script sentence with ordinal, text, and for cited ones the full cited stored sentences (+ 1 neighbouring sentence each side for context, labelled). The verifier sees no draft reasoning. Output schema (Pydantic, strict):
- per sentence: `kind ∈ {empirical, hedged_generalization, advice, framing}`, `verdict ∈ {supports, partial, overstated, unsupported, contradicts, not_applicable}` (`not_applicable` only for `framing`), `certainty_escalation: bool`, `hidden_claim: bool` (framing that asserts a fact), `note_de: str`, `suggested_fix_de: str | None`.
- Rubric (calibrated after probe 4b): `supports` includes "claim says less than the source / omits detail"; `partial` = only part of the claim is backed; `overstated` = stronger/more general than source or dropped hedge; `unsupported` = no cited sentence backs it OR an uncited non-framing sentence; `contradicts` = source says the opposite.
- Server-side code then FORCES: uncited sentence with `kind≠framing` → `unsupported`; `hidden_claim=True` → `unsupported`. (Never trust the model to apply blockers.)
- Risk sort for review: contradicts > unsupported > overstated > partial > escalation > supports > framing; within a class by sentence order.
- Reuse on edit (D-16): verdict reused iff `sha256(sentence_text + sorted cited sentence ids + verify_prompt_sha + verifier_model)` is unchanged.

## Edit flow (D-16)

`ndc script export <version>` writes an editable text file where each sentence is followed by its citation markers `⟦12:3,12:4⟧` (snapshot_id:ordinal). Operator edits (CLI/editor), `ndc script import <file>` parses markers back, validates every marker refers to a sentence of THIS corpus, creates `script_version(parent=…)`, runs mechanical checks, re-verifies only changed sentences. A factual sentence whose markers were deleted → `unsupported` (blocks). Any approval on the parent hash is void by construction (approval rows key on `script_sha256`).

## Review gate (SCR-03)

Pure function `gate(version) -> GateResult{approvable, blockers[], needs_ack[], warnings[]}`:
- blockers: any `contradicts`/`unsupported` (after forcing); any check `blocked`; any warn-tier check finding without override; idcheck not `ok` for a cited source; script not yet verified.
- needs_ack: each `overstated`/`partial`/`certainty_escalation=True` sentence → needs a `claim_ack` row (operator, note optional) for this exact `script_sha256`.
- warnings: AWMF expired/under revision; word count out of range; verdicts reused.
- `approve(script_sha, reviewer, channel)` re-computes the gate inside the same write transaction; refuses if not approvable or if `script_sha` isn't the latest version of that script. Decisions: `approved | rejected | changes_requested` (+ note). Same tables for CLI and web (M2 Telegram writes the same rows).

## Source list (SCR-04)

Pure renderer over DB rows: distinct sources cited by sentences of the APPROVED version (not the whole corpus — only what was actually cited), ordered by first citation. Format (D-08): `Quellen:` then one line per source `Soler-Gutiérrez et al. (2023). PLOS ONE. doi:10.1371/journal.pone.0280131` / `PMID 36608036` / AWMF: `AWMF S3-Leitlinie ADHS (028-045), Version …, gültig bis …`. Platform limits (config): TikTok caption 4,000 chars, comment 150 chars → pinned-comment variant emits compact `Quellen: Soler-Gutiérrez 2023 (PMID 36608036); …` and if over the limit, splits into numbered comments; never truncates a citation. Refuses to render for a non-approved hash.

## LLM layer (SCR-06)

`llm_run` already exists (001_core.sql: stage, model, request_sha256, response_artifact_path, tokens, cost_usd). Extend via migration: `prompt_sha256`, `input_sha256s_json` (snapshot/script hashes), `cache_read_tokens`, `cache_write_tokens`, `thinking_tokens`, `request_artifact_path`, `stop_reason`, `request_id`, `subject_kind/subject_id`. One wrapper `llm.call(stage, request) -> (response, run_id)`: canonical-JSON the request (sorted keys) → sha256 → write artifact → call → write response artifact → insert row → return. Cost = tokens × `config/llm.yaml` price table (operator-maintained; **Opus 5.5 $4/$20 per MTok, cache read $0.20 (skill reference 2026-06-24); Sonnet 5.5 price NOT in reference → planner leaves it as a config value the operator confirms**). Errors: anthropic typed exceptions; SDK default 2 retries; `stop_reason=="max_tokens"` → fail loudly (truncated draft must never be stored as a version); `refusal` → fail loudly. Secrets never written into artifacts (request JSON contains no headers).

Cost estimate per script (5 sources with full text, ~40k input): draft ≈ 40k×$4 + 3k×$20 ≈ $0.22; verify ≈ 8k×(Sonnet price) + 2k out ≈ $0.05–0.10; ≈ **$0.30–0.40 per script**, regenerations cheaper via cache. 28 videos × ~2 versions ≈ $20.

## Web review UI (D-17..D-19)

- New compose service `ndc-review`: same image, `command: ["uv","run","--no-sync","ndc","review","serve","--host","0.0.0.0","--port","8090"]` inside the container, published as `127.0.0.1:8090:8090` only. **No `env_file`** (no Anthropic/NCBI keys in this container). Mounts: `/home/nd-content-volumes/data:/data` (DB, WAL) and `./config:/app/config:ro`. `mem_limit 256m`, `cpus 0.25`, `restart: unless-stopped`.
- stdlib `http.server.ThreadingHTTPServer`, explicit route table: `GET /` (pending reviews list), `GET /r/<script_sha>` (review page), `POST /r/<script_sha>/ack`, `POST /r/<script_sha>/decide`. Everything else → 404. No static-file handler, no path joins from request input; CSS inline. `<script_sha>` must match `^[0-9a-f]{64}$`.
- CSRF/stale protection: POST requires a per-page nonce (HMAC of script_sha + issued-at with a random key generated at server start, kept in memory) and the `script_sha` in the URL must still be the latest version → else 409 "veraltet".
- Host header check: `localhost`/`127.0.0.1` only (defends DNS rebinding through the tunnel).
- All interpolated text `html.escape`d (sources contain `<`, `&`).
- Never reads files other than the DB; no `/proc`, no env dump, no debug pages, no tracebacks to the client.

## Common Pitfalls

1. **Truncated draft stored as a version** — Opus 5.5 thinking eats `max_tokens`. Guard on `stop_reason`.
2. **Off-by-one block indices** — `end_block_index` is exclusive.
3. **Medication/diagnosis claims smuggled from sources** — claim-level safety check + prompt rule + candidate title flag.
4. **Verifier over-flags omissions** — calibrate rubric; otherwise ack fatigue.
5. **Trusting the verifier to enforce blockers** — force uncited/hidden claims to `unsupported` in code.
6. **esummary 200-with-error** for bad PMIDs — check the `error` key.
7. **Full-text bloat** — keep Abstract/Intro/Results/Discussion only.
8. **Mutable sources** — triggers forbid UPDATE/DELETE on snapshots/sentences.
9. **Web UI as an attack surface** (2026-10-21 incident) — no static handler, no secrets in the container, localhost bind, Host check, nonce.
10. **Recording ≠ script** — out of scope here (SCR-05, Phase 3), but the approved hash is what Phase 3 diffs against; keep `script_version.text` canonical (NFC).

## Environment Availability

| Item | Status |
|---|---|
| ANTHROPIC_API_KEY in `/home/nd-content/.env` | present (probed: models list OK) |
| `claude-opus-5-5`, `claude-sonnet-5-5` | listed by `models.list()` 2026-10-26 |
| NCBI API key | absent → 3 req/s (fine); optional `NCBI_API_KEY`, `NCBI_EMAIL` in `.env.example` |
| Outbound HTTPS to eutils/ebi/crossref/anthropic from container | OK (probed) |
| Real AWMF PDF | **operator must supply** for live verification |
| Host port 8090 on 127.0.0.1 | free (only 8082 in use by polymarkt) |

## Validation Architecture

- Framework: pytest 9.1 in container (`bash scripts/test.sh`), pytest-recording cassettes for PubMed/EPMC/Crossref/Anthropic (keys scrubbed: filter `x-api-key`, `api_key` query).
- Unit (no network): splitter cases (DE abbreviations), snapshot hashing/immutability triggers, citation→sentence mapping incl. exclusive end, gate truth table, renderer limits, export/import markers, web route table (only 4 routes; `/../etc/passwd`, `/proc/self/environ`, `/static/x` → 404), Host check, nonce, stale sha → 409.
- Recorded integration: one cassette each for search, fetch abstract, fetch full text, Crossref ok/404, draft, verify.
- Live end-to-end (final plan): one real whitelisted topic → search → pick → draft → verify → phone review via tunnel → approve → render list; operator times the review (target ≤10 min).
- Pre-existing failing tests: `tests/scan/test_discover.py` (2) — exclude from the gate (comm-diff of failed set).

## Security Domain (ASVS L1)

V5 input validation (sha regex, marker parsing, PDF path is a CLI arg not web input), V4 access control (localhost bind + SSH tunnel; no auth beyond that by operator decision), V13 API (CSRF nonce, Host check), V7 errors (no tracebacks to client), V8 data protection (no secrets in web container/artifacts), V12 files (no file serving).

## Assumptions Log
- A1: Sonnet 5.5 pricing unknown → config value, operator confirms. (LOW)
- A2: ~2.5 spoken words/s for Austrian standard German → 150–190 words for 60–75 s. (MEDIUM)
- A3: pysbd quality on real AWMF PDF text after de-hyphenation is acceptable. (MEDIUM — verify in live plan)
- A4: TikTok comment limit 150 chars, caption 4,000 chars. (MEDIUM — config)

## Open Questions
- None blocking. Verifier rubric quality will only be known after the live run; prompts are config, so tuning is a config change.

## Sources
- Live probes 2026-10-26 (scratchpad `probe_cit.py`, `probe_ver.py`; responses saved): PubMed E-utilities, Europe PMC REST, Crossref, Anthropic Messages (Citations custom content, `messages.parse`), `models.list`.
- claude-api skill reference (cached 2026-06-24): Opus 5.5 pricing/thinking/effort, Citations ⟂ structured outputs.
- `.planning/research/{ARCHITECTURE,STACK,PITFALLS,SUMMARY}.md`.
- `/home/polymarkt-watch/docs/incidents/2026-10-21-safe-drain.md` (web UI threat).

## Metadata
Inline research by the orchestrating session; total API spend ≈ $0.10.
