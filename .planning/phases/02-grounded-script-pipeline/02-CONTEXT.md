# Phase 2: Grounded Script Pipeline - Context

**Gathered:** 2026-10-26
**Status:** Ready for planning

<domain>
## Phase Boundary

For any whitelisted topic: retrieve candidate sources (PubMed + Europe PMC, reviews/guidelines first) and import AWMF S3 PDFs by hand; store each source as an immutable, content-hashed snapshot split into numbered sentences with PMID/DOI metadata; generate a German 60–75s script with a hook whose claims cite source-sentence IDs; mechanically verify every DOI/PMID; run a separate adversarial verifier; let the operator approve risk-sorted claim ↔ source-sentence pairs (approval bound to the script hash); render the caption/pinned-comment source list from stored records only; log every LLM call.

Requirements: SRC-01, SRC-02, SRC-03, SRC-04, SCR-01, SCR-02, SCR-03, SCR-04, SCR-06.
Not in this phase: Whisper recording diff (SCR-05), crisis playbook, accounts, metrics, readout (Phase 3/4); Remotion/TTS/scheduler/Telegram approve card (milestone 2).

</domain>

<decisions>
## Implementation Decisions

### LLM execution
- **D-01:** Real Anthropic API calls from `ndc` (ends the Phase 1 D-21 in-session pattern for this phase). Draft uses the Citations API over document/custom-content blocks; verifier uses `messages.parse` structured output (no citations — the two are API-incompatible in one call). `ANTHROPIC_API_KEY` from `/home/nd-content/.env`.
- **D-02:** Draft model `claude-opus-5-5`, verifier `claude-sonnet-5-5` — two different models by rule; both IDs (and prompts) live in config, never hard-coded (SCR-06). Planner verifies the IDs against the live lineup.
- **D-03:** No auto-repair loop. Verifier flags are shown to the operator; the operator edits or regenerates.
- **D-04:** SCR-06 logging = a DB row per call (model, prompt hash, input content hashes, token counts, cost, timestamp, run id) plus the full request/response JSON stored as a content-hashed artifact file, so any script can be replayed/audited later.

### English sources → German script
- **D-05:** The draft is written directly in German, citing the original-language (mostly English) source sentences. No English-draft-then-translate stage.
- **D-06:** The verifier judges German claim vs original-language sentence cross-lingually and explicitly checks translation drift / certainty escalation (e.g. "may be associated" → "ist", dropped "some").
- **D-07:** Review view per claim: German claim + cited sentence(s) verbatim in the original language + verdict and verifier note (in German). No machine-translated gloss of sources.
- **D-08:** Source list format: original citation (authors, year, journal, DOI/PMID; titles in original language) with German framing labels (e.g. "Quellen:"). Rendered purely from DB rows (SCR-04), within platform length limits.

### Source selection & depth
- **D-09:** Operator picks 2–5 sources per script from a ranked candidate shortlist (guidelines / systematic reviews / meta-analyses ranked first; show title, year, publication type). The picked set is locked as the script's corpus before drafting.
- **D-10:** Corpus depth: abstract always, plus Europe PMC open-access full text (body sections) when available. Sentence-split everything; keep section labels.
- **D-11:** Hard filters: exclude retracted papers (PubMed Retracted Publication / retraction notices); human studies and reviews only (no animal/in-vitro support).
- **D-12:** Deliberately NOT applied: no recency cut-off and no evidence-tier floor — a single primary human study may support a claim. Ranking still prefers guidelines/reviews.
- **D-13:** AWMF import records register number, version and the "gültig bis" date (operator-entered); citing an expired or under-revision guideline shows a warning in review but does not block.
- SRC-04: an unresolvable or mismatched DOI/PMID (Crossref/PubMed, title/year match) blocks the script — mechanical, never LLM-judged.

### Review & approval
- **D-14:** Blocking rules: any `unsupported` or `contradicts` claim makes the script unapprovable. `overstated` / `partial` / certainty-escalation claims each need an explicit per-claim operator OK (optional note). `supports` needs no action.
- **D-15:** The claim extractor tags every sentence (empirical / hedged generalization / advice / framing). Framing lines (hook, transitions, CTA) need no citation, but the verifier flags any framing line that smuggles in a factual claim. Terminology + safety checks (Phase 1 engine) run on the script and every claim.
- **D-16:** An edit creates a new hashed script version (any approval on the old hash is void); ndc re-runs extraction + verification, reusing verdicts only for byte-identical claims with identical evidence.
- **D-17:** Review surface is phone-first: a small ndc web UI in its own Docker container (pattern like the polymarkt copy-desk UI). From the phone the operator can tick per-claim OKs, approve, reject, or request changes with a free-text note. Script editing and regeneration stay at the CLI / session.
- **D-18:** Access: the container binds to `127.0.0.1` only; the operator reaches it through their own SSH tunnel. No public port, no Tailscale/Cloudflare.
- **D-19 (security, from the 2026-10-21 polymarkt Safe-drain incident):** the UI must not serve arbitrary file paths (no generic static handler that could reach `/proc`, `.env`, `/data`), never exposes secrets or env, keeps the API key out of the web container if feasible, and every approval request is bound to the exact script hash (stale hash → rejected). Same review table regardless of channel, so M2's Telegram card can write identical rows.

