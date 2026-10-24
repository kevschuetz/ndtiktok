# Architecture Research

**Domain:** Research-grounded short-form health content production (neurodivergence), human-gated pipeline
**Researched:** 2026-10-24
**Confidence:** MEDIUM-HIGH. The structural recommendations are design judgment on standard patterns, and they are firm. The vendor facts (Claude Citations, TikTok APIs, NCBI limits) were verified against official docs today. Metrics-API coverage for Instagram/YouTube/schedulers is MEDIUM/LOW and is flagged where it comes up.

---

## Core Thesis (read this first)

Treat the system as a **ledger of evidence**, not a video factory. The durable asset in milestone 1 is a SQLite
database in which every spoken sentence of every published video traces back through this chain:

`claim → claim_evidence → source_sentence → source_snapshot (immutable, content-hashed) → source (PMID/DOI/AWMF id)`

Each link records who approved it, when, and against which exact script hash. Milestone 2 does not replace any
part of this. It only adds stages after `script.approved` (voice, render, publish) and before `topic.selected`
(analytics feedback). If the milestone-1 schema already has stable IDs, immutable versions, and a channel-agnostic
review record, milestone 2 can be built as pure additions.

Three decisions make that work:

1. **Sentence-level source storage with stable IDs.** Retrieval stores sources pre-split into numbered sentences.
   Both the script generator and the fact-checker cite *sentence IDs*, never free-text quotes. Claude's Citations
   API supports this directly through "custom content" documents. Each content block is one of our sentences, and
   a citation comes back as a block index range, which maps 1:1 onto our `source_sentence` rows (verified, see
   Sources).
2. **Content-addressed, immutable artifacts.** Source snapshots, script versions and fact-check runs are never
   updated in place. An edit creates a new version with a new hash. Approval binds to a hash, so any later edit
   automatically voids it.
