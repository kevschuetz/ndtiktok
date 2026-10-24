# Phase 1: Market Decision & Content Foundation - Research

**Researched:** 2026-10-24
**Domain:** Competitor-scan data collection (TikTok/YouTube public metadata), pre-registered decision rule, SQLite topic matrix, DE+EN terminology linting with German morphology, deterministic safety filter, Python CLI skeleton
**Confidence:** HIGH for scan feasibility (probed live today with yt-dlp 2026.10.21), crisis lines (official AT/DE/CH sources) and package versions (PyPI). MEDIUM for terminology norms (one authoritative German source, AFK 2023, plus community material). LOW and flagged where marked.

## Summary

The competitor scan is **feasible with yt-dlp and no login**, but only for some fields. A live probe today showed that `yt-dlp --flat-playlist -J https://www.tiktok.com/@<handle>` returns, per post, `view_count`, `like_count`, `comment_count`, `repost_count` (shares), **`save_count`**, `description`, `timestamp` and `duration`, newest first, in one request. Follower counts are not in yt-dlp output. They are in the public profile page's `__UNIVERSAL_DATA_FOR_REHYDRATION__` JSON, which a plain GET returns (`userInfo.stats.followerCount`, `videoCount`, plus bio and `bioLink`). YouTube works fully: the `/@channel/shorts` flat listing gives subscriber count plus per-Short views, and a per-video `--skip-download -J` gives description, likes, comments and upload date. `ytsearch30:"ADHS #shorts"` discovers YouTube channels without an API key.

Three things **do not work** and need an operator fallback:
- **TikTok hashtag pages.** `tiktok:tag` is marked "CURRENTLY BROKEN" in yt-dlp, and the tag page HTML has no hydrated challenge data.
- **TikTok comments, including pinned comments.** They came back empty.
- **TikTok captions/subtitles.** Absent in all 20 posts probed, so spoken or on-screen source citations are invisible to scraping.

**Bot-check circumvention (curl_cffi browser impersonation) is off-limits.** It was refused by this environment's safety policy during research, and it should not appear in any plan.

So TikTok account *discovery* is an operator-in-app step (~30–45 min of noting handles), plus research-named seeds and YouTube search. Fields that need eyes or ears (face/faceless, voice gender, format, on-screen citation) come from an operator walkthrough CLI, with provenance recorded.

For the checker, German inflection is solved cheaply. **simplemma 2.0.0** (pure Python, MIT, ~19 MB of dictionaries) lemmatized `leidet / litt / gelitten / leidest → leiden`, `geheilt → heilen`, `Medikamente → Medikament`, `Autisten → Autist` correctly in a live test. It does **not** split compounds or normalize adjectives (`hochfunktionalen`, `Superkräfte` and `Asperger-Syndrom` stay unchanged). The matcher should therefore be a hybrid: lemma rules for verbs and nouns, plus case-insensitive stem regexes for compounds and adjectives, with quoted spans stripped first for the `allow_in_quotes` terms. The authoritative German terminology source (Autismus-Forschungs-Kooperation, "Terminologie-Empfehlungen", 2023) backs every CONT-03 term. It also explicitly says identity-first is *not settled* in German and recommends "Person im Autismus-Spektrum". D-13 locks identity-first, so this is recorded as a known tension, not reopened.

**Primary recommendation:** Build `ndc` (uv + Typer + stdlib sqlite3/sqlite-utils, `db.py` as the single schema owner). Plan 01 is a walking skeleton: `ndc topic add/list` round-trips SQLite inside a `mem_limit: 1g` container. The decision-rule doc and its machine-readable twin (`config/decision_rule.yaml`) are committed and hash-recorded *before* `ndc scan fetch` may run. Collect scan data with yt-dlp plus one plain profile GET per TikTok account, single-threaded with 3–6 s jitter and blocked in 00:15–06:00 UTC. Then run Claude structured-output scoring of text-visible source citing, and an operator walkthrough for the visual/audio fields. The checker and safety filter are deterministic YAML-driven code shared by topic, script and claim levels.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Competitor scan (MKT-01)
- **D-01:** Claude collects the data, the operator spot-checks. A script pulls public profile and video stats (yt-dlp/web); Claude scores source-citing (0–3) from captions and pinned comments; the operator verifies ~5 accounts by hand in the app. Record per-account provenance (scraped vs operator-verified).
- **D-02:** Sample of ~40 accounts per language (ADHS/DACH and ADHD/English), ~80 total.
- **D-03:** Platforms: TikTok + YouTube Shorts (YouTube is the payout path most likely available in Austria). Reels is not scanned.
- **D-04:** Accounts are found by hashtag + search sampling: top accounts under #ADHS/#ADHD, #Autismus/#autism and parent tags (plus the broader-ND tags per D-10), plus accounts named in research (kirmesimkopf, nessadhs, @hey_mamaleben, @verena_eisbrenner, guardianofmind; How to ADHD, Dani Donovan, ADHD Alien, ADHD Dude), spread across size tiers so mid-size accounts are represented.
- **D-05:** Per-account fields follow MKT-01 + research: median views of last 15 posts (never the viral outlier), source-citing score 0–3, face/faceless, voice gender, format, cadence, pillars/audiences covered, saves and shares per 1k views where visible, monetization signals.
- Scraping must be polite (rate-limited) and must not hurt the shared polymarkt-watch host (low concurrency, run outside 00:15–06:00 UTC).

#### Language decision rule (MKT-02)
- **D-06:** Primary signal = sourcing gap + reachable audience: choose German if few DACH accounts cite sources at score ≥2 AND mid-size DACH reach is within roughly 5–10× of English mid-size reach. Exact numeric thresholds are written into the committed rule doc before the scan runs (planner proposes; the operator approves the doc).
- **D-07:** Tie-break / inconclusive data → German.
- **D-08:** One language only in milestone 1; no bilingual or parallel accounts. The other language is a milestone-2 option.
- The decision plus its reasoning is logged in validation week 1 (MKT-02); the hashtag set and crisis-line set (MKT-03) follow from the chosen language.

#### Topic matrix (CONT-01)
- **D-09:** Starting backlog of ~60–80 topics. Claude drafts candidates across the matrix (pillar × condition × domain × audience × angle), each with a whitelist/blacklist tag and a "source likely exists?" flag; the operator keeps or kills each one.
- **D-10:** Condition scope = broader ND: ADHD, autism, AuDHD plus dyslexia, dyspraxia/DCD, Tourette etc. Note: S3/AWMF guidelines exist for ADHS and Autismus only; other conditions lean on PubMed reviews.
- **D-11:** The backlog is weighted evenly across the 4 pillars (challenge+science+help, strengths, parents, men/dads/partners) because the experiment needs ~6–7 videos per pillar.
- Storage: SQLite; listable and filterable by every dimension via CLI.

#### Checker strictness & wording (CONT-03, CONT-04)
- **D-12:** Two tiers. Hard terms block (functioning labels, ABA-adjacent framing, blacklisted subjects: medication, diagnosis questions, ABA, "is my child autistic?"). Soft terms warn and require an override with a recorded reason ("superpower" hype, "leidet an", "Asperger" outside quotes, etc.).
- **D-13:** German autism wording is identity-first. Default to "autistische Menschen" (identity-first and gender-neutral); use "Autist:innen" only where a noun is unavoidable. English is identity-first by default ("autistic people").
- **D-14:** Gendering: neutral constructions where possible ("Menschen mit ADHS", "Eltern"); avoid gender colons in spoken text except the D-13 noun case.
- **D-15:** The terminology list is a versioned file in the repo, drafted by Claude from research and approved by the operator; later changes go through review.
- The safety filter applies at topic level in this phase and exposes the same check for script and claim text (consumed by Phase 2).

#### Style guide (CONT-02)
- Already locked by project decisions: fixed 60–75s template, hook in the first 1–2s spoken + on screen, one topic per video, hedged non-diagnostic tone, calm visuals (no strobe or rapid cuts), accurate burned-in captions, sources in caption/pinned comment.

### Claude's Discretion
- CLI shape, SQLite schema details, and file layout (keep it minimal: Python + uv + Typer + sqlite-utils per research STACK.md).
- Scraping tooling choice and exact sampling procedure within D-01–D-05.
- Exact threshold numbers in the decision-rule draft (operator approves before the scan).

### Deferred Ideas (OUT OF SCOPE)
- Scanning Instagram Reels — not in milestone 1 (Reels are cross-posts only).
- A second-language account — milestone 2 option (D-08).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MKT-01 | Competitor-scan sheet with per-account fields | §Competitor scan feasibility (field → source map). `competitor_account` / `competitor_post` schema. `ndc scan export --csv` produces "the sheet" |
| MKT-02 | Rule written before scan; language decided from data in week 1 | §Decision rule (concrete thresholds plus outcome table). Pre-registration enforced by rule-file sha256 stored on the first `scan_run` |
| MKT-03 | Hashtag/keyword set + crisis-line set fixed | §Hashtag methodology (derived from scan descriptions). §Crisis lines (verified AT/DE/CH, EN alternative) |
| CONT-01 | Browsable SQLite topic matrix, whitelist/blacklist tagged | §Topic matrix vocabularies. `topic` schema forward-compatible with ARCHITECTURE.md. Draft → import → keep/kill CLI |
| CONT-02 | Style guide for the fixed template | §Style guide contents (beat timing, word budget, hedging phrases, flash limit, caption/source card spec) |
| CONT-03 | DE+EN terminology table + automatic check | §Terminology checker (YAML format, hybrid lemma + regex matching, quote stripping, two tiers, hash-bound overrides) |
| CONT-04 | Safety filter at topic/script/claim level | §Safety filter (deterministic subject blacklist, including diagnosis-question patterns; one `check(text, level)` API) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

