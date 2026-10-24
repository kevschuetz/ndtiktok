# Project Research Summary

**Project:** nd-content — faceless neurodivergence short-form account
**Domain:** Research-grounded health/neurodivergence content production (short-form video), human-gated pipeline, milestone 1 = validation + light tooling
**Researched:** 2026-10-24
**Confidence:** MEDIUM-HIGH. Core API/library facts (Anthropic SDK, Citations, PubMed/E-utilities, TikTok API constraints, EU AI Act dates) are HIGH and verified live on 2026-10-24. Platform-growth/monetization mechanics, Austrian legal specifics and community-norm claims are MEDIUM, and are flagged inline in each doc.

## Executive Summary

This is a research-grounded, faceless health-education short-form video account in a niche with a documented **quality–engagement inversion**: the most-viewed ADHD/autism TikTok content is 50%+ misleading, and the rare evidence-based/clinician content gets a tiny fraction of the engagement (4% of likes in one DGPPN-cited study). The expert pattern for winning here is not "be more rigorous than the feed" — it's **pairing a relatable, hook-driven format with visible, mechanically-verifiable sourcing**, something almost nobody in the niche currently does. The credibility moat (every claim traces to a retrieved source sentence, shown to the viewer) is real and valuable, but it is a fragile asset: a single instance of an overstated claim sitting next to a real citation is reputationally worse than having no sources at all, because it reads as deliberate misrepresentation rather than an honest gap.

The recommended approach is a two-pass, two-model architecture built around Claude's Citations API (sentence-level, ID-based grounding, never free-text quotes) separated from a structurally independent adversarial fact-check pass using structured outputs — the two features cannot be combined in a single API call, which conveniently forces the right separation of concerns (generator ≠ judge). Everything is content-hashed and immutable (sources, script versions, approvals) so that months later any published claim can be traced back to its exact source sentence, and any correction can be propagated. Milestone 1 deliberately stays CLI + SQLite + flat files, with manual recording, manual posting and manual metrics entry — no web app, no vector DB, no automation pipeline — because the automation (Remotion render, TTS, scheduler, Telegram approval) should only be built for the formats milestone 1 proves actually win, and because several of the biggest risks (claim drift at the recording/caption stage, platform suppression, legal disclosure timing) are structural and have to be solved before any volume is produced, not fixed by scaling production faster.

The most consequential risks, in order, are: (1) **fact-checking the wrong artifact** — verifying the draft script instead of the actual recorded transcript/on-screen text/caption, which is where hedges get silently dropped during recording and editing; (2) **assuming current monetization/format assumptions hold in Austria** — Creator Rewards likely excludes Austria entirely, which undercuts part of the stated rationale for the 60–75s length target and means the monetization plan should not lean on TikTok payouts at all; (3) **treating the legal disclosure (MedienG §25) as a monetization-gated item** when it is actually required from the first regularly-published post, independent of money; (4) **over-reading a 20–30 video validation experiment** — the design can only support comparing about 4–6 cells with any statistical honesty, so the readout rule must be pre-registered before video 1; and (5) **citation hallucination/misattribution**, which requires mechanical DOI/PMID verification (Crossref/PubMed), not LLM self-verification. All five are M1-phase, pre-first-post concerns, not later cleanup.

## Key Findings

### Recommended Stack

M1 is deliberately small: Python 3.13 + uv, the Anthropic SDK (2.3.x — a 2.x major, `messages.parse`/`output_config.format`, not 0.x-era patterns), Pydantic 2.14, SQLite via stdlib + sqlite-utils, Typer for the CLI, httpx for PubMed/Europe PMC. The single most load-bearing stack fact: **Citations and structured outputs cannot be used in the same API call** (400 error) — this forces a two-pass design (draft with citations ON / verify with structured outputs ON, no citations) that happens to be good practice anyway (generator ≠ judge). AWMF (the German S3 guideline source) has no API and is behind a bot-stopper; guideline PDFs must be downloaded by hand, with the guideline's version/validity date recorded, because the ADHS S3 guideline (028-045) is itself mid-revision. M2 (deferred, automation-only, built only for winning formats) adds Remotion for render, faster-whisper for word-timestamp captions and a transcript-diff gate, and Buffer/Blotato or TikTok's unaudited "upload to inbox" draft flow for publishing (a fully-audited direct-post integration is a multi-week undertaking, not a default assumption).