3. **One review-decision table, many channels.** In M1 the operator approves via a CLI and a generated review
   sheet. In M2 the operator approves via a Telegram card. Both write the same `review` rows. The gate logic
   ("can this advance?") reads only the table and never checks which channel wrote it.

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ CONTROL: CLI (M1) ── later: scheduler + Telegram bot (M2) — both call same stages │
├──────────────────────────────────────────────────────────────────────────────────┤
│                       FRONT HALF (Milestone 1, reused as-is in M2)                │
│  ┌─────────┐   ┌───────────┐   ┌──────────┐   ┌────────────┐   ┌──────────────┐  │
│  │ Topic   │──▶│ Retrieval │──▶│ Script   │──▶│ Fact-check │──▶│ Review gate  │  │
│  │ matrix  │   │ + snapshot│   │ (grounded│   │ (adversar.)│   │ (human)      │  │
│  │ +select │   │ +sentences│   │  cites)  │   │ claim↔sent │   │ approve/edit │  │
│  └────▲────┘   └───────────┘   └──────────┘   └────────────┘   └──────┬───────┘  │
│       │                                                               │          │
│       │        ┌──────────────────────────────────────────────────────▼───────┐  │
│       │        │ Source-list renderer (caption / pinned comment, from links)  │  │
│       │        └──────────────────────────────────────────────────────┬───────┘  │
├───────┼───────────────────────────────────────────────────────────────┼──────────┤
│       │                 BACK HALF (M1: manual  │  M2: automated)      ▼          │
│       │   M1: operator records + posts by hand, enters post URL                  │
│       │   M2: ┌───────┐ ┌────────┐ ┌───────┐ ┌────────┐ ┌─────────┐ ┌─────────┐  │
│       │       │ Voice │▶│Transcr.│▶│Visuals│▶│ Render │▶│Telegram │▶│ Publish │  │
│       │       │rec/TTS│ │+diff vs│ │Remotion│ │        │ │approve  │ │scheduler│  │
│       │       └───────┘ │approved│ └───────┘ └────────┘ └─────────┘ └────┬────┘  │
│       │                 └────────┘                                       │       │
├───────┼──────────────────────────────────────────────────────────────────┼───────┤
│       │                 MEASUREMENT (M1 manual entry → M2 API pulls)     ▼       │
│  ┌────┴──────────────┐   ┌──────────────────────────────────────────────────┐    │
│  │ Readout / feedback│◀──│ Metrics snapshots at fixed post ages (48h, 7d)   │    │
│  │ (format scores)   │   └──────────────────────────────────────────────────┘    │
│  └───────────────────┘                                                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│ STORAGE: SQLite (ledger)  │  artifacts/ by content hash (snapshots, prompts,      │
│                           │  LLM transcripts, audio, renders)  │  config + prompts│
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation | Milestone |
|-----------|----------------|------------------------|-----------|
| **Topic matrix** | Enumerate valid cells `pillar × condition × domain × audience × angle`. Apply the whitelist/blacklist. Track the cell's state (backlog → in_production → published → retired). Pick the next topic. | Seed YAML (style guide, axes, whitelist) is loaded into a `topic` table. Selection is a SQL query. In M1 the operator picks; in M2 a scored ranking does. | M1 |
| **Safety filter** | Reject blacklisted themes (medication, diagnosis questions, ABA, "is my child autistic?") **at three points**: topic creation, generated script, generated claims. | A deterministic keyword/regex list plus an LLM classifier flag. Deterministic hits are a hard reject. | M1 |
| **Retrieval** | Find candidate sources for a topic, fetch them, freeze an immutable snapshot, split into sentences, tag the source tier. | PubMed E-utilities / Europe PMC REST (search + abstracts + OA full text), AWMF guideline PDFs added by hand, operator-added URLs/PDFs. | M1 |
| **Source store** | `source` (identity: PMID/DOI/AWMF register number), `source_snapshot` (content hash, retrieved_at, access type), `source_sentence` (ordinal, section, text). | SQLite rows plus raw files under `artifacts/sources/<sha256>`. | M1 |
| **Script generator** | Draft a 60–75 s script (hook + body + hedge + CTA) for the topic in the chosen language, citing only the snapshot's sentences. | Claude Messages API with Citations enabled on custom-content documents (one block = one `source_sentence`). The output is text interleaved with citations, and it is persisted as `script_version` plus provisional claim links. | M1 |
| **Claim extractor** | Segment the script into atomic, checkable claims with character spans. Classify each one (empirical / hedged generalization / advice / non-factual framing). | A separate Claude call using structured outputs (a JSON schema), which works because Citations are off for this call. | M1 |
| **Adversarial fact-checker** | For each claim, independently judge whether the linked sentences *entail* it (supports / partial / unsupported / contradicts / overstated-hedge). Flag claims with no link at all. | A separate Claude call with a *different* prompt persona ("find what's wrong") and no access to the generator's reasoning. It sees only the claim plus the candidate sentences, by ID. Structured output. | M1 |
| **Review gate** | Present claim ↔ sentence pairs, verdicts and the script. Record the human decision bound to the script hash. Block advancement unless the decision is `approved`. | M1: a generated Markdown/HTML review sheet plus a `review approve <script_hash>` CLI command. M2: a Telegram card writing the same rows. | M1 (channel swap in M2) |
| **Source-list renderer** | Produce the caption / pinned-comment source list **only from approved claim_evidence links** (deduped, formatted per platform length limits). | A pure function over the DB, with no LLM involved. | M1 |
| **Publication registry** | Map an approved script to its `video` (the produced asset) and `post` rows (platform, URL, posted_at). Carry the format tags (pillar/angle/hook type) denormalized for analysis. | M1: manual entry via the CLI. M2: written by the publish stage. | M1 |
| **Metrics store** | Store time-stamped metric snapshots per post at fixed ages, plus the method of capture (manual / API). | M1: a CLI prompt or CSV import from TikTok Studio. M2: API pulls where available. | M1 |
| **Readout** | Score formats relative to the account's own median (retention/saves/shares). This produces the go/no-go and, in M2, the topic-selection prior. | SQL views plus a small Python report. | M1 |
| **Voice** | Operator recording ingest (M1: offline; M2: upload) or TTS fallback. | M2: file drop / Telegram voice upload; TTS provider. | M2 |
| **Transcript diff gate** | Transcribe the recording and diff it against the approved script. Any material divergence (ad-libs, dropped hedges) sends it back to the fact-check/review loop. | M2: Whisper word timestamps. The same transcript feeds captions. | M2 |
| **Visuals + render** | Remotion composition (captions from word timestamps, b-roll/illustrations, an on-screen source card). | Node/Remotion in its own container with a CPU cap. | M2 |
| **Publisher** | Schedule or upload to the platforms. | A scheduler API (Metricool/Buffer/Blotato). Direct TikTok needs an audited app (see Integration Points). | M2 |

---

## Recommended Project Structure

Python for the pipeline (it matches the operator's existing tooling, and the Anthropic/HTTP/SQLite libraries are
mature). Remotion (Node) arrives only in M2 as a separate container. The STACK research owns the final
library/version choices; this is the layout.