`/home/nd-content/CLAUDE.md` (GSD-generated) carries the project and stack sections. Actionable directives:
- Python only in M1. CLI + SQLite + flat files. **No web app, task queue, vector DB or agent framework** (LangChain etc.).
- Model IDs and prompts are config, never hard-coded (SCR-06 lands in Phase 2, but any Phase 1 LLM call, i.e. source-citing scoring and topic drafting, should already read the model from config).
- Secrets live in `.env` (`ANTHROPIC_API_KEY`), never in config. Use `python-dotenv`.
- Docker on the shared host: a separate compose project, its own volume (`/home/nd-content-volumes/`, which does not exist yet and must be created) and a `mem_limit`. It must never interfere with polymarkt-watch. Run nothing heavy in 00:15–06:00 UTC.
- yt-dlp reads metadata only and never downloads or re-uploads content. Expect extractor breakage; fall back to manual entry.
- Never auto-reply, never diagnostic. The conservative whitelist (no medication, no diagnosis, no ABA, no "is my child autistic?").
- Tests run with pytest inside the container. Lint with ruff.
- Do not touch `/home/polymarkt-watch` (separate repo).

## Architectural Responsibility Map

The whole phase runs in one local tier (a CLI process plus a SQLite file). The "tiers" here are the module boundaries.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema + migrations | `ndc/db.py` (sole DDL owner) | — | ARCHITECTURE.md: a single schema owner prevents drift |
| Competitor data fetch | `ndc/scan/{tiktok,youtube}.py` (network, no DB writes inside the loop) | `db.py` writes after each fetch returns | Never hold a write txn across a network call |
| Source-citing scoring | `ndc/scan/score.py` → Anthropic API (structured output) | `llm_run` audit row | Claude judges text; operator verifies |
| Visual/audio fields | Operator via `ndc scan verify` walkthrough | — | Not derivable from metadata (no captions, no audio analysis) |
| Language decision | `ndc/scan/decide.py`: pure function over DB rows + `config/decision_rule.yaml` | `docs/language-decision.md` (human log) | Deterministic and re-runnable. Pre-registration checked by hash |
| Topic matrix | `ndc/topics.py` + `config/matrix.yaml` vocab | Claude draft → JSON/CSV import | The operator prunes via CLI |
| Terminology check + safety filter | `ndc/checks/{terminology,safety}.py`, data in `config/terminology.yaml`, `config/safety.yaml` | `check_override` table | Pure functions, reused by Phase 2 on script/claim text |
| Style guide, hashtags, crisis lines | Versioned files in `config/` (consumed by Phase 2 prompts) | — | Content artifacts, git-reviewed |

## Standard Stack

### Core
| Library | Version (PyPI, verified 2026-10-24) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13 (`python:3.13-slim`) | Runtime | Per STACK.md. Note the host only has 3.12.3; uv provisions 3.13 |
| uv | 0.13.5 (host has 0.11.8; pin 0.13.5 in the Dockerfile) | Env/lock/run | STACK.md |
| typer | 0.27.3 | CLI | STACK.md |
| sqlite-utils | 4.2.1 | Upserts, CSV import/export, ad-hoc queries | STACK.md. Keep DDL in `db.py` via stdlib `sqlite3` and use sqlite-utils for convenience I/O |
| pydantic | 2.14.1 | Structured-output models, YAML config validation | STACK.md |
| anthropic | 2.3.0 | Source-citing scoring + topic drafting (`client.messages.parse(output_format=Model)`) | STACK.md. 2.x API |
| PyYAML | 6.0.3 | `config/*.yaml` | STACK.md |
| python-dotenv | 1.2.4 | `.env` secrets | STACK.md |
| rich | 15.0.0 | Tables for `topic list`, `check`, `scan export` | Comes with Typer |
| httpx | 0.28.1 | TikTok profile GET (follower count) | STACK.md |
| tenacity | 9.2.1 | Retry/backoff on scan + API calls | STACK.md |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| yt-dlp | 2026.10.21 (optional extra `scan`) | TikTok/YouTube public metadata | Scan only. Pin the version, re-check with `yt-dlp -U`-equivalent version bumps when extractors break |
| simplemma | 2.0.0 | German/English lemmatization for the checker | Always (checker). Pure Python, no model download |
| pytest | 9.1.1 | Tests | dev |
| ruff | 0.17.2 | Lint/format | dev |
| pytest-recording | 0.14.0 | Replay recorded yt-dlp/HTTP/Anthropic responses | dev. Use saved JSON fixtures for the yt-dlp output instead of live calls |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| simplemma | spaCy `de_core_news_sm` (spacy 3.8.16) | Better POS/lemmas and compound handling is still poor. Pulls a ~15 MB model plus heavy deps; overkill for a term list |
| yt-dlp YouTube search | YouTube Data API v3 (`search.list` now has its own 100-calls/day bucket; `videos.list`/`channels.list` 1 unit; 10,000 units/day) | Exact (unrounded) counts and an official API, but needs a Google Cloud key. Use it only if yt-dlp YouTube breaks |
| Plain profile GET for TikTok followers | Operator types the follower count | The fallback when the profile JSON shape changes |
| LLM safety classifier now | Deterministic only in Phase 1 | Recommend deterministic hard-gate now, LLM "flag-only" second opinion in Phase 2 (where SCR-06 LLM logging lands). Keyword lists miss paraphrases; Pattern 5 covers this in Phase 2 |

**Installation:**
```bash
cd /home/nd-content
uv init --package --name ndc --python 3.13
uv add "typer==0.27.*" "sqlite-utils==4.2.*" "pydantic==2.14.*" "anthropic==2.3.*" \
       "pyyaml==6.0.*" "python-dotenv==1.2.*" "rich==15.*" "httpx==0.28.*" \
       "tenacity==9.2.*" "simplemma==2.0.*"
uv add --optional scan "yt-dlp==2026.10.21"
uv add --dev "pytest==9.1.*" "ruff==0.17.*" "pytest-recording==0.14.*"
```
Only add the Phase 2 deps (biopython, pymupdf, jinja2) in Phase 2.

## Package Legitimacy Audit

slopcheck **could not run** in this environment (tool execution was refused). Per protocol, **every package is `[ASSUMED]`**, and the planner should gate installs behind a `checkpoint:human-verify` (one combined checkpoint in Plan 01 is enough). The registry evidence gathered:

| Package | Registry | Age (first release) | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-------------|-----------|-------------|
| yt-dlp | PyPI | 2021-01 | github.com/yt-dlp/yt-dlp (Unlicense) | unavailable | [ASSUMED], approved pending human-verify. Well-known; used live today |
| simplemma | PyPI | 2021-01 | github.com/adbar/simplemma (MIT) | unavailable | [ASSUMED], approved pending human-verify. Used live today |
| sqlite-utils | PyPI | 2018-07 | github.com/simonw/sqlite-utils (Apache-2.0) | unavailable | [ASSUMED], approved pending human-verify |
| typer | PyPI | 2019-12 | github.com/fastapi/typer (MIT) | unavailable | [ASSUMED], approved pending human-verify |
| anthropic, pydantic, pyyaml, python-dotenv, rich, httpx, tenacity, pytest, ruff, pytest-recording | PyPI | multi-year | official orgs (per STACK.md) | unavailable | [ASSUMED], approved pending human-verify |

**Packages removed due to [SLOP]:** none. **Flagged [SUS]:** none (no verdict available).

## Competitor Scan Feasibility (verified live 2026-10-24, yt-dlp 2026.10.21, no login)

### Field → source map

| MKT-01/D-05 field | TikTok | YouTube Shorts | Provenance tag |
|---|---|---|---|
| Followers / size tier | Profile HTML `__UNIVERSAL_DATA_FOR_REHYDRATION__` → `__DEFAULT_SCOPE__["webapp.user-detail"].userInfo.stats.followerCount` (plain GET worked) [VERIFIED: live probe] | `channel_follower_count` from the `/shorts` flat listing [VERIFIED] | scraped |
| Last 15 posts: views | `--flat-playlist -J` entries: `view_count`, newest first [VERIFIED] | Flat `/shorts` entries: `view_count` (no dates in flat mode) [VERIFIED] | scraped |
| Likes/comments | `like_count`, `comment_count` [VERIFIED] | Per-video `--skip-download -J`: `like_count`, `comment_count` [VERIFIED] | scraped |
| Shares per 1k | `repost_count` [VERIFIED] | Not exposed [ASSUMED absent] | scraped / n/a |
| Saves per 1k | `save_count` present in flat entries [VERIFIED] | Not exposed | scraped / n/a |
| Cadence (posts/week) | `timestamp` of the 15 posts [VERIFIED] | `upload_date` from the per-video call [VERIFIED] | scraped |
| Caption text (for scoring) | `description` [VERIFIED] | `description` (per video) [VERIFIED] | scraped |
| Pinned comment | **Not available**: comments came back empty; impersonation is not allowed | `--write-comments` gives `is_pinned` and `author_is_uploader` [VERIFIED] | scraped (YT) / operator (TT) |
| Spoken/on-screen citations | **Not available** (no subtitles in 20/20 posts) | Not fetched | operator |
| Face/faceless, voice gender, format, creator type | Not in metadata | Not in metadata | operator (walkthrough) |
| Bio / link-in-bio (monetization) | `user.signature`, `user.bioLink` from the profile JSON [VERIFIED] | Channel description (per channel) [ASSUMED available via `--flat-playlist` channel page] | scraped + Claude |
| Pillars/audiences covered | Claude classifies from 15 descriptions | same | claude_scored |