**Core technologies:**
- Anthropic SDK (`anthropic` 2.3.x) + Citations API over custom-content documents: grounded, sentence-ID-level draft generation — why: the only way to make "citation" mean "really in the source" instead of "plausible-sounding"
- Pydantic 2.14 + `messages.parse(output_format=...)`: structured claim extraction and adversarial verification — why: schema-valid, reviewable claim↔source-sentence pairs, incompatible with citations in the same call
- SQLite (stdlib) + sqlite-utils 4.2: single-file ledger for sources, claims, approvals, metrics — why: zero ops, trivially backed up, right-sized for 20–30 videos and a handful of writers
- PubMed E-utilities + Europe PMC REST: primary biomedical retrieval, MeSH/publication-type filtered (systematic reviews, meta-analyses, guidelines) — why: authoritative, free, rate-limited but generous with a free NCBI key
- **Model-ID discrepancy to resolve before building:** the project brief's model references are stale relative to the current lineup (`claude-opus-5-5`/`claude-sonnet-5-5`/`claude-haiku-5-5`, verified live 2026-10-24); `claude-sonnet-5`/`claude-haiku-4-5-20251001` are legacy. **Model IDs must live in config, not hard-coded**, both to avoid this drift recurring and because the draft/verify split benefits from being able to swap models independently (research recommends a *different* model for the verify pass than the draft pass, to reduce shared-blind-spot risk).

### Expected Features

The niche's quality–engagement inversion is the dominant fact: evidence-based content structurally underperforms on raw engagement, so the differentiator is combining the two halves (hook energy + visible sourcing) rather than picking one. There is also a concrete, evidenced gap: sourced, faceless, **male**-voice content aimed at men/dads/partners is essentially absent in both German and English markets — this validates Pillar 4 as a real structural opportunity, not just an "early bet."

**Must have (table stakes):**
- Hook in the first 1–2 seconds, spoken AND as on-screen text (TikTok tests a small cohort first; a weak hook plateaus reach)
- Burned-in, accurate, styled captions — not optional for this audience; many watch muted and ND viewers use captions as redundant processing support
- Hedged, non-diagnostic language with a "not a therapist" framing, visible in bio
- Visible sources on every video — on-screen citation card + full list in the pinned comment (pinned comment beats caption: captions truncate and compete with hashtags)
- A deterministic, three-checkpoint safety filter (topic / script / claim) against the blacklist (medication, diagnosis, ABA, "is my child autistic?")

**Should have (competitive differentiators):**
- "Paper-on-screen" b-roll (a highlighted guideline/abstract sentence) — a faceless-friendly way to literally show the receipt
- The underserved "this is human, not ADHD-specific, but here's the research nuance" framing — directly counters the documented transdiagnostic-symptom misattribution pattern
- Named, recurring series ("Mythos oder Studie?") for retention and profile-visit conversion
- Male-voice men/dads/partners pillar run as its own measured arm, not folded into general content

**Defer (v2+ / M2):**
- Automated captions (Whisper), Remotion render templates, scheduler publishing — build only for the pillar(s)/formats that win the M1 readout
- Email list / lead magnet, sponsorships, affiliate monetization — gated on traction *and* the legal/tax checklist
- Stitching other creators ("myth or study" with a paraphrase is the safer early substitute)

### Architecture Approach