```
nd-content/
├── config/
│   ├── style_guide.md          # voice, hedging rules, hook patterns, banned phrasings
│   ├── matrix.yaml             # axes: pillars, conditions, domains, audiences, angles
│   ├── safety.yaml             # whitelist/blacklist terms + rationale
│   └── source_tiers.yaml       # tier 1 guideline/systematic review … tier 4 excluded
├── prompts/                    # versioned prompt templates (hashed into every run)
│   ├── script_generate.md
│   ├── claim_extract.md
│   └── fact_check_adversarial.md
├── src/ndc/
│   ├── db.py                   # schema + idempotent migrations (single owner of SQL DDL)
│   ├── ids.py                  # content hashing, stable id helpers
│   ├── stages/                 # one module per pipeline stage, same interface
│   │   ├── topics.py           # seed matrix, select, safety-filter topics
│   │   ├── retrieve.py         # search → fetch → snapshot → sentence-split
│   │   ├── script.py           # grounded generation with citations
│   │   ├── claims.py           # claim extraction
│   │   ├── factcheck.py        # adversarial verification
│   │   ├── review.py           # review sheet render + decision recording
│   │   ├── sources_caption.py  # caption/pinned-comment source list
│   │   ├── publish_log.py      # M1 manual post registry
│   │   └── metrics.py          # snapshot entry / CSV import
│   ├── clients/                # thin wrappers: anthropic, pubmed/europepmc, (M2: tts, telegram, scheduler)
│   ├── safety.py               # deterministic blacklist check (shared by 3 stages)
│   ├── readout.py              # format scoring vs own median
│   └── cli.py                  # `ndc topic next`, `ndc run <topic>`, `ndc review …`, `ndc metrics add …`
├── tests/                      # golden fixtures: a frozen snapshot + expected claim links
├── artifacts/                  # gitignored; bind-mounted volume
│   ├── sources/<sha256>.{xml,pdf,txt}
│   ├── llm/<run_id>.json       # full request/response transcript per LLM call
│   └── review/<script_hash>.html
├── render/                     # M2 only: Remotion project (separate container)
├── Dockerfile
└── docker-compose.yml          # mem/cpu limits; no long-running service in M1
```

### Structure Rationale

- **`stages/` with one module per stage and a uniform interface:** this is what makes the M1→M2 handover cheap.
  The M2 scheduler and Telegram bot call the same `run_stage(name, entity_id)` the CLI calls. There is no second
  code path.
- **`config/` and `prompts/` are versioned and hashed into every run:** "why did this script say X?" must be
  answerable months later. A prompt change is a new hash on every downstream artifact.
- **`db.py` is the single schema owner:** one file of idempotent migrations. The sibling project's experience
  shows that schema drift across many writers is the main source of silent bugs.
- **`artifacts/` holds content-addressed files outside the DB:** the DB stays small and fast, and the raw evidence
  (the paper text as fetched, and every LLM transcript) survives for audit.
- **`render/` is isolated:** Node/Chromium/ffmpeg are heavy. Keep them out of the Python image so M1 stays light
  on the shared host.

---

## Data Model

The tables below are the M1 core. Everything marked *(M2)* is additive: new tables or nullable columns, and no
rewrites.