**Gotchas observed live:**
- TikTok view counts above ~10k come back rounded (e.g. `18000`, `310400`), because they mirror the displayed "18K". That is fine for medians but not exact.
- Flat YouTube Shorts entries have no timestamp. Fetch the 15 Shorts per channel individually (15 calls per channel, ~40 YT channels ≈ 600 calls; at 3–6 s that is ~45 min), or accept the newest-15 order without dates and get the dates from the per-video call.
- yt-dlp warns "No supported JavaScript runtime" for YouTube. Metadata still worked with `--skip-download`. Don't add deno unless extraction breaks.
- `kirmesimkopf` has only 5,046 TikTok followers (her main platform is elsewhere), which confirms STATE.md's warning that the research follower numbers are illustrative. Research-named accounts can be off-platform-heavy; record their platform presence honestly rather than forcing them into a tier.
- Pinned posts: TikTok profiles can pin old viral posts at the top. **Always sort by `timestamp` descending and take the newest 15 posts that are ≥72 h old** (views still accumulating on younger posts). Never take "first 15 entries" blindly.

### Discovery (D-04) — what works

| Method | Works? | Use |
|---|---|---|
| Research-named seeds (D-04 list) | Yes | Always included; flag `seed_named=1` |
| TikTok hashtag page via yt-dlp (`tiktok:tag`) | **No**: extractor marked CURRENTLY BROKEN, `ERROR: No working app info` [VERIFIED] | — |
| TikTok hashtag page via plain GET | **No**: no hydrated challenge data in the HTML [VERIFIED] | — |
| TikTok in-app search/hashtag browsing by operator | Yes (manual) | **Primary TikTok discovery.** The operator spends ~30–45 min noting handles into `scan/candidates.csv` |
| YouTube `ytsearch30:"<term> #shorts"` | Yes, returns channel + channel_id [VERIFIED] | Primary YT discovery, scripted |
| Web search `site:tiktok.com/@ ADHS` (Claude WebSearch) | Plausible [ASSUMED] | Optional supplement to widen the TikTok candidate pool |

**Recommended sampling procedure (per language, target ~40 accounts, TikTok-weighted ~28 TT + ~12 YT):**
1. Seeds from D-04 (resolve each to TikTok and/or YouTube handles; record "not on platform" when absent).
2. Operator in-app: for each query in the language's query list (ADHS / ADHD; Autismus / autism; "ADHS Eltern" / "ADHD parenting"; "ADHS Männer" / "ADHD men"; "ADHS Papa" / "ADHD dad"; Neurodivergenz / neurodivergent; Legasthenie / dyslexia; Tourette), open the Accounts tab and the top videos and note the first ~8 distinct recurring creators (≥10 niche posts). Write `handle,platform,language,query,notes` rows into the CSV. Do this as one sitting outside the quiet hours.
3. YouTube: `ytsearch30` per query, keep channels with ≥3 niche Shorts.
4. `ndc scan fetch` pulls followers for all candidates, then **stratified selection**: fill quotas per tier so that the mid tier (10k–100k) has ≥12 accounts per language where available, micro (1k–10k) ~10, macro (100k–1M) ~10, mega (>1M) ≤5, plus all seeds. If the mid tier can't reach 12, record the shortfall (it is itself a finding about DACH saturation).

### Politeness / host safety
- Single-threaded, `sleep(uniform(3, 6))` between every request, an exponential backoff on 429/403 (tenacity), and stop the platform for the run after 3 consecutive failures, falling back to operator entry for the rest.
- Estimated load: ~80 accounts × (1 profile GET + 1 listing) + ~40 YT channels × 15 video calls ≈ 800 requests ≈ 60–80 min wall time. Run in 2–3 sittings; the scan is resumable (skip accounts with a fresh `captured_at`).
- A quiet-hours guard in the CLI refuses `scan fetch`/`scan score` when the UTC time is in [00:15, 06:00). `--force` overrides it and logs the override.
- Run inside the container (`mem_limit: 1g`, `cpus: "1.0"`). No daemon in M1: `docker compose run --rm ndc scan fetch …`.
- Use no cookies, no login, no browser impersonation and no proxy rotation. If TikTok blocks, the fallback is operator entry, not evasion.

### Source-citing score — rubric and Claude scoring

Rubric (from FEATURES.md, sharpened so that it is scorable):

| Score | Definition | Text-observable examples |
|---|---|---|
| 0 | No reference to evidence | Pure personal story or opinion, "so ist ADHS" |
| 1 | Vague appeal to evidence, nothing findable | "Studien zeigen…", "laut Forschung", "science says", "Experten sagen" |
| 2 | A named, findable source (author/institution/guideline/journal) in the caption, pinned comment or spoken/on-screen, but no full reference | "laut S3-Leitlinie ADHS", "Barkley sagt…", "a 2021 meta-analysis by Faraone", "Studie der Uni Bonn" |
| 3 | A full or linkable citation: author + year + journal/DOI/PMID/link, or a reference list in the caption/pinned comment/link-in-bio | "Faraone et al. 2021, Neurosci Biobehav Rev, doi:…", "Quellen im Kommentar" **and** the pinned comment contains refs |

The **account score** is the highest level reached in ≥3 of the last 15 posts (a habit, not a one-off). Store the per-post levels too. Scraping sees only text, so the scraper produces `text_score` and the final `source_citing_score = max(text_score, operator_score)`.

