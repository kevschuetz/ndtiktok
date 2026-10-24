# Phase 1: Market Decision & Content Foundation - Context

**Gathered:** 2026-10-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Delivers: (1) a data-backed German-vs-English language decision from a competitor scan, made against a rule committed before the scan; (2) a fixed hashtag/keyword set and crisis-line set for the chosen language; (3) a SQLite topic matrix of operator-pruned topics, each tagged whitelist/blacklist; (4) a style guide documenting the fixed 60–75s template; (5) a DE+EN terminology checker and a safety filter usable on topic, script and claim text.

Requirements: MKT-01, MKT-02, MKT-03, CONT-01, CONT-02, CONT-03, CONT-04.
Not in this phase: source retrieval, script generation, fact-checking (Phase 2); accounts, crisis playbook, publishing (Phase 3).

</domain>

<decisions>
## Implementation Decisions

### Competitor scan (MKT-01)
- **D-01:** Claude collects the data, the operator spot-checks. A script pulls public profile and video stats (yt-dlp/web); Claude scores source-citing (0–3) from captions and pinned comments; the operator verifies ~5 accounts by hand in the app. Record per-account provenance (scraped vs operator-verified).
- **D-02:** Sample of ~40 accounts per language (ADHS/DACH and ADHD/English), ~80 total.
- **D-03:** Platforms: TikTok + YouTube Shorts (YouTube is the payout path most likely available in Austria). Reels is not scanned.
- **D-04:** Accounts are found by hashtag + search sampling: top accounts under #ADHS/#ADHD, #Autismus/#autism and parent tags (plus the broader-ND tags per D-10), plus accounts named in research (kirmesimkopf, nessadhs, @hey_mamaleben, @verena_eisbrenner, guardianofmind; How to ADHD, Dani Donovan, ADHD Alien, ADHD Dude), spread across size tiers so mid-size accounts are represented.
- **D-05:** Per-account fields follow MKT-01 + research: median views of last 15 posts (never the viral outlier), source-citing score 0–3, face/faceless, voice gender, format, cadence, pillars/audiences covered, saves and shares per 1k views where visible, monetization signals.
- Scraping must be polite (rate-limited) and must not hurt the shared polymarkt-watch host (low concurrency, run outside 00:15–06:00 UTC).

### Language decision rule (MKT-02)
- **D-06:** Primary signal = sourcing gap + reachable audience: choose German if few DACH accounts cite sources at score ≥2 AND mid-size DACH reach is within roughly 5–10× of English mid-size reach. Exact numeric thresholds are written into the committed rule doc before the scan runs (planner proposes; the operator approves the doc).
- **D-07:** Tie-break / inconclusive data → German.
- **D-08:** One language only in milestone 1; no bilingual or parallel accounts. The other language is a milestone-2 option.
- The decision plus its reasoning is logged in validation week 1 (MKT-02); the hashtag set and crisis-line set (MKT-03) follow from the chosen language.

### Topic matrix (CONT-01)
- **D-09:** Starting backlog of ~60–80 topics. Claude drafts candidates across the matrix (pillar × condition × domain × audience × angle), each with a whitelist/blacklist tag and a "source likely exists?" flag; the operator keeps or kills each one.
- **D-10:** Condition scope = broader ND: ADHD, autism, AuDHD plus dyslexia, dyspraxia/DCD, Tourette etc. Note: S3/AWMF guidelines exist for ADHS and Autismus only; other conditions lean on PubMed reviews.
- **D-11:** The backlog is weighted evenly across the 4 pillars (challenge+science+help, strengths, parents, men/dads/partners) because the experiment needs ~6–7 videos per pillar.
- Storage: SQLite; listable and filterable by every dimension via CLI.

### Checker strictness & wording (CONT-03, CONT-04)
- **D-12:** Two tiers. Hard terms block (functioning labels, ABA-adjacent framing, blacklisted subjects: medication, diagnosis questions, ABA, "is my child autistic?"). Soft terms warn and require an override with a recorded reason ("superpower" hype, "leidet an", "Asperger" outside quotes, etc.).
- **D-13:** German autism wording is identity-first. Default to "autistische Menschen" (identity-first and gender-neutral); use "Autist:innen" only where a noun is unavoidable. English is identity-first by default ("autistic people").
- **D-14:** Gendering: neutral constructions where possible ("Menschen mit ADHS", "Eltern"); avoid gender colons in spoken text except the D-13 noun case.
- **D-15:** The terminology list is a versioned file in the repo, drafted by Claude from research and approved by the operator; later changes go through review.
- The safety filter applies at topic level in this phase and exposes the same check for script and claim text (consumed by Phase 2).

### Style guide (CONT-02)
- Already locked by project decisions: fixed 60–75s template, hook in the first 1–2s spoken + on screen, one topic per video, hedged non-diagnostic tone, calm visuals (no strobe or rapid cuts), accurate burned-in captions, sources in caption/pinned comment.