```
topic                       one matrix cell (+ free-text working title)
  id, pillar, condition, domain, audience, angle, language,
  working_title, status{backlog,selected,in_production,published,retired,rejected},
  safety_status{ok,flagged,blocked}, origin{matrix,operator,trend(M2),reddit(M2)},
  priority_score(M2), created_at

source                      identity of a citable work (stable across re-fetches)
  id, kind{guideline,systematic_review,meta_analysis,review,primary,other},
  tier{1..4}, pmid, pmcid, doi, awmf_reg_no, title, authors, year, journal,
  url, language, retracted_flag, added_by{retrieval,operator}

source_snapshot             immutable frozen text of a source at a moment
  id, source_id, content_sha256, retrieved_at, access{abstract,oa_fulltext,pdf_manual},
  artifact_path, parser_version

source_sentence             the unit of citation
  id, snapshot_id, ordinal, section{abstract,results,discussion,recommendation,…},
  text, char_start, char_end
  UNIQUE(snapshot_id, ordinal)

retrieval_run               which sources were considered for a topic, and why
  id, topic_id, query, provider, params_json, result_source_ids_json, created_at

topic_source                the evidence pack chosen for a topic
  topic_id, snapshot_id, selected_by{auto,operator}, rank

script_version              immutable; edits create a new row
  id, topic_id, parent_id(nullable), content_sha256, language, text,
  hook_text, hook_type, est_duration_s, model, prompt_sha256, config_sha256,
  llm_run_id, author{llm,operator_edit}, created_at

claim                       atomic checkable statement inside a script version
  id, script_version_id, ordinal, span_start, span_end, text,
  text_en_gloss (when script language ≠ source language),
  kind{empirical,hedged_generalization,advice,framing}, requires_evidence(bool)

claim_evidence              claim ↔ source sentence link (the core of provenance)
  id, claim_id, source_sentence_id, proposed_by{generator_citation,factcheck,operator},
  relation{supports,partial,unsupported,contradicts,overstated},
  verifier_run_id, verdict_rationale

factcheck_run               one adversarial pass over one script version
  id, script_version_id, model, prompt_sha256, llm_run_id,
  summary{pass,needs_changes,fail}, unsupported_count, created_at

review                      human decision, channel-agnostic
  id, subject_type{topic,script_version,video(M2)}, subject_id, subject_sha256,
  decision{approved,rejected,changes_requested}, reviewer, channel{cli,telegram(M2)},
  notes, per_claim_overrides_json, decided_at

llm_run                     audit of every model call
  id, stage, model, request_sha256, response_artifact_path, input_tokens,
  output_tokens, cost_usd, created_at

video                       the produced asset for an approved script version
  id, script_version_id, approval_review_id, recording_method{operator,tts(M2)},
  audio_path(M2), transcript_path(M2), transcript_diff_status(M2),
  render_path(M2), duration_s, caption_text, source_list_text,
  format_key (= pillar|angle|hook_type, denormalized for analysis), created_at

post                        one platform publication of a video
  id, video_id, platform{tiktok,youtube,instagram}, url, platform_post_id,
  posted_at, posted_by{operator,scheduler(M2)}, ai_label_applied(bool)

metric_snapshot             time series, never overwritten
  id, post_id, captured_at, age_hours, age_bucket{48h,7d,28d},
  views, avg_watch_s, completion_rate, shares, saves, likes, comments,
  follows_gained, capture{manual,api}, raw_json

stage_run                   idempotency + observability ledger
  id, stage, entity_type, entity_id, input_sha256, output_ref, status{ok,failed,skipped},
  error, started_at, finished_at
  UNIQUE(stage, entity_type, entity_id, input_sha256) WHERE status='ok'
```

Design notes:

- **Separate `source` from `source_snapshot`:** a guideline gets updated (the S3 ADHS guideline revision cycle is
  a real case), and an OA full text may appear after the abstract was first fetched. A new snapshot never mutates
  sentences that published claims point to.
- **Claims belong to a `script_version`, not to a topic:** if an edit changes one sentence, only that version's
  claims are re-checked, and the published video keeps pointing at the version it actually used.
- **`claim.requires_evidence`:** framing lines ("Let's talk about this") need no source. Empirical lines without
  any `supports` link block approval. The rule is enforced in code, not left to reviewer discipline.
- **`text_en_gloss`:** if the language decision is German, claims are spoken in German while most evidence is
  English. Store an English gloss so the fact-checker and the reviewer compare like with like, and so
  translation drift ("can" → "does") is visible.
- **`metric_snapshot.age_bucket`:** the go/no-go compares videos posted on different days. Comparing a 7-day-old
  video to a 1-day-old one is meaningless, so each video gets snapshots at fixed ages and the readout compares
  bucket to bucket.

---

## Architectural Patterns

### Pattern 1: Cite-by-ID grounding (Citations API over custom-content documents)

**What:** Pre-split every snapshot into sentences ourselves, and pass each source to Claude as a custom-content
document whose content blocks *are* our sentences. With Citations enabled, Claude's response carries
`content_block_location` citations (document index + block index range), and these map deterministically to
`source_sentence.id`. The model can only cite text we supplied. `cited_text` is returned by the API and does not
count toward output tokens.

**When to use:** the script-generation stage. Every factual sentence must carry at least one citation, and any
generated sentence without a citation is either framing or an unsupported claim to be flagged.

**Trade-offs:** Citations **cannot be combined with structured outputs** (the API returns a 400 error), so the
generator returns prose with interleaved citations, not JSON. That is why claim extraction and fact-checking are
separate calls that *do* use structured outputs and reference sentence IDs as plain fields. Custom-content blocks
are not re-chunked, so our sentence splitter defines the citation granularity. Use a decent splitter that knows
abbreviations ("et al.", "e.g.", "vs.") and test it on real abstracts.