Treat the system as an evidence ledger, not a video factory: every spoken sentence traces through `claim → claim_evidence → source_sentence → source_snapshot (immutable, hashed) → source`. Three structural decisions make M2 a pure addition rather than a rebuild: sentence-level source storage with stable IDs (so Claude's Citations map 1:1 onto DB rows, never free-text quotes); content-addressed immutable artifacts (a script edit creates a new version, which automatically voids any prior approval bound to the old hash); and one channel-agnostic `review` table (M1's CLI approval and M2's eventual Telegram card write identical rows, so the gate logic never has to know which UI produced the decision).

**Major components:**
1. **Retrieval + source store** — PubMed/Europe PMC search plus manually-added AWMF PDFs, frozen into content-hashed snapshots, split into numbered sentences before anything else touches them
2. **Script generator (grounded, cite-by-ID)** — Claude + Citations over custom-content documents built from those sentences; output is prose with citations, never JSON (API-incompatible with structured outputs)
3. **Claim extractor + adversarial fact-checker** — two separate structured-output calls; the fact-checker is deliberately adversarial, sees only claim + candidate sentences by ID, and classifies supports/partial/unsupported/contradicts/**overstated** (the dropped-hedge failure mode)
4. **Review gate (hash-bound, human)** — a review row binds to the exact script-version hash; any edit after review voids the approval and forces re-check
5. **Source-list renderer, publication registry, metrics store, readout** — pure functions / manual-entry tables that turn approved claim_evidence links into the pinned-comment citation list and, later, the format-vs-median go/no-go

### Critical Pitfalls

1. **Claim drift after fact-checking** — hooks get "punched up," hedges get cut, ad-libs aren't in the checked script. Fix: fact-check must run on the **final recorded transcript + on-screen text + caption + hook**, never the draft; no re-edit without a re-check.
2. **Hallucinated or misattributed citations** — a second LLM pass tends to agree with the first's fabrication. Fix: retrieval-first closed-book drafting, plus **mechanical DOI/PMID resolution against Crossref/PubMed** (title/author/year match), never LLM-only "verification."
3. **Platform suppression is often silent** — misinformation/self-harm-adjacency classifiers can tank reach with no strike. Fix: log a per-video FYF/eligibility field in the metrics log, or the validation readout will confuse "bad format" with "suppressed video."
4. **Validation noise at 20–30 videos** — new-account distribution is highly variable; raw views are nearly meaningless at this sample size. Fix: pre-register the readout rule before video 1, use rate metrics (saves/shares/follows per 1k views, completion %) relative to the account's own running median, and accept that only ~4–6 cells can be honestly compared.
5. **Austrian legal disclosure timing** — MedienG §25 applies from the first regularly-published post, not from the first euro of revenue; the broader monetization-gated checklist (ECG §5, trade/tax registration, ad labeling) is correctly gated on monetization, but §25 is not.

## Implications for Roadmap

Based on research, suggested phase structure (all milestone 1):

### Phase 1: Ledger foundation + topic matrix + safety
**Rationale:** Everything downstream depends on stable IDs, immutable versioning, and the three-checkpoint safety filter; this is also where the Austrian §25 disclosure decision belongs (pre-launch, not pre-monetization) and where the competitor scan (language decision) can run in parallel since it's non-code work.
**Delivers:** `db.py` schema for all M1 tables, content-hashing helpers, `stage_run` idempotency, the deterministic blacklist, the topic matrix seeded from `matrix.yaml`/`safety.yaml`, the bio/Impressum disclosure live.
**Addresses:** table-stakes safety/legal features from FEATURES.md (bio disclosure, whitelist/blacklist); avoids Pitfall 9 (legal timing) and Pitfall 7 (don't architect around Creator Rewards assumptions).

### Phase 2: Competitor scan + language decision
**Rationale:** Blocks the source corpus, hashtag scheme and crisis-line choice; FEATURES.md gives a pre-registerable decision rule and a concrete sampling methodology. Can run concurrently with Phase 1's code work.
**Delivers:** a logged competitor spreadsheet, a data-backed German-vs-English decision with the reasoning recorded, the terminology table (DE/EN, Pitfall 5) drafted alongside it.
**Uses:** no stack dependency; feeds `topic.language` in the Phase 1 schema.

### Phase 3: Retrieval + source store
**Rationale:** Grounding needs sentence IDs to exist before any script can be generated; this must precede Phase 4.
**Delivers:** PubMed/Europe PMC search + snapshot + sentence-split pipeline, manual AWMF PDF ingestion path, source tiering.
**Implements:** the `source` / `source_snapshot` / `source_sentence` architecture component; avoids Pitfall 2's citation-hallucination risk at its root by making "cite by ID" structurally impossible to fake.

### Phase 4: Grounded script generation
**Rationale:** The riskiest new integration (Citations API over custom-content docs); validate on 5–10 topics before building the next stage on top of it.
**Delivers:** script_version persistence, the style-guide prompt (hedge vocabulary, terminology lint), citation→sentence-ID mapping.
**Uses:** `anthropic` 2.3.x Citations; implements Architectural Pattern 1 (cite-by-ID grounding).

### Phase 5: Claims + adversarial fact-check + review gate + source-list renderer
**Rationale:** Completes the front half; unblocks the first recorded, published video. The hash-bound approval (Pattern 3) and the mandatory "fact-check the final transcript, not the draft" rule (Pitfall 1) both land here.
**Delivers:** claim extraction, the adversarial verifier (different persona/temperature-0, ideally a different model than the drafter), the risk-sorted HTML review sheet, the `ndc review approve` CLI, the pinned-comment/caption source-list renderer.
**Addresses:** the core-value features (visible sources, claim↔sentence pairs) from FEATURES.md; avoids Pitfalls 1 and 2 directly.

### Phase 6: Publication registry + metrics log + pre-registered readout
**Rationale:** Should start logging from the very first video — retrofitting metrics later loses early-age snapshots permanently. The go/no-go rule (comparison metric, minimum videos per cell, exclusion criteria) must be written and committed *before* video 1 posts, per Pitfall 6.
**Delivers:** manual post/video logging, fixed-horizon (24h/72h/7d) metric snapshots including an FYF-eligibility field, the Latin-square pillar rotation, the pre-registered readout rule, and the crisis-comment playbook (Pitfall 10) in place before any posting begins.
**Avoids:** Pitfall 6 (validation noise) and Pitfall 3 (confusing suppression with format quality).

### Phase Ordering Rationale

- Retrieval must exist before generation (sentence IDs are the citation unit); generation must exist before extraction/fact-check; fact-check must exist before the review gate can have anything to show.
- The competitor scan and the ledger/safety foundation are independent and can run in parallel — neither blocks the other, and both block Phase 3+.
- Metrics logging is deliberately pulled forward to "start day one," not placed at the end of the build order, because the cost of missing early-age data is unrecoverable, unlike almost everything else in this stack.
- M2 (automation) is explicitly out of this phase structure — ARCHITECTURE.md's Anti-Pattern 3 ("building the M2 machine to validate M1") is a named risk, and the build order research puts the M2 transcript-diff gate first *within* M2 specifically because it protects the core value even before voice/render/publish are automated.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (competitor scan):** sparse, point-in-time data (follower counts, source-citing rates) that must be re-verified live at scan time, not trusted from this research pass.
- **Phase 4 (grounded script generation):** first real integration against Citations + custom-content documents; PyMuPDF 2.0 is a brand-new major version (5 days old at research time) and needs a smoke test against a real AWMF PDF before being trusted.
- **Phase 6 (readout design):** the statistical design (Latin-square rotation, minimum-exposure filters, rate-metric choice) is prescriptive in FEATURES.md but should be sanity-checked against the actual competitor-scan findings and against whichever language is chosen (DACH has a smaller/noisier reach distribution).

Phases with standard patterns (skip research-phase):
- **Phase 1 (ledger foundation):** standard SQLite-ledger + content-hashing patterns, well-covered by ARCHITECTURE.md with working code examples.
- **Phase 3 (retrieval):** PubMed E-utilities and Europe PMC are stable, well-documented REST APIs with verified rate limits.
- **Phase 5 (fact-check + review gate):** the two-pass pattern and hash-bound approval are fully specified in ARCHITECTURE.md with example code; the main residual risk is prompt-engineering quality, not architecture.

## Challenges to PROJECT.md — read before roadmap/requirements lock-in

Research surfaced several points where PROJECT.md's current framing should be revisited, not silently inherited:

1. **MedienG §25 disclosure is very likely needed from the first regularly-published post, not gated behind monetization.** PROJECT.md currently lists the "Austrian legal/tax checklist" as a single Active item with no internal sequencing. PITFALLS.md recommends explicitly splitting it into a **pre-launch** item (§25 bio disclosure) and a **pre-monetization** bundle (ECG §5, trade/tax registration, ad-labeling rules). This should be reflected as two separate requirements, not one.
2. **TikTok Creator Rewards is likely unavailable to an Austria-resident creator** (third-party 2026 country lists exclude Austria; official terms say "selected countries" without enumerating them — confidence LOW–MEDIUM on the exclusion itself, but consistent across sources). This matters twice: it weakens part of the stated rationale for the 60–75s length choice (the ">1 minute" threshold is a Creator Rewards requirement that may not apply to this account at all), and it means the monetization plan should be built around own products/sponsorships/affiliates and YouTube's revenue share (which **is** available in Austria), not around TikTok platform payouts. Recommend verifying Creator Rewards eligibility in-app early and explicitly decoupling the length decision from a monetization mechanism that may not exist for this account.
3. **The 20–30 video validation design can only support ~4–6 comparable cells, and the readout must be pre-registered before video 1.** PROJECT.md's requirement list currently states the validation plan (20–30 videos, go/no-go readout) without specifying the comparison design. Research is explicit that pillar should be the one held-constant-elsewhere primary variable, hook should be tested as a secondary/later phase, and the comparison rule, minimum-per-cell count, and exclusion criteria need to be written down and committed *before* posting starts — otherwise the go/no-go risks being post-hoc storytelling on noisy new-account data.
4. **Fact-check scope must be the final recorded artifact (transcript + on-screen text + caption + hook), not the draft script.** This is implicit in PROJECT.md's requirement ("adversarial fact-check pass") but not stated as a scope rule. Given that claim drift during recording/editing is the single most dangerous failure mode identified (Pitfall 1), this should be made an explicit requirement, with mechanical citation ID verification (Crossref/PubMed resolve) as a second explicit requirement rather than folded implicitly into "fact-check."
5. **Posting cadence: research recommends 4–5/week batched production, not ~1/day.** PROJECT.md's constraint section implies roughly daily posting ("~1/day at a 30–60 min/day operator budget"). PITFALLS.md finds the realistic per-video cost (research + fact-check review + recording + editing + posting + comment moderation + metrics logging) is closer to 60–120 minutes for a sourced health video, and recommends batching research/scripting and recording in sessions, then posting 4–5×/week via TikTok's native scheduler — validation needs 20–30 *comparable* videos, not 30 consecutive calendar days. This should be reconciled explicitly rather than left as an implicit daily-cadence assumption that risks stalling the validation (Pitfall 11).
6. **Model-ID discrepancy.** The project brief's model references predate the current Claude lineup (verified live 2026-10-24: `claude-opus-5-5`/`claude-sonnet-5-5`/`claude-haiku-5-5`). Recommend making model IDs a config value from day one (not hard-coded anywhere), both to fix this immediately and to prevent the same drift recurring as new model generations ship.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Anthropic SDK, Citations/structured-outputs incompatibility, PubMed/Europe PMC rate limits, and every package version were verified live against official docs/PyPI/npm on 2026-10-24. Platform scheduler/analytics API coverage (Buffer, Metricool, Instagram Graph insights) is MEDIUM — vendor-blog sourced, not independently tested. |
| Features | MEDIUM | The quality–engagement-inversion studies are peer-reviewed and HIGH confidence. Platform-mechanics claims (hook-retention windows, link-in-bio follower thresholds, watermark deprioritization) are MEDIUM/LOW and training-data- or marketing-blog-sourced; named competitor follower counts are point-in-time snapshots that must be re-verified during the actual competitor scan. |
| Architecture | MEDIUM-HIGH | The structural patterns (content-addressed ledger, cite-by-ID, hash-bound approval, separated adversarial verifier) are firm design judgment with working code examples and are internally consistent with the verified Citations API behavior. The specific vendor facts cited (TikTok API object fields, NCBI rate limits) are independently HIGH. |
| Pitfalls | MEDIUM | Platform API constraints (TikTok audit/SELF_ONLY, YouTube's July 2025 inauthentic-content policy, EU AI Act Art. 50 date) are HIGH. Austrian legal specifics (Impressum mechanics, regulated-trade boundaries) and community-language norms are MEDIUM and explicitly flagged as "not legal advice — confirm with WKO/Steuerberater." The exact Creator Rewards country exclusion for Austria is LOW–MEDIUM (no official enumerated list found; consistent third-party claims only). |

**Overall confidence:** MEDIUM-HIGH. The technical/API facts that gate architecture decisions are solid. The platform-growth, monetization-eligibility and Austrian-legal specifics are directional and should be spot-verified (in-app Creator Rewards check, a short WKO consultation) before they're treated as settled inputs to planning.

### Gaps to Address

- **TikTok Creator Rewards eligibility for Austria:** not independently confirmable from available sources (no official country list). Verify in-app (Creator tools → Creator Rewards) during Phase 1/2 and update the monetization narrative in PROJECT.md accordingly rather than assuming eligibility.
- **AWMF S3 ADHS guideline (028-045) version status:** mid-revision as of this research; the operator must manually confirm the currently valid version/date before Phase 3 source ingestion and record it in the `source` table.
- **Exact competitor source-citing landscape:** this research's examples are a non-exhaustive, point-in-time sample. The Phase 2 competitor scan is the authoritative pass and should not simply inherit the illustrative examples listed in FEATURES.md.
- **Austrian legal mechanics (ECG §5 address requirements, Lebens- und Sozialberatung trade boundary, Kleinunternehmer threshold):** sourced from WKO/legal-blog summaries, not primary statute reading. Treat the legal checklist as a draft to validate with WKO/a Steuerberater before monetization, and get §25 confirmed before the first post regardless.
- **Platform scheduler API capability (Buffer vs. Blotato vs. TikTok inbox-draft) for M2 publishing:** MEDIUM/LOW confidence; this is explicitly deferred to M2 and should get a fresh, narrow research pass once M1's winning format is known (so the publishing requirements — e.g. whether AI-label flags are needed — are concrete rather than speculative).

## Sources

### Primary (HIGH confidence)
- platform.claude.com/docs/en/models/overview — current model IDs, pricing, legacy list (fetched 2026-10-24)
- platform.claude.com/docs/en/build-with-claude/citations — custom-content documents, sentence chunking, citations/structured-outputs incompatibility
- platform.claude.com/docs/en/build-with-claude/structured-outputs — `messages.parse`, `output_config.format`
- NCBI E-utilities rate limits and PubMed/Europe PMC REST documentation
- TikTok Content Posting API / Content Sharing Guidelines (developer docs) — unaudited-client SELF_ONLY restriction
- TikTok API v2 video object — confirms no saves/retention fields exposed
- YouTube "inauthentic content" YPP policy (15 Jul 2025); EU AI Act Art. 50 transparency obligations (2 Aug 2026)
- Yeung et al. 2022 (PMC) and Karasavva et al. 2025 (PLOS ONE) — peer-reviewed TikTok ADHD content-quality studies

### Secondary (MEDIUM confidence)
- PyPI/npm registry version checks (2026-10-24) for all M1/M2 package versions
- WKO Impressum/Offenlegung guidance; Austrian legal-blog summaries of MedienG §25 / ECG §5
- Buffer/Metricool/Blotato vendor pricing and API-capability pages
- German-language TikTok ADHS content analysis (177-video study); DGPPN 2024 (Philipsen) engagement-vs-evidence finding
- Named competitor account characteristics (kirmesimkopf, ADHD Alien, Dani Donovan, ADHD Dude, etc.) — point-in-time, to be re-verified in Phase 2

### Tertiary (LOW confidence)
- Third-party TikTok Creator Rewards country-eligibility lists (no official enumerated source found) — Austria's exclusion needs in-app verification
- Retention/length benchmark figures (vendor blogs: Retensis, OpusClip) — directional only
- TikTok link-in-bio follower-threshold claims — training-data sourced, unverified against current TikTok policy

---
*Research completed: 2026-10-24*
*Ready for roadmap: yes*