**Operator video-check coverage (extends D-01's ~5 spot checks; flag for operator confirmation):** watch 2 recent videos for (a) the ~5 random spot-check accounts and (b) every DACH account with `text_score ≥ 1`, or creator_type clinician/org, or faceless. These are the only accounts where a hidden on-screen citation could flip the decision rule. Estimated 10–20 accounts, ~20–30 min.

Claude scoring call (`ndc scan score`): one `messages.parse` per account. The model comes from `config/models.yaml` (`scan_scorer: claude-sonnet-5-5`, a STACK.md ID). The input is the bio, up to 15 descriptions and (YouTube) uploader pinned comments. Output schema:

```python
# Source: platform.claude.com structured-outputs docs (per STACK.md); pattern only
class PostCiting(BaseModel):
    post_id: str
    level: Literal[0, 1, 2, 3]
    evidence: str | None  # verbatim substring from the description, None for level 0

class AccountScore(BaseModel):
    text_score: Literal[0, 1, 2, 3]
    posts: list[PostCiting]
    pillars: list[Literal["challenge_science_help", "strengths", "parents", "men_dads_partners"]]
    audiences: list[str]
    hedging_or_diagnostic: Literal["hedged", "neutral", "diagnostic_lists"]
    monetization_signals: list[str]  # from bio/bioLink: shop, book, course, linktree, sponsor, affiliate
    needs_video_check: bool
    confidence: Literal["low", "medium", "high"]

resp = client.messages.parse(model=cfg.models.scan_scorer, max_tokens=4000,
                             messages=[...], output_format=AccountScore)
```
**Guard:** after parsing, verify that every `evidence` string is a literal substring of the input description. Any mismatch downgrades that post's level to 0 and sets `needs_video_check`. This stops a hallucinated "citation" from inflating a score. Cost ≈ 80 accounts × ~5k input tokens ≈ 0.4 MTok ≈ <$2 on Sonnet 5.5 [ASSUMED pricing per STACK.md]. Write an `llm_run` row (model, prompt sha256, request/response artifact path) so Phase 2's SCR-06 table already exists.

## Decision Rule (MKT-02) — proposed thresholds for the operator-approved doc

Definitions (all written into `docs/language-decision-rule.md` + `config/decision_rule.yaml`, committed before the first fetch):

- **Account reach** `M_a` = median `view_count` of the account's newest 15 posts that are ≥72 h old (fewer than 8 qualifying posts → the account is excluded from reach metrics, still counted for sourcing).
- **Size tiers** by followers (TikTok) or subscribers (YT): micro 1k–10k, **mid 10k–100k**, macro 100k–1M, mega >1M. Under 1k: excluded from the sample.
- **Mid-tier reach** `R_lang` = median of `M_a` over the mid-tier accounts of that language, TikTok only (the primary platform). YouTube is reported alongside but does not decide.
- **Reach ratio** `Q = R_EN / R_DE`.
- **Sourcing count** `N_lang` = number of sampled accounts with `source_citing_score ≥ 2`.
- **Slot check** `S_lang` = number of accounts that are score ≥2 **and** faceless **and** male-voiced (the operator's exact positioning).

Proposed thresholds (planner proposes, operator approves):

| # | Condition | Outcome |
|---|---|---|
| V | Validity: fewer than 8 mid-tier TikTok accounts with valid `M_a` in either language | Compute Q over micro+mid combined. If still <8 → **inconclusive → German** (D-07) |
| 1 | `N_DE ≤ 4` **and** `Q ≤ 10` | **German** (sourcing gap + reachable audience) |
| 2 | `Q > 15` | **English** (hard DACH reach ceiling), unless `S_EN ≥ 3` and `S_DE = 0`, in which case it is inconclusive → German |
| 3 | `N_DE ≥ 8` **and** `Q ≤ 15` **and** `S_DE ≥ 1` **and** `S_EN = 0` | **English** (German sourcing gap closed; English positioning slot empty) |
| 4 | Anything else (e.g. `10 < Q ≤ 15`, or `5 ≤ N_DE ≤ 7`) | **Inconclusive → German** (D-07) |

Rationale: "within roughly 5–10×" (D-06) becomes `Q ≤ 10` for a clean German win. 10–15 is a gray band that D-07 resolves to German. Only >15 counts as a ceiling. "Few" = ≤4 of ~40 (≤10%), matching FEATURES.md's "fewer than ~5". The rule rows are evaluated in order V, 1, 2, 3, 4; the first match wins. The decision log must also explicitly answer the research question "does a sourced, male, faceless German account exist?" (`S_DE`).

**Pre-registration enforcement:** the first `ndc scan fetch` records `sha256(config/decision_rule.yaml)` and the git commit of the rule doc on `scan_run`. `ndc scan decide` recomputes the hash and refuses (exit 2) if the rule file changed after the first fetch, unless `--amend "reason"` is given, which is logged. `decide` prints the metric values, the matching row and the verdict, and writes `docs/language-decision.md` (or appends to it) with date, values and reasoning, plus a `language_decision` row in SQLite.

## Hashtag / Keyword Methodology (MKT-03)

1. **Harvest from scan data (free):** regex `#[\wäöüÄÖÜß]+` over all collected descriptions of the chosen language. Count per tag: the number of distinct accounts using it, and the mid-tier median views of posts that carry it.
2. **Candidate tiers:** broad (1–2: `#ADHS`, `#Autismus` / `#ADHD`, `#autism`), niche (`#ADHSbeiErwachsenen`, `#Neurodivergent`, `#AuDHD`…), pillar tags (parents: `#ADHSMama`/`#ADHSEltern`; men/dads: `#ADHSPapa`/`#ADHSMänner`; strengths), all taken from the harvest, not invented. [ASSUMED examples; the harvest decides.]
3. **Exclusions:** any tag that hits `safety.yaml` (e.g. `#Ritalin`, `#ADHSMedikamente`, `#Diagnose`, `#Selbsttest`). Use `#ActuallyAutistic` with care: it is a community-owned self-identification tag (the operator is not stated to be autistic), so exclude it [ASSUMED community norm, flag for operator].
4. **Fixed scheme:** 3–5 hashtags per video = 1 broad + 1–2 niche + 1 pillar tag. The same scheme for every video during validation (FEATURES.md: the hashtag scheme is held constant). Store it as `config/hashtags.yaml` with `version`, the per-pillar tag lists and the harvest stats that justified each tag.
5. **Keywords (search):** a spoken keyword in the first sentence plus the on-screen text (e.g. "ADHS", "Autismus", "ADHS bei Männern"). List them per pillar in the same YAML.
6. Operator in-app check: confirm each chosen tag shows content in the app (post count visible) and isn't restricted. Record that in the YAML (`verified_in_app: <date>`).

## Crisis-Line Set (MKT-03)

**German (DACH audience) — recommended set** (verified 2026-10-24):

| Country | Service | Number | Who / hours | Source |
|---|---|---|---|---|
| AT | Telefonseelsorge | **142** | Everyone, 24/7, free, anonymous; chat/mail via telefonseelsorge.at | [CITED: gesundheit.gv.at notrufnummern; telefonseelsorge.at] |
| AT | Rat auf Draht | **147** | Children, young people (and their caregivers), 24/7 | [CITED: gesundheit.gv.at] |
| AT | Ö3 Kummernummer (Rotes Kreuz) | 116 123 | Everyone, **16:00–24:00 only** | [CITED: gesundheit.gv.at] |
| AT | Männerberatung | 0800 400 777 | Men in crisis, 24/7 (relevant to pillar 4) | [CITED: gesundheit.gv.at] |
| AT | Emergency | 144 (ambulance), 133 (police), 112 | Acute danger | [CITED: gesundheit.gv.at] |
| DE | TelefonSeelsorge | **0800 111 0 111**, **0800 111 0 222**, **116 123** | Everyone, 24/7, free | [CITED: telefonseelsorge.de via search] |
| DE | Nummer gegen Kummer (Kinder- und Jugendtelefon) | 116 111 | Children/young people | [CITED: search results; hours not verified] |
| DE | Elterntelefon | 0800 111 0 550 | Parents: Mon/Wed/Fri 9–17, Tue/Thu 9–19 | [CITED: elterntelefon.info via search] |
| DE | Emergency | 112 | Acute danger | [ASSUMED, well known] |
| CH | Die Dargebotene Hand | 143 | Everyone, 24/7 | [CITED: 143.ch / BAG listing via search] |
| CH | Pro Juventute | 147 | Children/young people, 24/7 | [CITED: 147.ch] |

The pinned-comment short form (DE): "Wenn es dir gerade nicht gut geht: AT 142 · DE 0800 111 0 111 · CH 143 (rund um die Uhr, kostenlos). Im Notfall 144 / 112." The full table lives in `config/crisis_lines.yaml` with `verified_at` and `source_url` per entry. Re-verify before Phase 3's OPS-01 playbook.

**English alternative (only if the rule picks English):** UK Samaritans 116 123 (24/7), Shout text 85258 (24/7), US/CA 988 call/text (24/7) [CITED: search results: samaritans/Shout/988 Lifeline]. Ireland, Australia and others need extra verification [ASSUMED scope].

## Topic Matrix (CONT-01)

### Dimension vocabularies (`config/matrix.yaml`, stable snake_case keys + DE/EN labels)
- **pillar** (4, D-11): `challenge_science_help`, `strengths`, `parents`, `men_dads_partners`
- **condition** (D-10): `adhd`, `autism`, `audhd`, `dyslexia`, `dyspraxia_dcd`, `tourette`, `dyscalculia`, `nd_general`. Each carries a `guideline_layer` hint: `awmf_s3` for adhd/autism, `pubmed_reviews` for the others.
- **domain**: `focus_attention`, `executive_function`, `time_perception`, `emotion_regulation`, `sensory`, `sleep`*, `routines_household`, `school_learning`, `work`, `relationships`, `communication`, `social`, `energy_burnout`*, `masking`, `money`, `late_identification`*, `family_life`, `parenting_coregulation`. (* = sensitive and likely to trip a flag: sleep → melatonin, burnout → self-harm adjacency, late identification → diagnosis questions. Drafting must stay on the safe side of these.)
- **audience**: `nd_adults`, `parents`, `men`, `dads`, `partners`, `general_public`
- **angle**: `mechanism_why` (science explainer), `try_this_strategy` ("if X, try Y"), `myth_vs_research`, `human_not_only_adhd` (the transdiagnostic differentiator from FEATURES.md), `strength_with_caveat`, `what_research_doesnt_know`, `study_explained`, `lived_story_consented`

### Schema (forward-compatible with ARCHITECTURE.md `topic`)
```sql
CREATE TABLE IF NOT EXISTS topic (
  id INTEGER PRIMARY KEY,
  pillar TEXT NOT NULL, condition TEXT NOT NULL, domain TEXT NOT NULL,
  audience TEXT NOT NULL, angle TEXT NOT NULL,
  language TEXT,                       -- 'de'|'en'; NULL until decision (filled by decision)
  working_title TEXT NOT NULL,
  summary TEXT,
  list_tag TEXT NOT NULL CHECK(list_tag IN ('whitelist','blacklist')),
  source_likely TEXT NOT NULL CHECK(source_likely IN ('yes','maybe','no')),
  status TEXT NOT NULL DEFAULT 'proposed'
    CHECK(status IN ('proposed','backlog','selected','in_production','published','retired','rejected')),
  safety_status TEXT NOT NULL DEFAULT 'ok' CHECK(safety_status IN ('ok','flagged','blocked')),
  safety_hits_json TEXT,               -- check() findings at last evaluation
  origin TEXT NOT NULL DEFAULT 'matrix',  -- matrix|operator|trend(M2)|reddit(M2)
  decided_reason TEXT, decided_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE(working_title, language)
);
CREATE INDEX IF NOT EXISTS ix_topic_dims ON topic(pillar, condition, domain, audience, angle);
```
- `proposed` is an *additive* status in front of ARCHITECTURE's enum. Keep → `backlog`, kill → `rejected` (with `decided_reason`).
- `list_tag` (the operator's/Claude's whitelist/blacklist label) is separate from `safety_status` (what `check()` computed). A topic with `list_tag='blacklist'` or `safety_status='blocked'` can never move to `selected`: enforce this in `topics.select()`, and add a test.
- Blacklisted examples are kept (status `rejected` or `backlog` with `list_tag='blacklist'`) as documentation of what is excluded. CONT-01 asks to "show the tag", so `topic list` displays it.
- Also create the empty `llm_run` table now (used by `scan score` and `topic draft`), matching ARCHITECTURE's columns.

### Draft → prune flow
1. `ndc topic draft --n 80` → one Claude `messages.parse` call (model from config) with `matrix.yaml` vocab + safety/terminology summaries + the D-11 even-pillar constraint (20 per pillar ± 2) → a JSON list validated by pydantic (vocab enums enforced) → each candidate passes `safety.check(level="topic")` → insert `status='proposed'`. Also write `artifacts/topic_drafts/<ts>.json` for audit. Alternatively, Claude (this agent, during execution) writes `config/topic_seed.yaml` by hand and `ndc topic import` loads it. That is equivalent and needs no API key; pick one (recommend import from a reviewed YAML file: git-diffable and no runtime LLM dependency).
2. `ndc topic list [--pillar …] [--condition …] [--domain …] [--audience …] [--angle …] [--tag whitelist|blacklist] [--status …] [--format table|csv]` (CONT-01, success criterion 3).
3. `ndc topic review` → an interactive walk over `proposed` rows: `k`eep / `x` kill (prompts for a reason) / `s`kip / `q`uit. Also non-interactive `ndc topic keep ID…`, `ndc topic kill ID --reason …`, because the operator may drive from a phone over SSH.
4. `ndc topic stats` → counts per pillar × status, so the operator sees the ~6–7 per pillar target is reachable after pruning.

Draft language: draft after the language decision so working titles are in the chosen language. The matrix code and import can be built before it.

## Terminology Checker (CONT-03) and Safety Filter (CONT-04)

### File format (`config/terminology.yaml`, versioned; D-15)
```yaml
version: 1
approved_by: operator
approved_at: null            # set when operator approves
terms:
  - id: de.leiden_an
    lang: de
    tier: warn                # block | warn
    category: pathologizing
    match:
      lemma_seq: [["leiden"], ["an", "unter"]]   # lemma of token i, i+1 (window ≤3)
    allow_in_quotes: true
    message: "Pathologisierende Zuschreibung ('leidet an')."
    suggest: "ist autistisch / hat ADHS / erlebt …"
    rationale: "AFK 2023: emotionale Zuschreibungen wie 'unter Autismus leiden' vermeiden."
    source: "https://www.autismus-forschungs-kooperation.de/…/230719-Empfehlungen-Sprachgebrauch.pdf"
  - id: de.hochfunktional
    lang: de
    tier: block
    category: functioning_label
    match:
      regex: '\b(hoch|niedrig|gering)[-\s]?funktional\w*'
    allow_in_quotes: false
  - id: any.asperger
    lang: any
    tier: warn
    category: outdated
    match: {regex: '\bAsperger\w*|\bAspie\w*'}
    allow_in_quotes: true       # "Asperger outside quotes" ⇒ quoted spans stripped first
```
`config/safety.yaml` has the same shape but `scope: subject`, an always-`block` tier, and `levels: [topic, script, claim]`.

### Matching algorithm (hybrid, verified building blocks)
1. Normalize: NFC, lowercase a copy for regex (keep original offsets via a char map), normalize typographic dashes/quotes.
2. **Quote stripping** for `allow_in_quotes` rules: remove spans inside balanced pairs `„…“`, `"…"`, `“…”`, `»…«`, `«…»`, `‚…‘`, `'…'`. An unbalanced quote means the text is treated as unquoted (fail-safe: warn).
3. Tokenize (`\w+(?:-\w+)*`); lemmatize each token with `simplemma.lemmatize(tok, lang=…)` [VERIFIED live: leidet/litt/gelitten → leiden; Medikamente → Medikament; geheilt → heilen; suffered → suffer; superpowers → superpower].
4. Apply `lemma` / `lemma_seq` rules (window-based, so "leidet seit Jahren an" needs a window ≤3 tokens and is configurable).
5. Apply `regex` rules on the normalized text. **Regex is required for compounds and adjectives** (simplemma left `hochfunktionalen`, `Superkräfte`, `Asperger-Syndrom` unchanged [VERIFIED]): e.g. `superkr(a|ä)ft\w*`, `\w*medikament\w*` (catches `ADHS-Medikamente`, `Medikamentenpause`), and case-sensitive `\bABA\b` (avoid matching "Abakus").
6. Return `Finding(rule_id, tier, category, span, matched_text, message, suggest)`. Overall result: `blocked` if any block finding; `needs_override` if only warns; `ok` otherwise.

Pure functions: `check_terminology(text, lang) -> list[Finding]`, `check_safety(text, lang, level) -> list[Finding]`, and a combined `check(text, lang, level)`. Phase 2 imports these unchanged.

### Override recording (D-12)
```sql
CREATE TABLE IF NOT EXISTS check_override (
  id INTEGER PRIMARY KEY, text_sha256 TEXT NOT NULL, rule_id TEXT NOT NULL,
  level TEXT NOT NULL, reason TEXT NOT NULL CHECK(length(trim(reason)) >= 5),
  terminology_version INTEGER NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(text_sha256, rule_id)
);
```
- `ndc check FILE --lang de --level script [--override RULE_ID="reason"]…` exits 0 (ok, or all warns overridden for *this exact text hash*), 1 if a block finding exists (block can **never** be overridden), and 2 if warns remain un-overridden. Binding to `text_sha256` mirrors Phase 2's hash-bound approval: editing the text voids the overrides.
- `ndc check --text "…"` for quick checks.

### Starter term table (Claude drafts the full YAML; operator approves per D-15)

**Block tier (terminology):**
| DE | EN | Basis |
|---|---|---|
| hochfunktional*, niedrigfunktional*, leichter/milder/schwerer Autismus, "high/low functioning" | high-functioning, low-functioning, mild/severe autism | AFK 2023 [CITED]; PITFALLS |
| ABA, angewandte Verhaltensanalyse, Stimming abgewöhnen/unterbinden/abtrainieren, Blickkontakt erzwingen/trainieren, "Autismus heilen/bekämpfen" | ABA, applied behavior analysis, stop stimming, make them make eye contact, cure autism | PITFALLS; D-12; AFK Q3 |
| zurückgeblieben, geistig behindert | retarded | AFK 2023 [CITED] |

**Warn tier (override with reason):**
| DE | EN | Suggestion |
|---|---|---|
| leiden an/unter (all forms) | suffer from/with | "ist autistisch", "hat ADHS", "erlebt" |
| Superkraft/Superkräfte, "Gabe" hype | superpower | "manche berichten von Stärken bei … neben echten Herausforderungen" |
| Asperger* outside quotes, Aspie | Asperger's outside quotes, aspie | "Autismus" / quote historical terms |
| Autismus-Spektrum-Störung / ASS outside quotes | autism spectrum disorder outside quotes | "Autismus(-Spektrum)" (AFK: ok when citing ICD/DSM) |
| Krankheit, erkrankt, Störung (non-quoted, about autism), Defizit*, Symptom* (re autism) | disease, disorder (non-clinical), deficit | "Merkmale", "Unterschiede", "Schwierigkeiten bei …" (AFK) |
| komorbid | comorbid | "zusammen auftretend" (AFK) |
| gesund/normal as a contrast group, neurotypisch as a comparison label | healthy/normal controls | "nicht-autistisch" (AFK) |
| eingeschränkte/begrenzte Interessen | restricted interests | "intensive Interessen" (AFK) |
| Mensch(en) mit Autismus, Person mit Autismus | person with autism | "autistische Menschen" (D-13) |
| Autisten/Autistinnen (generic) | — | "autistische Menschen"; "Autist:innen" only if a noun is unavoidable (D-13/D-14) |
| AD(H)S, ADS as a separate condition, Zappelphilipp, Modediagnose, "jeder ist ein bisschen ADHS" | "everyone's a little ADHD" | PITFALLS; misinformation pattern |
| Behandlung, Therapie (outside guideline quotes) | treatment, therapy | "Unterstützung", "Strategien", "Umfeld" (PITFALLS) |

**Known tension to document in the YAML header:** AFK 2023 says German identity-first is not settled and recommends "Person im Autismus-Spektrum" as neutral. D-13 locks identity-first ("autistische Menschen"), which AFK lists as a valid identity-first form. Do not flag "Person im Autismus-Spektrum" (allowed neutral).

### Safety filter subjects (`config/safety.yaml`, all **block**, levels topic/script/claim)
| Subject | DE patterns (lemma/regex) | EN patterns |
|---|---|---|
| Medication | `\w*medikament\w*`, Methylphenidat, Ritalin, Medikinet, Concerta, Elvanse, Lisdexamfetamin, Atomoxetin, Strattera, Guanfacin, Intuniv, Stimulan(z\|s)\w*, Amphetamin\w*, Melatonin, Antidepressiv\w*, SSRI, Dosis, Tablette\w*, Pille\w* | medication, meds, methylphenidate, Ritalin, Adderall, Vyvanse, Concerta, Strattera, atomoxetine, guanfacine, stimulant(s), melatonin, SSRI, dose/dosage, pill(s) |
| Diagnosis question | `\b(hab(e)?\|hast) ich (adhs\|autismus)`, `\bbin ich (autistisch\|neurodivergent)`, `\b(ist\|wird) mein kind autistisch`, `\bhat mein kind (adhs\|autismus)`, `woran erkenne ich,? ob`, `\bselbst-?test\w*`, `\bcheckliste\b`, `\b\d+ (anzeichen\|signs?)\b`, `test(e)? dich` | "do I have ADHD", "am I autistic", "is my child autistic", "does my child have", "signs you have", "self-test", "quiz", "checklist" |
| ABA | (see block terminology; also listed here at subject level) | ABA |
| Self-harm / suicide | Suizid\w*, Selbstmord\w*, Selbstverletz\w*, ritzen | suicide, self-harm, kill myself |
| Eating disorders | Essstörung\w*, Magersucht, Anorexie, Bulimie, ARFID | eating disorder, anorexia, bulimia, ARFID |
| Cure / treatment claims | heilen (lemma), Heilung, kurieren, "wegtherapieren" | cure(d), heal autism/ADHD |
| Supplements / diet-as-treatment | Nahrungsergänzung\w*, Omega-?3, Supplement\w*, "ADHS-Diät", zuckerfrei heilt | supplement(s), omega-3, ADHD diet |
| Conspiracy framing | "Ärzte verschweigen", "was dir keiner sagt", Impf\w* | doctors won't tell you, vaccine(s) |

Diagnosis-adjacent wording such as "Diagnose" alone is too broad for block (it would hit "nach der Diagnose"). Put it on **warn** in terminology.yaml (`category: diagnosis_adjacent`). The crisis-line YAML is exempt from checking (it naturally contains "Suizid").

## Style Guide Contents (CONT-02) — `config/style_guide.md`
It lives in `config/` because Phase 2 prompts consume it. It should contain:
- **Template beats (60–75 s):** 0–2 s hook (spoken = on-screen text, contains the search keyword) → 2–10 s "what people experience" (hedged: "Manche Menschen mit ADHS…") → 10–45 s explanation with 1–2 cited claims, each with an on-screen source card (1–2 s, "Studie: Autor et al. Jahr, Journal") → 45–65 s what helps / environment / strategy → 65–75 s strength-with-caveat or a one-line takeaway + "Quellen im angepinnten Kommentar".
- **Word budget:** ~140–190 spoken words for 60–75 s at a calm ~140–150 wpm [ASSUMED speaking rate; calibrate on the operator's first recordings].
- **Hedging phrase bank** (DE+EN): "manche", "viele berichten", "Studien deuten darauf hin", "im Schnitt", "kann", "das heißt nicht, dass…". **Forbidden frames:** "du hast ADHS, wenn…", lists of signs, "Ärzte sagen dir nicht…".
- **Disclaimer line:** "Kein Ersatz für ärztliche oder psychotherapeutische Beratung." in the caption/bio. "Ich bin kein Therapeut – ich lese die Forschung und übersetze sie."
- **Visual rules:** calm palette, no strobe. **No more than 3 flashes in any 1-second period** (WCAG 2.3.1 general flash threshold) [ASSUMED citation, standard], no rapid-cut montage, minimum ~1.5 s per shot, high-contrast captions, nothing text-critical in the bottom ~20% (platform UI overlap) [ASSUMED].
- **Captions:** burned in, verbatim to the spoken script (accuracy over styling), max 2 lines, ~32–42 characters per line [ASSUMED].
- **Source presentation:** the on-screen card format, the pinned-comment format (author, year, title short, journal, DOI/PMID; AWMF register number for guidelines), and that the source list is rendered from the DB only (Phase 2 SCR-04).
- **Terminology pointer:** "every script must pass `ndc check`" (links CONT-03), including the D-13/D-14 wording rules spelled out in prose.
- **Crisis line in the pinned comment** for any topic touching emotions/burnout (from `crisis_lines.yaml`).

## Architecture Patterns

### System Architecture Diagram
```
                 ┌──────────────── config/ (git, versioned) ─────────────────┐
                 │ decision_rule.yaml  matrix.yaml  terminology.yaml          │
                 │ safety.yaml  hashtags.yaml  crisis_lines.yaml  models.yaml │
                 │ style_guide.md                                             │
                 └───────┬──────────────┬─────────────┬───────────────────────┘
operator CSV ──┐         │rule sha256   │vocab        │terms
seeds (D-04) ──┼─▶ ndc scan fetch ──(yt-dlp / httpx GET, 1 req per 3–6 s,
yt search ─────┘        │                quiet-hours guard)──▶ TikTok / YouTube
                        ▼  (write after each fetch returns)
                 competitor_account / competitor_post  (SQLite, WAL)
                        │
            ndc scan score ──▶ Anthropic messages.parse ──▶ AccountScore
                        │       (evidence substring guard) ──▶ llm_run audit
            ndc scan verify (operator: face/voice/format/on-screen cite)
                        │
            ndc scan export ──▶ competitor sheet CSV (MKT-01)
            ndc scan decide ──(rule hash check)──▶ verdict + docs/language-decision.md
                        │                                   │
                        ▼                                   ▼
             hashtags.yaml (harvest)              topic.language filled
                                                            │
 topic seed YAML / ndc topic draft ──▶ check(level=topic) ──▶ topic(status=proposed)
                                                            │
                                    ndc topic review (keep/kill) ──▶ backlog | rejected
                                                            │
 any text ──▶ ndc check (terminology + safety) ──▶ ok | needs_override | blocked
                        └── overrides bound to text_sha256 ──▶ check_override
```

### Recommended Project Structure
```
/home/nd-content/
├── pyproject.toml / uv.lock
├── Dockerfile / docker-compose.yml / .env.example / .gitignore (.env, artifacts/, data/)
├── config/   decision_rule.yaml matrix.yaml terminology.yaml safety.yaml
│             hashtags.yaml crisis_lines.yaml models.yaml style_guide.md topic_seed.yaml
├── docs/     language-decision-rule.md  language-decision.md
├── scan/     candidates.csv (operator-collected handles)
├── src/ndc/
│   ├── cli.py            # Typer app: topic, scan, check sub-apps
│   ├── db.py             # sole DDL owner, idempotent migrations, WAL
│   ├── config.py         # pydantic-validated YAML loaders
│   ├── topics.py
│   ├── checks/{terminology,safety,text}.py   # text = normalize/quotes/tokenize/lemmatize
│   ├── scan/{tiktok,youtube,score,decide,quiet_hours}.py
│   └── llm.py            # thin Anthropic wrapper writing llm_run rows
└── tests/ (fixtures/ with saved yt-dlp JSON + sample scripts DE/EN)
```
Data path: inside the container `/data/ndc.db`, bind-mounted from `/home/nd-content-volumes/` (create it). Never use `/data` on the host directly (on this host that path belongs to another project's convention).

### Pattern: walking skeleton (Plan 01)
`uv init` → `ndc --help` → `db.py` creates `topic` + `llm_run` → `ndc topic add --pillar … --title …` and `ndc topic list` round-trip through SQLite → `Dockerfile` (`python:3.13-slim`, uv copied from `ghcr.io/astral-sh/uv:0.13.5` [ASSUMED tag], `uv sync --frozen`) → `docker compose run --rm ndc topic list` works → one pytest per command passes inside the container.

### docker-compose essentials
```yaml
services:
  ndc:
    build: .
    image: nd-content:dev
    mem_limit: 1g
    memswap_limit: 1g
    cpus: "1.0"
    env_file: .env
    volumes:
      - /home/nd-content-volumes/data:/data
      - ./config:/app/config:ro
      - ./docs:/app/docs
      - ./scan:/app/scan
    working_dir: /app
    entrypoint: ["uv", "run", "--no-sync", "ndc"]
    # no ports, no restart policy: CLI-only, nothing listening
```
The host has 11 GB RAM with ~5 GB available; polymarkt-watch is capped at 9 GB. 1 GB is ample (yt-dlp and simplemma are light).

### Anti-Patterns to Avoid
- **Scraping with impersonation/cookies/login or evading blocks.** Refused by policy and against platform rules. Fall back to operator entry.
- **Taking the first 15 listing entries.** Pinned posts distort them. Sort by timestamp and apply the ≥72 h age filter.
- **Mean views or including the outlier.** Use the median only (D-05).
- **Editing the decision rule after seeing data.** The hash check prevents it; amendments are explicit and logged.
- **One combined "lint" boolean.** Keep tiers and per-rule IDs, so overrides are auditable.
- **Lemma-only matching.** It misses compounds (`ADHS-Medikamente`). **Regex-only matching** misses inflections (`litt`). Use both.
- **DDL outside `db.py`**, or writing to SQLite inside the network loop.
- **Exposing any port.** M1 has no server (the sibling project on this host was just drained via a dashboard path-traversal; keep nd-content port-free).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TikTok/YouTube metadata parsing | Custom HTML/API scrapers for posts | yt-dlp `--flat-playlist -J` / `--skip-download -J` | Maintained extractors. The only hand parse is the single profile-JSON follower field |
| German inflection | Suffix-stripping regexes for every verb | simplemma lemmatize + targeted regex | Irregular forms (`litt`, `gelitten`) break naive stemming |
| Structured LLM output | Prompt "return JSON" + json.loads | `client.messages.parse(output_format=PydanticModel)` | Schema-valid output, validated locally |
| Retry/backoff | sleep loops | tenacity | Jitter, stop conditions |
| CSV sheet export | Manual csv writer quirks | sqlite-utils / `csv.DictWriter` over a view | Trivial; keep a `v_competitor_sheet` SQL view as the single sheet definition |
| Median | — | `statistics.median` | stdlib |

**Key insight:** the risky parts here are judgment (scoring, terms, the rule), not code volume. Spend the effort on fixtures and tests that pin the judgment, not on infrastructure.

## Runtime State Inventory
Greenfield phase: not applicable (no rename/migration). Omitted.

## Common Pitfalls

### Pitfall 1: Hidden on-screen citations undercount DACH sourcing
**What goes wrong:** text-only scoring says `N_DE = 2`, but several accounts cite on screen, so the rule picks German on a false gap.
**How to avoid:** the operator video-checks every DACH account with `text_score ≥ 1`/clinician/faceless (≈10–20 accounts). The decision uses `max(text, operator)`.
**Warning signs:** many DACH accounts at text_score 1 ("Studien zeigen").

### Pitfall 2: Mid tier too thin in DACH
**What goes wrong:** only 4 DACH mid-tier accounts, so the Q ratio is noise.
**How to avoid:** the validity row V of the rule. Discovery deliberately searches niche queries to find mid-size accounts. Record the shortfall as a finding.

### Pitfall 3: Rounded and immature view counts
**What goes wrong:** posts <72 h old and rounded "K" counts skew the medians.
**How to avoid:** the age filter. Accept rounding (medians are robust); note it in the sheet.

### Pitfall 4: Extractor breakage mid-scan
**What goes wrong:** a TikTok extractor update breaks the listing halfway through.
**How to avoid:** pin yt-dlp; make the scan resumable; per-account `fetch_status`; manual entry fallback `ndc scan add-manual` (followers + 15 view counts typed from the app, `provenance='operator_entered'`).

### Pitfall 5: Checker false positives erode trust
**What goes wrong:** "Diagnose", "Störung" and "Therapie" appear legitimately (quotes, guideline names), so the operator starts overriding reflexively.
**How to avoid:** keep these as warn with clear suggestions; `allow_in_quotes`; a fixture corpus of legitimate sentences that must produce zero block findings (a precision test), alongside the must-flag corpus.

### Pitfall 6: Safety filter checks only the topic title
**What goes wrong:** "ADHS und Schlaf" passes, then a script mentions Melatonin.
**How to avoid:** one `check(text, level)` exposed now, with tests at all three levels (success criterion 5). Phase 2 calls it on script and claims.

### Pitfall 7: LLM-drafted topics drift outside the vocab or the pillar balance
**How to avoid:** pydantic `Literal` enums for every dimension; `topic stats` shows per-pillar counts; the import rejects unknown keys.

### Pitfall 8: Running during quiet hours / starving the host
**How to avoid:** the CLI quiet-hours guard, container limits and no parallelism.

## Code Examples

### yt-dlp TikTok listing → last-15 median (pattern verified live)
```python
# Source: live probe 2026-10-24 (yt-dlp 2026.10.21 Python API equivalent of --flat-playlist -J)
import statistics, time, random
from yt_dlp import YoutubeDL

def tiktok_recent(handle: str, n: int = 30) -> list[dict]:
    opts = {"extract_flat": True, "playlistend": n, "quiet": True, "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.tiktok.com/@{handle}", download=False)
    keep = ("id", "timestamp", "view_count", "like_count", "comment_count",
            "repost_count", "save_count", "duration", "description")
    return [{k: e.get(k) for k in keep} for e in info.get("entries") or []]

def median_last15(posts, now_ts):
    eligible = sorted((p for p in posts if p["timestamp"] and now_ts - p["timestamp"] >= 72*3600),
                      key=lambda p: p["timestamp"], reverse=True)[:15]
    views = [p["view_count"] for p in eligible if p["view_count"] is not None]
    return (statistics.median(views), len(views)) if len(views) >= 8 else (None, len(views))

time.sleep(random.uniform(3, 6))  # between accounts
```

### TikTok follower count (one plain GET; no impersonation)
```python
# Source: live probe 2026-10-24 — public profile page hydration JSON
import json, re, httpx
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def tiktok_profile(handle: str) -> dict | None:
    r = httpx.get(f"https://www.tiktok.com/@{handle}", headers={"User-Agent": UA}, timeout=20)
    m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return None  # → operator entry
    ui = json.loads(m.group(1)).get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {}).get("userInfo", {})
    stats, user = ui.get("stats") or {}, ui.get("user") or {}
    return {"followers": stats.get("followerCount"), "video_count": stats.get("videoCount"),
            "bio": user.get("signature"), "bio_link": (user.get("bioLink") or {}).get("link")}
```

### Lemma + quote-aware matching core
```python
# Source: simplemma 2.0.0 API (verified live: lemmatize(tok, lang="de"))
import re, simplemma
QUOTE_PAIRS = [("„", "“"), ("\"", "\""), ("“", "”"), ("»", "«"), ("«", "»"), ("‚", "‘")]

def strip_quoted(text: str) -> str:
    for o, c in QUOTE_PAIRS:
        text = re.sub(re.escape(o) + r"[^" + re.escape(c) + r"]*" + re.escape(c),
                      lambda m: " " * len(m.group(0)), text)  # keep offsets
    return text

def lemmas(text: str, lang: str) -> list[tuple[str, int, int]]:
    return [(simplemma.lemmatize(m.group(0), lang=lang).lower(), m.start(), m.end())
            for m in re.finditer(r"\w+(?:-\w+)*", text)]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| yt-dlp `tiktok:tag` hashtag listing | Marked CURRENTLY BROKEN in 2026.10.21 | before 2026-10 | Hashtag discovery is manual |
| YouTube Data API: search.list = 100 units | search.list has a separate 100-calls/day bucket; other calls 1 unit; 10k/day | per current docs [CITED: developers.google.com/youtube/v3/determine_quota_cost] | The API is a viable fallback if needed |
| "Asperger", functioning labels | "Autismus(-Spektrum)", describe support needs | ICD-11/DSM-5; AFK 2023 | Warn/block terms |
| yt-dlp YouTube without a JS runtime | Deprecated (deno recommended) | 2025–26 | Metadata still works. Install deno only if extraction fails |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | All packages legitimate (slopcheck unavailable) | Package audit | Low (well-known); one human-verify checkpoint |
| A2 | Proposed thresholds (N_DE ≤4, Q ≤10 / >15, mid = 10k–100k, ≥8 valid accounts) | Decision rule | The operator must approve before the scan (D-06) |
| A3 | Operator video-check of ~10–20 DACH accounts (beyond D-01's ~5) is acceptable | Scoring | If not, Pitfall 1 risk rises. Ask the operator |
| A4 | Operator walkthrough for face/voice/format on all ~80 accounts (~40–60 min) | Field map | MKT-01 requires these fields; no automated source exists. Ask the operator |
| A5 | YouTube channel description is retrievable via yt-dlp | Field map | Monetization signals for YT come from the operator |
| A6 | Example hashtags; `#ActuallyAutistic` should be excluded | Hashtags | The harvest decides; community etiquette is to be confirmed by the operator |
| A7 | Speaking rate 140–150 wpm, caption line lengths, bottom-20% safe zone, WCAG flash rule | Style guide | Calibrate on the first recordings |
| A8 | DE emergency 112; Nummer gegen Kummer hours | Crisis lines | Re-verify in Phase 3 OPS-01 |
| A9 | Web search `site:tiktok.com` helps discovery | Discovery | Optional only |
| A10 | Sonnet 5.5 pricing/model IDs per STACK.md | Scoring cost | Config-driven; trivial |
| A11 | `ghcr.io/astral-sh/uv:0.13.5` image tag exists (ghcr returned 401 to an anonymous probe) | Dockerfile | Fall back to `pip install uv==0.13.5` in the image |

## Open Questions (RESOLVED — see 01-CONTEXT.md D-17 walkthrough automated, D-18 TikTok-only Q, D-19 reviewed seed file; D-21 no API in Phase 1)

1. **Operator time for the field walkthrough (A3/A4).**
   - What we know: face/voice/format/on-screen citations can't be scraped.
   - What's unclear: whether the operator accepts ~1–1.5 h total for walkthrough + video checks, vs D-01's "~5 accounts".
   - Recommendation: the planner adds this as an explicit operator checkpoint task with a time estimate. Allow `unknown` for face/voice on non-decisive accounts (micro/mega English) to cut the time roughly in half.
2. **Topic drafting at runtime vs a reviewed seed file.**
   - Recommendation: reviewed `config/topic_seed.yaml` (git-diffable, no API key needed) plus `ndc topic import`. A `topic draft` command is optional.
3. **Does the operator want YouTube in the decision metric?** The rule proposes TikTok-only for Q (YouTube reported). Confirm this in the rule-doc approval.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker + compose | Container runtime | ✓ | 29.4.0 / v5.1.2 | — |
| uv (host) | Local dev | ✓ | 0.11.8 (target 0.13.5) | Pin 0.13.5 in the image; the host version is fine for `uv run` |
| Python 3.13 | Runtime | ✗ on host (3.12.3); uv provisioned 3.13 automatically in the scratch test | — | The container image |
| git | Pre-registration commit | ✓ | 2.43.0 | — |
| yt-dlp | Scan | installs from PyPI (tested in a scratch venv) | 2026.10.21 | Operator manual entry |
| ffmpeg / JS runtime | Not needed (metadata only) | ✗ | — | Warnings are harmless |
| Anthropic API key | scan score, topic draft | unknown (`.env` not created) | — | Claude-in-session scoring/drafting via files |
| `/home/nd-content-volumes/` | DB volume | ✗ (create it) | — | Plan 01 creates it |
| Network to tiktok.com / youtube.com | Scan | ✓ (probed) | — | — |

**Missing with no fallback:** none. **Missing with fallback:** the volume directory (create it), the Anthropic key (in-session alternative).

## Validation Architecture

(`workflow.nyquist_validation` is `false` in config.json, but the orchestrator requested this section.)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (in container) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (Wave 0) |
| Quick run command | `docker compose run --rm --entrypoint "uv run --no-sync pytest -q -x" ndc tests/` |
| Full suite command | `docker compose run --rm --entrypoint "uv run --no-sync pytest -q" ndc` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| (skeleton) | `topic add` → `topic list` round-trips SQLite; migrations are idempotent (run twice) | unit + CLI (Typer `CliRunner`) | `pytest tests/test_db.py tests/test_cli_topic.py` | ❌ Wave 0 |
| MKT-01 | Saved yt-dlp/profile JSON fixtures parse into account/post rows; median uses ≥72 h newest 15 and ignores pinned/young posts; `v_competitor_sheet` has every MKT-01 column; provenance set | unit (fixtures, no network) | `pytest tests/scan/test_parse.py tests/scan/test_sheet.py` | ❌ |
| MKT-01 | Score guard: a non-substring `evidence` downgrades to 0 | unit (mocked parse result) | `pytest tests/scan/test_score_guard.py` | ❌ |
| MKT-01 | Quiet-hours guard blocks 00:15–06:00 UTC unless `--force` | unit (freeze clock) | `pytest tests/scan/test_quiet_hours.py` | ❌ |
| MKT-02 | `decide()` returns the expected verdict for one synthetic dataset per rule row (V, 1, 2, 3, 4), including tie → German | unit (table-driven) | `pytest tests/scan/test_decide.py` | ❌ |
| MKT-02 | `decide` refuses when the rule hash differs from the first `scan_run` (without `--amend`) | unit | `pytest tests/scan/test_prereg.py` | ❌ |
| MKT-02 | Rule doc committed before the first fetch | manual/git | `git log --format=%cI -- config/decision_rule.yaml` earlier than the first `scan_run.started_at` | manual |
| MKT-03 | `hashtags.yaml`, `crisis_lines.yaml` load via pydantic; each crisis entry has number, source_url, verified_at; no hashtag hits safety.yaml | unit | `pytest tests/test_config_files.py` | ❌ |
| CONT-01 | Filters by each of the 5 dimensions + tag/status; the tag is shown; blacklist/blocked topics can't be selected; the import rejects unknown vocab; pillar counts | unit + CLI | `pytest tests/test_topics.py` | ❌ |
| CONT-02 | `style_guide.md` contains the required sections (60–75 s, hook 0–2 s, hedging, captions, calm visuals/flash, sources) | unit (heading/keyword presence) | `pytest tests/test_style_guide.py` | ❌ |
| CONT-03 | Must-flag corpus: each listed term (DE+EN, inflected forms: leidet/litt/gelitten, hochfunktionalen, Superkräfte, Asperger outside quotes, ABA framing) yields the expected rule_id/tier; "Asperger" inside „…“ does not flag | unit (parametrized) | `pytest tests/checks/test_terminology.py` | ❌ |
| CONT-03 | Precision corpus: legitimate sentences give zero block findings; warns are overridable; the override is bound to the text hash (an edit voids it); block can't be overridden; exit codes 0/1/2 | unit + CLI | `pytest tests/checks/test_overrides.py tests/test_cli_check.py` | ❌ |
| CONT-04 | Each blacklisted subject (medication incl. compounds, diagnosis-question patterns, ABA, "is my child autistic?" DE+EN) blocks at level topic, script and claim | unit (parametrized over level) | `pytest tests/checks/test_safety.py` | ❌ |
| Success crit. 4 | `ndc check tests/fixtures/sample_script_de.txt --lang de --level script` lists the violations | CLI smoke | same command, assert exit 2 / findings | ❌ |
| Live scan | One real account fetch works end-to-end | manual smoke (network, polite) | `docker compose run --rm ndc scan fetch --only kirmesimkopf` | manual |

### Sampling Rate
- **Per task commit:** the quick run (targeted test file).
- **Per wave merge:** the full suite + `ruff check`.
- **Phase gate:** the full suite green; the manual checks (rule commit precedes scan, operator spot-check provenance rows present, decision doc written).

### Wave 0 Gaps
- [ ] `pyproject.toml` pytest/ruff config; `tests/conftest.py` with a tmp-DB fixture (`Database(tmp_path/"t.db")`), a frozen clock and a config loader pointing at test YAMLs
- [ ] `tests/fixtures/`: saved `tt_flat.json`-style yt-dlp output (scrub nothing secret; it is public data), a profile JSON snippet, YT shorts listing, DE/EN sample scripts (must-flag + precision corpora)
- [ ] The Typer `CliRunner` harness

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No server, no users |
| V3 Session Management | no | — |
| V4 Access Control | no | Local CLI only; **expose no ports** |
| V5 Input Validation | yes | pydantic for YAML config + LLM outputs; parameterized SQL only; treat scraped descriptions as untrusted (never `eval`, never shell-interpolate handles; validate handles `^[A-Za-z0-9._]{2,24}$`) |
| V6 Cryptography | no (hashing only) | `hashlib.sha256` for rule/text hashes |
| Secrets | yes | `.env` (gitignored), `.env.example` committed; never log the API key; scrub cassettes |

### Known Threat Patterns
| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| Prompt injection via scraped captions into the scoring LLM | Tampering | Structured output only; the evidence-substring guard; scores are advisory, the operator verifies the decisive accounts |
| Shell injection via handles in subprocess calls | Tampering | Use the yt-dlp Python API (no subprocess) + handle regex |
| Retroactive rule edit | Repudiation | Rule sha256 on `scan_run` + git history |
| Secret leakage in the git repo | Information disclosure | `.gitignore .env`; `commit_docs` only covers `.planning/` |

## Sources

### Primary (HIGH confidence)
- Live probes 2026-10-24 with yt-dlp 2026.10.21 (scratch venv): TikTok user flat listing (fields incl. `save_count`, `repost_count`), single video, `tiktok:tag` broken, TikTok comments empty, YouTube `/shorts` flat + per-video + comments `is_pinned`, `ytsearch30`
- Live probe: TikTok profile `__UNIVERSAL_DATA_FOR_REHYDRATION__` follower stats via plain GET
- Live test: simplemma 2.0.0 lemmatization (DE/EN)
- PyPI JSON API: versions/licenses for all packages (2026-10-24)
- [gesundheit.gv.at — Notrufnummern bei Krise und Suizidgefahr](https://www.gesundheit.gv.at/leben/suizidpraevention/anlaufstellen/notrufnummern.html): AT numbers/hours
- [Telefonseelsorge Österreich](https://www.telefonseelsorge.at/): 142, 24/7, free
- [Autismus-Forschungs-Kooperation — Terminologie-Empfehlungen (2023)](https://www.autismus-forschungs-kooperation.de/WordPressStrato200521/wp-content/uploads/230719-Empfehlungen-Sprachgebrauch.pdf): full text extracted
- [YouTube Data API quota costs](https://developers.google.com/youtube/v3/determine_quota_cost)

### Secondary (MEDIUM confidence)
- [TelefonSeelsorge Deutschland](https://www.telefonseelsorge.de/) / [Wikipedia: Telefonseelsorge](https://de.wikipedia.org/wiki/Telefonseelsorge): 0800 111 0 111 / 0222 / 116 123
- [Elterntelefon (Nummer gegen Kummer)](https://www.elterntelefon.info/): 0800 111 0 550 and hours
- [Pro Juventute 147](https://www.147.ch/de/beratung/dein-kontakt-zu-uns/), [143.ch Die Dargebotene Hand](https://www.infosenior.ch/de/angebot-finden/143ch-die-dargebotene-hand-darueber-reden-hilft)
- [Samaritans](https://samaritanshope.org/our-services/24-7-helpline/), [988 Lifeline (Wikipedia)](https://en.wikipedia.org/wiki/Suicide_and_Crisis_Lifeline), [Centre for Mental Health helplines](https://www.centreformentalhealth.org.uk/helplines-and-crisis-contacts/)
- [autismus-kultur.de — High-Functioning-Autismus](https://autismus-kultur.de/high-functioning-autismus/), [mittendrin — Begrifflichkeiten](https://mittendrin.family/begrifflichkeiten/)
- Project research: `.planning/research/{STACK,FEATURES,PITFALLS,ARCHITECTURE}.md`

### Tertiary (LOW confidence)
- Hashtag examples and the `#ActuallyAutistic` etiquette (to be confirmed by the harvest and the operator)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (versions verified live; slopcheck unavailable → audit marked ASSUMED)
- Scan feasibility: HIGH (probed live today), but vendor behaviour can change any day
- Decision-rule thresholds: MEDIUM (reasoned from D-06/FEATURES; the operator approves)
- Terminology: MEDIUM (AFK 2023 authoritative for research language; community preferences vary)
- Crisis lines: HIGH for AT (official .gv.at), MEDIUM for DE/CH/EN (official sites via search)
- Pitfalls: MEDIUM-HIGH

**Research date:** 2026-10-24
**Valid until:** scan-tooling facts ~7 days (yt-dlp/TikTok churn); everything else ~30 days