**Example:**
```python
doc = {
  "type": "document",
  "source": {"type": "content",
             "content": [{"type": "text", "text": s.text} for s in sentences]},
  "title": f"[{source.id}] {source.title} ({source.year})",
  "citations": {"enabled": True},
}
# response citation: {"type":"content_block_location","document_index":0,
#                     "start_block_index":4,"end_block_index":6,"cited_text":"..."}
sentence_ids = [sentences[i].id for i in range(c.start_block_index, c.end_block_index)]
```

### Pattern 2: Separated adversarial verifier (generator ≠ judge)

**What:** The fact-checker is a separate call with an adversarial persona. It receives only `{claim, claim_en_gloss,
candidate sentences by ID}` plus a rubric (supports / partial / unsupported / contradicts / overstated-hedge).
It never sees the generator's prompt or reasoning. It may also propose *other* sentences from the topic's evidence
pack that contradict the claim. Its verdicts are written to `claim_evidence.relation`.

**When to use:** always, for every script version that could be approved.

**Trade-offs:** using the same model family for generator and judge shares blind spots. Mitigate with a different
prompt, temperature 0, the explicit "overstated" category (the common failure in health content is not
fabrication but dropped hedges and population over-generalization), and the human gate as the final authority. A
second model family is a possible later addition, not an M1 requirement.

### Pattern 3: Hash-bound approval (review gate)

**What:** A review row stores `subject_sha256`, the hash of the exact script text plus the claim-evidence set
being approved. Downstream stages check: is there an `approved` review whose hash equals the current
`script_version.content_sha256`? An operator edit produces a new version, so the approval no longer matches and
the claims get re-extracted and re-checked. The operator is then asked again, showing only the changed claims.

**When to use:** at every human gate. In M1 that is the script gate. In M2 a second gate is added at the
rendered-video level (`subject_type='video'`), and it re-uses the same mechanics.

**Trade-offs:** strict, and it may mean extra re-check calls after small wording edits. That is the point:
"I only changed a word" is exactly how a hedge disappears.

```python
def can_advance(db, script_version):
    return db.exists("""SELECT 1 FROM review WHERE subject_type='script_version'
        AND subject_id=? AND subject_sha256=? AND decision='approved'""",
        script_version.id, script_version.content_sha256)
```

### Pattern 4: Idempotent stages keyed on input hash

**What:** Every stage has the signature `run(entity_id) -> output_ref`. Before doing any work, it computes
`input_sha256` = hash(upstream artifact hashes + prompt hash + config hash + model id). If a `stage_run` with
status ok exists for that key, it returns the stored output and makes no LLM call. A failure writes
`status='failed'` and the stage can be re-run safely. Stages write their outputs and their `stage_run` row in
one transaction, **after** any network/LLM call has returned (never hold a write transaction across a call).

**When to use:** all stages. In M1 this makes "re-run the pipeline for topic 42" free and safe. In M2 it lets a
scheduler retry anything without duplicate spending or duplicate posts.

**Trade-offs:** you need discipline about what goes into the hash. Under-hashing means stale outputs get reused;
over-hashing just means extra recomputation. Include the model id and the prompt hash, but leave out timestamps.

### Pattern 5: Defense-in-depth safety filter (three checkpoints)

**What:** The same `safety.check(text)` (deterministic blacklist, plus an LLM category flag) runs on (1) topic
creation, (2) the generated script, and (3) each extracted claim. A deterministic hit blocks. An LLM flag goes to
the review sheet with a red banner.

**When to use:** always. The topic filter alone is not enough, because a whitelisted topic ("ADHD and sleep") can
still produce a medication sentence in generation.

### Pattern 6: Channel-agnostic human gate

**What:** Review UIs are views over the same table. M1 renders `artifacts/review/<hash>.html`, which shows the
script with claims highlighted, and for each claim the linked source sentences with their surrounding context
(±1 sentence), the verdict and the source tier. The operator then runs `ndc review approve|reject|changes`. M2
renders a condensed Telegram card (the video, the claims with unsupported/overstated ones on top, and a link to
the full HTML sheet), with buttons that write the same `review` rows.

**Why this layout for a ~10 min/day budget:** sort the claims by risk (contradicts > unsupported > overstated >
partial > supports). Show green claims collapsed. The operator spends their minutes on the 1–3 claims that matter,
not on re-reading 15 fine ones.

---

## Data Flow

### Milestone 1 flow (per video)