### Amendments after phase research (operator, 2026-10-24)
- **D-16:** Research found TikTok hashtag pages, comments and subtitles are not scrapable without login, and bot-check workarounds (e.g. curl_cffi impersonation, paid scraping services like Apify) are NOT allowed. Account discovery is automated instead via TikTok Creative Center (official; top creators/hashtags by country AT/DE/US) and/or a creator-search database free tier (Exolyt/Favikon/Modash), plus research-named seeds and YouTube search (`ytsearch`). Operator only confirms/edits the candidate list. Verify each discovery source live in the plan; if all fail, fall back to operator handle collection (~30–45 min).
- **D-17:** The face/voice/format walkthrough and the spoken/on-screen citation check are automated: yt-dlp downloads ~3 recent videos per account (verify no-login download works first); faster-whisper transcribes them (catches spoken citations); Claude vision on sampled frames judges face vs faceless, format and on-screen citations; voice gender is a pitch-based estimate labelled as such. Every field keeps per-field provenance (auto vs operator) and a confidence. The operator spot-checks only uncertain or decision-relevant accounts (~10–15 min). Replaces the ~5-account spot-check in D-01 and the manual walkthrough. Needs an Anthropic API key (env var; model IDs in config). Heavy CPU work (Whisper) runs low-priority outside 00:15–06:00 UTC.
- **D-18:** Reach ratio Q uses TikTok only; YouTube Shorts metrics are reported alongside, not blended.
- **D-19:** Topic drafts are a Claude-written, reviewed seed file in the repo (`config/topic_seed.yaml`) plus an import command — no runtime API call for drafting.
- **D-20:** The research-proposed decision-rule thresholds are accepted as the draft: mid tier = 10k–100k followers; Q = EN ÷ DE median of mid-tier accounts' median views (TikTok); N_DE = DE accounts scoring ≥2; fewer than 8 usable mid-tier accounts in either language → inconclusive → German; German if N_DE ≤ 4 and Q ≤ 10; English if Q > 15; English if N_DE ≥ 8 and the DE sourced+faceless+male slot is filled while the EN one is empty; else → German. The operator formally approves and commits the rule doc before any scan data is pulled; the scan records the rule hash and `decide` refuses a changed rule without a logged amendment.
- **D-21:** No Anthropic API calls in Phase 1 (operator, 2026-10-24, cost). The LLM steps — caption source-citing scoring (structured, substring-verified evidence) and frame analysis (face/faceless, format, on-screen citations) — are performed in-session by the Claude Code executor (subscription), which reads the downloaded captions/frames/transcripts from disk and writes its judgments into SQLite through an `ndc` import command with provenance `llm_session`. Code must still define the rubric, the JSON/import schema and the substring check, so the step is reproducible by hand. `ANTHROPIC_API_KEY` exists in `/home/nd-content/.env` (gitignored, chmod 600) but is only used from Phase 2 on. Supersedes the "Needs an Anthropic API key" part of D-17.
- Known tension (not reopened): AFK 2023 guidance says German identity-first is unsettled and suggests "Person im Autismus-Spektrum"; D-13 stands.

### Claude's Discretion
- CLI shape, SQLite schema details, and file layout (keep it minimal: Python + uv + Typer + sqlite-utils per research STACK.md).
- Scraping tooling choice and exact sampling procedure within D-01–D-05.
- Exact threshold numbers in the decision-rule draft (operator approves before the scan).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project
- `.planning/PROJECT.md` — scope, core value, key decisions
- `.planning/REQUIREMENTS.md` — MKT-01..03, CONT-01..04
- `.planning/ROADMAP.md` §Phase 1 — goal and success criteria
- `PROJECT-BRIEF.md` — original operator brief (pillars, tone, whitelist)

### Research
- `.planning/research/SUMMARY.md` — synthesis and challenges
- `.planning/research/FEATURES.md` — competitor-scan spec, example accounts, decision-rule draft, anti-features
- `.planning/research/PITFALLS.md` — ND community language pitfalls, terminology guidance, platform keyword risks
- `.planning/research/STACK.md` — Python/uv/Typer/sqlite-utils/yt-dlp versions
- `.planning/research/ARCHITECTURE.md` — data model (topics table, safety filter at three levels)
- `.planning/phases/01-market-decision-content-foundation/01-RESEARCH.md` — phase research: live-tested scan feasibility, rubric, thresholds, matcher, crisis lines, skeleton

</canonical_refs>

<code_context>
## Existing Code Insights

Greenfield: no code exists yet in /home/nd-content. This phase establishes the Python project skeleton (uv, Typer CLI, SQLite) that later phases extend. Runs on the shared polymarkt-watch host: separate repo and separate Docker/volume; keep resource use low.

</code_context>

<specifics>
## Specific Ideas

- Research-named accounts (see D-04) must be included in the scan sample.
- Research found no sourced, male, faceless German account (LOW confidence); the scan should confirm or refute that explicitly.

</specifics>

<deferred>
## Deferred Ideas

- Scanning Instagram Reels — not in milestone 1 (Reels are cross-posts only).
- A second-language account — milestone 2 option (D-08).

</deferred>