### Claude's Discretion
- Schema/migration details, CLI command names, prompt wording, sentence splitter choice, ranking formula, exact cost logging, web framework (keep it minimal).
- How topic → PubMed/Europe PMC query is built (MeSH + publication-type filters per research); operator can see/edit it.
- Hook handling (single hook vs variants) and script length enforcement for 60–75s.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project
- `.planning/PROJECT.md` — core value, constraints (budget, operator time, shared host)
- `.planning/REQUIREMENTS.md` — SRC-01..04, SCR-01..04, SCR-06
- `.planning/ROADMAP.md` §Phase 2 — goal and success criteria
- `PROJECT-BRIEF.md` — pillars, tone, whitelist

### Research
- `.planning/research/ARCHITECTURE.md` — evidence-ledger data model (`source` / `source_snapshot` / `source_sentence` / `claim` / `claim_evidence` / `review`), cite-by-ID pattern, hash-bound approval, two-pass verifier
- `.planning/research/STACK.md` — anthropic SDK 2.x (Citations, `messages.parse`), PubMed E-utilities + Europe PMC REST, PyMuPDF 2.0 for AWMF PDFs, rate limits
- `.planning/research/PITFALLS.md` — citation hallucination, dropped hedges, fact-checking the wrong artifact
- `.planning/research/SUMMARY.md` — synthesis, model-ID note, AWMF version status

### Phase 1 outputs consumed here
- `.planning/phases/01-market-decision-content-foundation/01-CONTEXT.md` — D-12..D-15 (checker tiers, identity-first wording, gendering), D-21 (in-session pattern now superseded for Phase 2)
- `config/style_guide.md` — fixed 60–75s template, hook rules, hedged tone
- `config/terminology.yaml`, `config/safety.yaml` — rules consumed by the script/claim checks
- `config/topic_seed.yaml` + `docs/topic-backlog.csv` — whitelisted topics
- `docs/language-decision.md` — German decision

### Incident context
- `/home/polymarkt-watch/docs/incidents/2026-10-21-safe-drain.md` — why the web UI must be localhost-only and must never serve arbitrary paths

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ndc/checks/engine.py` (`check`, `text_sha256`, `record_override`): terminology + safety check on any text with hard/soft tiers and recorded overrides — run on scripts and claims.
- `src/ndc/db.py` (`Database`, numbered SQL migrations in `src/ndc/schema/`): add Phase 2 tables as new migrations.
- `src/ndc/scan/judging.py` (`_contains`, `apply_evidence_guard`, strict Pydantic models): substring evidence-guard pattern reusable for checking cited text against stored sentences.
- `src/ndc/config.py` (`config_dir`, `load_env`): config + `.env` loading; model IDs/prompts go in config here.

### Established Patterns
- Python 3.13 + uv + Typer CLI (`ndc ...`), SQLite with WAL, pydantic strict models, tenacity around network calls, pytest-recording cassettes for HTTP.
- docker-compose `nd-content` project: CLI-only, resource-capped (`mem_limit` 1g), no ports, quiet hours 00:15–06:00 UTC for heavy work. The web UI will be the first service with a port (127.0.0.1 only).

### Integration Points
- New `src/ndc/sources/`, `src/ndc/script/`, `src/ndc/review/` style packages registered on the root Typer app in `src/ndc/cli.py`.
- Topics come from the Phase 1 topic matrix (whitelist only).

</code_context>

<specifics>
## Specific Ideas

- Operator reads English papers comfortably; no machine translation of sources needed.
- Operator drives from a phone; the approval step must be usable there.
- Known pre-existing test debt: `tests/scan/test_discover.py` 2 failures (see Phase 1 `deferred-items.md`), not this phase's scope.

</specifics>

<deferred>
## Deferred Ideas

- Editing script text from the phone — not now (phone does approve/reject/request changes only).
- Telegram approve card — milestone 2 (AUTO-02); the shared review table keeps it a channel swap.
- Exposing the polymarkt copy-desk UI through the same tunnel — out of this project's scope.

</deferred>

---

*Phase: 02-grounded-script-pipeline*
*Context gathered: 2026-10-26*