```
ndc topic next ──▶ topic(status=selected)  [safety check #1]
      ↓
ndc run <topic>
  retrieve: search PubMed/EuropePMC (+operator-added AWMF PDF)
      → source rows → source_snapshot (sha256, artifact file) → source_sentence rows
      → topic_source (top-N by tier, operator can pin/unpin)
      ↓
  script: Claude + Citations over custom-content docs
      → script_version (hash) + provisional claim_evidence(proposed_by=generator_citation)
      → [safety check #2]
      ↓
  claims: structured extraction → claim rows (+ en gloss)  [safety check #3]
      ↓
  factcheck: adversarial verdicts → claim_evidence.relation, factcheck_run summary
      ↓
  review sheet rendered → artifacts/review/<hash>.html
      ↓
ndc review approve <script_version>   (or edit → new version → loop back to claims)
      ↓
ndc sources <script_version>  → caption/pinned-comment text (from approved links only)
      ↓
[operator records + posts manually]
      ↓
ndc post add <script_version> --platform tiktok --url …   → video + post rows
      ↓
ndc metrics add <post> --age 48h …  (and 7d)  → metric_snapshot rows
      ↓
ndc readout → per-format scores vs own median → go/no-go
```

### Milestone 2 additions (same front half)

```
analytics pull (API where possible) → metric_snapshot
      → readout scores → topic.priority_score (only for winning formats) → auto-select
front half unchanged …  review(script) approved
      → voice (operator upload or TTS) → Whisper transcript → DIFF vs approved script
           ├─ material divergence → new script_version from transcript → claims → factcheck → review
           └─ ok → visuals/captions (word timestamps) → render
      → Telegram card (video + risk-sorted claims + sources) → review(video) approved
      → publisher (scheduler API) → post rows
```

### Key Data Flows

1. **Provenance flow:** source fetch → content-hashed snapshot → numbered sentences → model citations by block
   index → `claim_evidence` rows → verifier verdict → human approval bound to hash → caption source list generated
   from those links. No step uses free-text quotes copied by an LLM, so a citation to a sentence that does not
   exist cannot be produced.
2. **Spoken-vs-approved flow:** in M1 the operator records by hand from the approved script. That is a
   provenance gap (ad-libs are unverified), so M1 relies on an operator attestation checkbox on `video`. M2 closes
   the gap with the transcript diff. This is the most important M2 addition for the core value, and it should not
   be skipped as "just captions".
3. **Feedback flow:** `metric_snapshot` (fixed ages) → format scoring relative to the account median → in M1, a
   human go/no-go; in M2, a prior on topic selection, restricted to matrix cells inside winning formats.
4. **Correction flow (needed even in M1):** if a source turns out to be retracted or wrong, query
   `source → sentences → claim_evidence → claim → script_version → video → post` to list every affected post. This
   query is free because of the model, and it is the "we take corrections seriously" credibility asset.

---

## Build Order (suggested phases)

The order follows dependencies, and each phase leaves something usable.

1. **Ledger foundation:** repo, Docker (no daemon), `db.py` schema for *all* M1 tables, `ids.py` hashing,
   `stage_run` idempotency helper, `llm_run` audit wrapper around the Anthropic client. Everything depends on
   this. Getting stable IDs and immutability right here is what makes M2 additive.
2. **Topic matrix + safety:** `matrix.yaml`/`safety.yaml`/`style_guide.md` → `topic` table, `ndc topic next`, the
   deterministic blacklist. This can run in parallel with the competitor scan (non-code work); the language
   decision fills `topic.language`.
3. **Retrieval + source store:** PubMed/Europe PMC search, snapshotting, the sentence splitter (test it on
   golden abstracts), manual add of AWMF PDFs/URLs, tiering. This must exist before the script stage, because
   grounding needs sentence IDs.
4. **Grounded script generation:** Citations over custom-content docs, mapping citations back to sentence IDs,
   script_version persistence, style-guide prompt. Validate on 5–10 topics before moving on.
5. **Claims + adversarial fact-check + review sheet + caption sources:** claim extraction, the verifier, the HTML
   review sheet, the approve CLI, the hash-bound gate, the source-list renderer. This completes the front half and
   unblocks the first recorded videos.
6. **Publication registry + metrics + readout:** post/video logging, metric snapshot entry or CSV import at
   48h/7d, the format-vs-median readout. It can start before phase 5 is polished, because the first videos need
   logging from day one. Retrofitting metrics later loses the early-age snapshots, which cannot be recovered.
7. *(M2)* **Transcript diff gate** (Whisper) — build this first in M2, because it protects the core value even
   while voice remains manual.
8. *(M2)* **Visuals/captions/render** (Remotion container, CPU-capped).
9. *(M2)* **Telegram approve card** as a second channel on the same `review` table.
10. *(M2)* **Publisher + analytics pulls + feedback into selection**, limited to winning formats.

**Deliberately not built in M1:** no web app, no task queue, no background daemon, no vector DB/embeddings (the
evidence pack per topic is ~3–10 sources, which fit in context, so retrieval is keyword/MeSH search plus operator
curation, not semantic search over a corpus), no multi-model ensemble, no TTS, and no scheduler integration.

---

## Scaling Considerations

The relevant scale is videos per day and operator minutes, not users.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| M1: ~1 video/day, 20–30 total | A CLI plus SQLite and on-demand `docker compose run --rm`. LLM cost is roughly cents per video (a few calls with ~10–40k input tokens). Nothing needs to stay running. |
| M2: 1–3 videos/day automated | One small long-running container (scheduler + Telegram bot) calling the same stages. A Remotion render container with `cpus:`/`mem_limit` started per job. SQLite in WAL mode is plenty. |
| Multi-language / multi-account | A `account`/`channel` dimension on topic/post. Still SQLite. Only consider Postgres if several writers ever run truly concurrently, which is unlikely. |

### Scaling Priorities

1. **First bottleneck: operator review minutes.** Fix it with risk-sorted claims, collapsed green claims, showing
   only changed claims on re-review, and source-tier badges. Do not "fix" it by auto-approving.
2. **Second bottleneck (M2): shared-host CPU during renders/transcription.** Whisper and Remotion/Chromium are
   CPU-heavy, and the polymarkt-watch container on the same box has a 9 GB memory limit and a heavy nightly
   pipeline (~00:15–06:00 UTC). Cap the nd-content containers (`cpus: "2"`, `mem_limit`), run renders outside
   that window, and consider a hosted Whisper API if local transcription contends.

---

## Anti-Patterns

### Anti-Pattern 1: Letting the LLM write the citation text

**What people do:** Ask the model for a script and a list of sources or quotes, then display them.
**Why it's wrong:** quotes get paraphrased, sources get invented or attached to the wrong claim, and none of it is
mechanically checkable. For an anonymous health account this is the fastest way to lose the only moat.
**Do this instead:** cite by sentence ID over our own snapshots (Pattern 1). Generate the displayed source list
from approved links (a pure function).

### Anti-Pattern 2: Mutable scripts and approvals

**What people do:** Store one `script` row, edit it in place, and keep an `approved=1` flag.
**Why it's wrong:** an approval silently covers text that was changed after review. The audit trail cannot say
what was actually approved.
**Do this instead:** immutable `script_version` plus hash-bound `review` (Pattern 3).

### Anti-Pattern 3: Building the M2 machine to validate M1

**What people do:** Build Remotion, TTS and auto-posting first, "since we'll need them anyway".
**Why it's wrong:** it automates formats that haven't been proven, burns the operator's validation weeks on
plumbing, and the TikTok API audit can block the whole thing (unaudited clients can only post private videos).
**Do this instead:** build the front half (phases 1–6), post manually, and automate only the winning formats.

### Anti-Pattern 4: One mega-prompt that writes, checks and approves itself

**What people do:** "Write a script and make sure every claim is supported."
**Why it's wrong:** self-verification within one generation is weak, and you get no per-claim artifacts to review.
**Do this instead:** separate the generator, extractor and adversarial verifier calls, each persisted (Pattern 2).

### Anti-Pattern 5: Overwriting metrics / comparing videos of different age

**What people do:** Keep one row per video with the "current views".
**Why it's wrong:** the go/no-go compares formats, and a video checked after 7 days always beats one checked after
1 day. Overwriting also loses the early-velocity signal.
**Do this instead:** append-only `metric_snapshot` with fixed age buckets, and compare within a bucket.

### Anti-Pattern 6: Semantic-search infrastructure for a tiny evidence set

**What people do:** Stand up embeddings + a vector DB for "RAG".
**Why it's wrong:** each video needs a handful of high-tier sources chosen deliberately (guidelines, systematic
reviews). Similarity search over chunks invites low-tier or out-of-context sentences.
**Do this instead:** structured search (PubMed with MeSH terms + publication-type filters for reviews/guidelines),
tier ranking, operator pinning, and the whole evidence pack in context.

### Anti-Pattern 7: Trusting the topic whitelist alone

**What people do:** Filter topics, then assume scripts are safe.
**Why it's wrong:** generation drifts (sleep → melatonin → medication).
**Do this instead:** run the safety check at topic, script and claim level (Pattern 5).

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Anthropic Messages API** | Generator call with Citations on custom-content docs; extractor/verifier calls with structured outputs. Every call goes through the `llm_run` audit wrapper. | **Citations and structured outputs are mutually exclusive (400 error)**, hence the split calls. `cited_text` is free in output tokens. (HIGH, official docs) |
| **NCBI E-utilities (PubMed)** | esearch (MeSH + `publication type` filters: Systematic Review, Meta-Analysis, Practice Guideline, Review) → efetch abstracts. | 3 req/s without a key, 10 req/s with a free API key. Pass `tool`/`email`. (HIGH, NCBI) |
| **Europe PMC REST** | search + `/{PMCID}/fullTextXML` for open-access full text (results/discussion sentences). | Full text is only available for the OA subset; otherwise fall back to the abstract. (HIGH) |
| **AWMF register (S3 guidelines)** | Manual: the operator downloads the guideline PDF and runs `ndc source add --pdf`. Extract text, split into sentences, keep the page number in `section`. | No public API found (LOW confidence that none exists; not worth automating for a few documents). Check the guideline's validity date, since expired guidelines are a credibility risk. |
| **TikTok** | M1: manual posting; metrics come from TikTok Studio (manual entry or CSV). M2: a scheduler, or the Content Posting API after audit. | Unaudited Content Posting API clients can only post **private** videos (HIGH). The public video object exposes views/likes/comments/shares only, **not saves or retention** (HIGH). So retention/saves stay manual from Studio unless a scheduler/analytics vendor provides them (LOW, verify in STACK). |
| **YouTube Analytics API** | M2 pull of average view percentage/duration, shares. | MEDIUM, from training data. Verify before M2. |
| **Instagram Graph API** | M2 pull of reels insights (reach, saves, shares, avg watch time) for business/creator accounts. | MEDIUM/LOW, from training data. Verify before M2. |
| **Scheduler (Metricool/Buffer/Blotato)** | M2 publish plus possibly analytics. | LOW. Feature/API availability is unverified here, and the choice belongs in STACK/M2 research. |
| **Telegram Bot API** | M2 review channel (inline buttons → `review` rows). | Keep a separate bot from the polymarkt-watch bots. |
| **Whisper (local or API)** | M2 transcript and word timestamps → diff gate + captions. | Local Whisper is CPU-heavy on a shared host. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI / scheduler / Telegram bot ↔ stages | Direct function calls `run_stage(name, entity_id)` | One code path. Front-ends never contain business logic. |
| stage ↔ stage | Only through DB rows + artifact hashes | No in-memory hand-offs, so any stage can be re-run alone. |
| stages ↔ LLM | Through `clients/anthropic.py` (audit + cost + prompt hashing) | No direct SDK calls in stages. |
| gate logic ↔ review channels | `review` table only | Channels write rows; `can_advance()` reads rows. |
| Python pipeline ↔ Remotion (M2) | A JSON render spec file (script text, word timestamps, source card text, asset paths) passed to a separate container | Keeps Node out of the Python image; the spec is an artifact with a hash. |
| nd-content ↔ polymarkt-watch | **None** (separate repo, compose project, DB, bots, volumes) | Share only the host. Set CPU/memory limits on nd-content containers. |

---

## Sources

- Claude Citations, official docs (custom-content documents → `content_block_location` block indices; sentence
  chunking for text/PDF; `cited_text` not billed as output; **incompatible with structured outputs**):
  https://platform.claude.com/docs/en/build-with-claude/citations (HIGH, fetched 2026-10-24)
- TikTok Content Posting API: unaudited clients are restricted to private viewing:
  https://developers.tiktok.com/doc/content-posting-api-get-started (HIGH)
- TikTok API v2 video object (view/like/comment/share counts; no saves/retention fields):
  https://developers.tiktok.com/doc/tiktok-api-v2-video-object (HIGH)
- NCBI E-utilities rate limits (3/s without key, 10/s with key):
  https://ncbiinsights.ncbi.nlm.nih.gov/2018/08/14/release-plan-for-e-utility-api-keys/ ,
  https://www.ncbi.nlm.nih.gov/sites/books/NBK25497/ (HIGH)
- Europe PMC REST API (fullTextXML for the OA subset): https://europepmc.org/RestfulWebService (HIGH)
- Patterns (content-addressed artifacts, idempotent stages, hash-bound approval, claim-level verification): design
  judgment informed by provenance/RAG-evaluation practice and by the sibling polymarkt-watch codebase's operational
  lessons (single schema owner, no write transaction across network calls, append-only ledgers, mechanism-named
  flags). (MEDIUM)

---
*Architecture research for: research-grounded short-form neurodivergence content production*
*Researched: 2026-10-24*
