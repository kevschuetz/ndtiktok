# Stack Research

**Domain:** Faceless short-form health/neurodivergence video account. Research-grounded script tooling (M1), then a production automation pipeline (M2).
**Researched:** 2026-10-24
**Confidence:** HIGH for the Anthropic API, PubMed and package versions (each verified live against PyPI, npm or the official docs on 2026-10-24). MEDIUM for the platform-analytics and scheduler APIs (checked against vendor docs plus secondary 2026 guides). LOW where marked.

---

## Critical corrections to the brief (read first)

1. **The model lineup in the research prompt is stale.** As of 2026-10-24 the official models overview lists these current models:

   | Model | API ID | Price (input/output per MTok) |
   |-------|--------|-------------------------------|
   | Claude Fable 5.1 | `claude-fable-5-1` | $10 / $50 |
   | Claude Opus 5.5 | `claude-opus-5-5` | $4 / $20 |
   | Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2 / $10 |
   | Claude Haiku 5.5 | `claude-haiku-5-5` | from $0.10 / $0.50 |

   Every current model has a 1M-token context window, 128K max output and adaptive thinking.

   `claude-sonnet-5` and `claude-haiku-4-5-20251001` are now **legacy** (still callable). Use the 5.5 IDs, and put model IDs in config, never hard-coded. (HIGH, platform.claude.com/docs/en/models/overview.)
2. **Citations and structured outputs cannot be combined in one request.** If any document has citations enabled and you also pass `output_config.format`, the API returns a 400 error. This shapes the whole M1 architecture:
   - **Draft pass:** citations ON, plain text out.
   - **Verify pass:** structured outputs ON, no citations. Sentences are carried as data instead.

   (HIGH, official citations doc.)
3. **AWMF has no API, and its register is behind a bot-stopper.** Both `register.awmf.org/de/leitlinien/detail/...` and the PDF asset URLs return an HTML challenge page to scripted requests (tested with curl and WebFetch). The operator downloads guideline PDFs by hand into a local `corpus/guidelines/` folder. Do not build a scraper. (HIGH, tested live.)
4. **The S3 ADHS guideline (028-045) is mid-revision.** The 2018 version expired in May 2022. A revision was due by 2026-09-30, and a consultation draft ("KF") has circulated. Before relying on either version, the operator must check by hand which version is currently valid and record the version and date in the source record. (MEDIUM: secondary sources, AWMF page not reachable by script.)
5. **Semantic Scholar without a key returned HTTP 429 on the first call.** It is not in the M1 critical path.

---

## Recommended Stack — Milestone 1 (validation + light tooling)

Principle: **CLI scripts plus SQLite plus flat files, Python only.** Keep to around six direct dependencies. No web app, no vector DB, no agent framework.

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | 3.13 (`python:3.13-slim` image) | Runtime for all M1 tooling | Every library below supports it. One language keeps an operator-time-limited project small. | HIGH |
| uv | 0.13.5 | Dependency + venv + lockfile manager | One tool for install, lock and run (`uv run nd draft ...`), with reproducible `uv.lock` and fast Docker builds. Replaces pip + pip-tools + virtualenv. | HIGH |
| anthropic (Python SDK) | 2.3.0 (released 2026-10-23) | Claude calls: grounded draft (citations) + adversarial verify (structured outputs) | The official SDK. It covers `document` blocks with `citations: {enabled: true}`, `search_result` blocks, `client.messages.parse(..., output_format=PydanticModel)` (it now maps to `output_config.format`), prompt caching and the Batch API. Note that this is a **2.x** major version: don't copy 0.x-era snippets. | HIGH |
| pydantic | 2.14.1 | Schemas for sources, claims and verdicts; structured-output models | Passed directly to `messages.parse`. The SDK strips constraints the API doesn't support and still validates locally. | HIGH |
| SQLite (stdlib `sqlite3`) + sqlite-utils | sqlite-utils 4.2.1 | Topic matrix, source registry, claim↔source pairs, per-video metrics log | One file, zero ops, easy to back up. sqlite-utils gives schema-less inserts/upserts, CSV import (`sqlite-utils insert ... --csv`) and a CLI for ad-hoc queries, which suits a 20–30-video log. Use WAL mode. | HIGH |
| Typer | 0.27.3 | CLI surface (`nd retrieve`, `nd draft`, `nd verify`, `nd caption`, `nd metrics add`) | Type-hint-driven CLI with almost no boilerplate. Rich output comes for free. | HIGH |
| httpx | 0.28.1 | HTTP for E-utilities / Europe PMC / (optional) Semantic Scholar | Sync and async from one client, timeouts by default, HTTP/2. It is stable but old (Dec 2024); that is fine, since it is the de-facto standard. | HIGH |

### Biomedical retrieval (M1)

| Source | Access | Use For | Why / Notes | Confidence |
|--------|--------|---------|-------------|------------|
| **PubMed via NCBI E-utilities** (`esearch` → `esummary`/`efetch`) | Free REST. 3 req/s without a key, **10 req/s with a free NCBI API key**. Always send `tool=` and `email=`. | Primary discovery plus citation metadata (PMID, DOI, journal, year, authors, publication types, abstract) | Authoritative. The filters do the evidence-hierarchy work: `systematic[sb]`, `Meta-Analysis[pt]`, `Review[pt]`, `Practice Guideline[pt]`, plus MeSH (`"Attention Deficit Disorder with Hyperactivity"[MeSH]`, `"Autism Spectrum Disorder"[MeSH]`). Verified live 2026-10-24. Check `Retracted Publication[pt]` / "retraction of" to exclude retracted papers. | HIGH |
| **Biopython `Bio.Entrez`** | biopython 1.88 | Thin wrapper over E-utilities, used for `efetch` XML parsing | Handles rate limiting, the API key and MEDLINE/XML parsing, which saves writing a parser. Raw httpx is fine for `esearch` JSON. | HIGH |
| **Europe PMC REST** (`/webservices/rest/search`, `/{PMCID}/fullTextXML`) | Free, no key | Open-access **full text**, so claims can cite sentences beyond the abstract | Better OA full-text access than PubMed (structured JAT XML), covers PubMed and PMC, and offers `PUB_TYPE:"systematic-review"`, `OPEN_ACCESS:y` and `resultType=core`. During testing it returned a **transient 503**: wrap it in tenacity retries. | MEDIUM-HIGH |
| **AWMF guidelines (S3 ADHS 028-045; Autismus 028-018 diagnosis / 028-047 therapy)** | Manual PDF download only | German guideline statements and recommendations ("Empfehlungen") | The source of German-language authority. Extract text with PyMuPDF, split it into recommendation blocks, and keep page numbers so citations can point to a page. | HIGH (access), MEDIUM (current version status) |
| **PyMuPDF** | 2.0 (released 2026-10-19; new major) | PDF → text with page numbers for guideline PDFs and any OA PDFs | Fast and accurate, and keeps page numbers. Alternatively, pass the PDF straight to Claude as a `document` (base64 PDF source); citations then come back as `page_location`. Use both: PyMuPDF for indexing and search, the native PDF document for the draft call. The 2.0 major is brand new, so pin it and run a smoke test (LOW risk of API breaks). | MEDIUM |
| **NICE guidelines (NG87 ADHD, CG142/CG170 autism)**, optional | Manual or web | English-language guideline layer if the language decision is English | Plays the role AWMF plays in German. | MEDIUM |
| Semantic Scholar Graph API | `semanticscholar` 0.12.0 or raw httpx; **needs a free API key** | Optional: TLDRs, citation counts, "highly influential citations" | Not needed in M1. Unauthenticated calls hit 429 immediately (tested). Defer it, or apply for a key if the operator wants citation-count signals. | MEDIUM |

**Retrieval design (prescriptive):** no embeddings or vector DB in M1. Each topic pulls about 5–15 sources: guideline sections plus the top systematic reviews/meta-analyses. Claude's 1M context and citations feature then read them directly. Cache every fetched record in SQLite (`sources` table: id, kind, pmid, doi, pmcid, title, year, journal, pub_types, url, retrieved_at, text_hash, guideline_version), so drafts are reproducible and the APIs aren't hit again.

### Claude grounding + adversarial verification (M1)

| Step | Model | API features | Why |
|------|-------|-------------|-----|
| 1. Draft 60–75s script + hook | `claude-opus-5-5` (default) | Each source as a `document` block: plain text for abstracts/sections, PDF for guidelines, **custom content** for guideline recommendation lists. `citations: {enabled: true}`. `cache_control` on the documents. System prompt holds the style guide, hedging rules, whitelist/blacklist and "only claims supported by the documents". | Citations return the exact `cited_text` with `char_location` / `page_location` / `content_block_location` per claim. `cited_text` doesn't count toward output tokens. Plain text and PDF are chunked into sentences automatically, so citations are sentence-granular, which is exactly the claim ↔ source-sentence pairing the requirements ask for. |
| 2. Adversarial verify | **A different model than the draft**: `claude-sonnet-5-5` or `claude-fable-5-1` for hard topics | `client.messages.parse(output_format=VerifyReport)`, no citations (incompatible). Input: the script split into atomic claims, each with the `cited_text` from step 1 plus the full source text. Output: per claim, `{claim, source_id, source_sentence, verdict: supported/partially/unsupported/overgeneralized, hedge_ok, issue, suggested_fix}`. | Structured outputs are GA (no beta header) and give a schema-valid table to render for operator review. A different model and a "find the overreach" prompt reduce same-model agreement bias. |
| 3. Caption/source list | `claude-haiku-5-5` or a pure template | Jinja2 template from the `sources` table (APA-lite: Author et al., Year, Journal, DOI/PMID link) | This is deterministic, so no LLM is needed. It never invents a citation, because it renders only DB rows. |

Cost at M1 volume (about 1 video/day, about 30–80K input tokens per draft with caching): roughly $0.20–$1 per video on Opus 5.5, well inside budget. Use the Batch API (50% off) only in M2.

**Operator review output:** a Markdown or terminal (Rich table) report pairing each claim with its source sentence, verdict and link. Store it in SQLite (`claims` table) so the go/no-go readout can audit it.

### Metrics (M1)

| Platform | M1 method | Notes | Confidence |
|----------|-----------|-------|------------|
| **TikTok** | **Manual: TikTok Studio desktop → Analytics → Export data (CSV)** plus hand entry of per-video retention / average watch time / watched-full-video % from the video detail page | Analytics only reach back **60 days**, so export weekly. Desktop only. The Display API doesn't expose retention to a small creator, and the Research API is for academics. | MEDIUM |
| **YouTube Shorts** | YouTube Studio by hand; optionally the **YouTube Analytics API** (`google-api-python-client` 2.201.0, OAuth, own channel): `views`, `averageViewPercentage`, `averageViewDuration`, `shares`, `subscribersGained` per video | It is free and works for any channel size. Automate it only if hand entry becomes annoying. | HIGH |
| **Instagram Reels** | Manual from in-app insights in M1. M2 option: Instagram Graph API media insights (`views`, `reach`, `saved`, `shares`, avg watch time) on a **Professional (Creator/Business) account** | Meta deprecated `plays`/`impressions` in 2025, and `views` is now the primary metric. Some new fields require "Instagram API with **Facebook** Login", so link a Facebook Page if you go the API route. | MEDIUM |

**M1 recommendation:** a `nd metrics add` CLI (or a CSV import into SQLite with `sqlite-utils insert --csv`). With 20–30 videos, typing beats any API integration. The `videos` table holds: video_id, platform, posted_at, pillar, condition, audience, angle, hook_type, language, length_s, views, avg_watch_s, completion_pct, shares, saves, follows, captured_at. Store snapshots at fixed ages (24h, 72h, 7d) so videos are compared at the same age.

### Supporting Libraries (M1)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | 9.2.1 | Retry/backoff for E-utilities, Europe PMC (503s seen) and the Anthropic API | Always, around every network call |
| rich | 15.0.0 | Claim↔source review tables in the terminal | Review step (comes with Typer) |
| python-dotenv | 1.2.4 | Load `ANTHROPIC_API_KEY`, `NCBI_API_KEY`, `NCBI_EMAIL` | Always. Secrets go in `.env`, never in config |
| jinja2 | 3.1.6 | Caption / pinned-comment source-list templates | Caption step |
| PyYAML | latest | `config.yaml` (model IDs, whitelist/blacklist, retrieval filters) | Always |
| trafilatura | 2.3.1 | Extract the main text from guideline/organization web pages (e.g. NICE HTML) | Only when a source is HTML, not PDF |
| yt-dlp | 2026.10.21 | **Competitor scan:** pull public metadata (view counts, upload dates, descriptions, for checking whether sources are cited) from TikTok/YouTube account pages | Competitor-scan phase. It breaks often, so update it often and expect some extractor failures on TikTok. Fall back to manual sampling. Read metadata only, never re-upload. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff 0.17.2 | Lint + format | One tool. Configure in `pyproject.toml` |
| pytest 9.1.1 | Tests | Run inside the container |
| pytest-recording 0.14.0 (VCR.py) | Record E-utilities/Europe PMC/Anthropic HTTP once and replay it in tests | Keeps tests offline and free. Scrub API keys from cassettes |
| Docker + docker compose | Isolated runtime on the shared host | Separate compose project, its own volume (`/home/nd-content-volumes/`), set `mem_limit` (e.g. 1g in M1; 6–8g in M2 for render/Whisper) so it never starves polymarkt-watch |

## Installation (M1)

```bash
uv init nd-content && cd nd-content
uv add "anthropic==2.3.*" "pydantic==2.14.*" "typer==0.27.*" "httpx==0.28.*" \
       "biopython==1.88" "sqlite-utils==4.2.*" "pymupdf==2.0.*" \
       "tenacity==9.2.*" "python-dotenv==1.2.*" "jinja2==3.1.*" pyyaml
uv add --optional scan "yt-dlp" "trafilatura==2.3.*"
uv add --dev "ruff==0.17.*" "pytest==9.1.*" "pytest-recording==0.14.*"
```

---

## Recommended Stack — Milestone 2 (automation, only for winning formats)

| Component | Recommendation | Version | Why | Confidence |
|-----------|---------------|---------|-----|------------|
| Video composition/render | **Remotion** (React/TS, headless Chromium render via `@remotion/renderer` / CLI) | 4.0.538 (all `@remotion/*` packages must be the **exact same version**) | Code-defined templates suit repeatable formats (hook card, kinetic captions, B-roll, source end card). `@remotion/captions` provides TikTok-style word-highlight captions. **License:** free for individuals and companies with ≤3 employees, commercial use included. Remotion 5.0 will change the license slightly, so recheck before upgrading. Rendering happens locally in Docker (no Lambda needed at 1 video/day). | HIGH |
| Node | Node 22 LTS (or 24 LTS) | — | Remotion 4 runs on current LTS. A separate `render` service in Docker keeps the Python container slim. | MEDIUM |
| Word timestamps | **faster-whisper** with `word_timestamps=True`, model `large-v3-turbo` (or `large-v3` for German accuracy), `compute_type="int8"` on CPU | 1.2.1 | CTranslate2 runs about 4× faster than openai-whisper on CPU with less RAM. 60–75s clips transcribe in well under a minute on CPU. Because the operator reads a known script, align the transcript back to the script text afterwards, which corrects Whisper's spelling of technical terms. Convert the output to Remotion `Caption[]` JSON. | HIGH (lib), MEDIUM (CPU timing) |
| Alternative in-ecosystem | `@remotion/install-whisper-cpp` (whisper.cpp) | 4.0.538 | Choose it if you want transcription inside the Node render service and output already in Remotion's caption format. Either choice is fine; pick one. | MEDIUM |
| TTS fallback | **ElevenLabs** cloned from the operator's *own* voice (Instant/Professional Voice Clone) for emergency days; local **Piper** (`piper-tts` 1.8.0, German `de_DE` voices) as a free last resort | — | The project's own voice is the differentiator, and a clone of that voice keeps the brand consistent. Any synthetic voice needs TikTok's AI-generated content label. Never use a different persona. | MEDIUM |
| Publishing | **Buffer API** (public GraphQL API since 2026-05-27, available on every plan; TikTok, YouTube and Instagram supported; $5/channel/month on Essentials; also ships an MCP server and CLI) | — | Cheapest multi-platform publish path that avoids the TikTok app audit. 3 channels ≈ $15/mo, within the $30–80 budget. | MEDIUM |
| Publishing alternative | **Blotato** ($29/mo Starter flat; API + n8n + hosted MCP; built for TikTok/Reels/Shorts) | — | Choose it if Buffer's TikTok video posting falls short in testing. | MEDIUM |
| TikTok direct (optional) | **TikTok Content Posting API — "Upload to inbox" mode** | — | **Needs no audit**: the video lands as a draft in the TikTok app and the operator taps publish. That *is* the human gate. Direct Post without an audit is forced to SELF_ONLY with private accounts and at most 5 creators per 24h, so don't depend on it. | MEDIUM |
| Approve card | Telegram Bot API via **python-telegram-bot** (or plain httpx `sendVideo` + inline keyboard callback) | latest 22.x | Proven pattern on this host. Send the video, script, claim↔source table and buttons. A separate bot and chat from polymarkt-watch. | MEDIUM |
| Analytics feedback | YouTube Analytics API + Instagram Graph insights automated; TikTok stays CSV export (or Buffer analytics if the plan includes it) | — | TikTok offers no retention API to a small creator. | MEDIUM |
| Scheduling inside the box | Plain cron / a long-running Python loop with APScheduler | — | No Airflow/Prefect for one video a day. | HIGH |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| PubMed E-utilities + Europe PMC | OpenAlex (`pyalex` 0.21) | When you need broad citation graphs or non-biomedical literature. PubMed is better for clinical evidence filtering via MeSH and publication types. |
| Native Claude citations | Self-built quote-extraction prompt ("quote the sentence verbatim") | Never in M1. Native citations guarantee `cited_text` really exists in the document, while prompt quotes can be hallucinated. |
| Long-context stuffing (5–15 sources) | Embeddings + vector DB (Chroma/pgvector) | Only if the corpus grows past about 200 documents per topic, or M2 needs cross-topic semantic search of a big local library |
| Separate draft and verify calls | One call doing both | Never: the two features are API-incompatible, and self-verification in one pass is weak |
| SQLite + sqlite-utils | Postgres, Airtable, Notion | Notion/Airtable only if the operator insists on editing the matrix on a phone. Even then, sync it into SQLite as the source of truth |
| Typer CLI | Streamlit / web UI | M2 at the earliest, and only if the Telegram card isn't enough |
| faster-whisper | WhisperX 3.8.6 (forced alignment + diarization) | If faster-whisper's word timing drifts noticeably on German speech. WhisperX adds wav2vec2 alignment at the cost of PyTorch weight |
| Buffer API | Metricool API | Metricool's API needs the **Advanced plan (from about €43/mo)**, which is too much for a single brand. Its analytics UI is good, though |
| Remotion | FFmpeg + MoviePy / Editly | If template complexity stays trivial (static text + captions). Remotion pays off once there are animated, reusable templates |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Scraping register.awmf.org | Behind a bot-stopper, and scraping is unreliable and unfriendly | Manual PDF download into `corpus/guidelines/`, with the version and date recorded |
| `output_format` / structured outputs together with citations | 400 error, API-incompatible | Two-pass draft (citations) → verify (structured outputs) |
| `client.beta.messages.create(output_format=...)` (raw dict) | The parameter moved to `output_config.format`, and the SDK raises a TypeError | `client.messages.parse(output_format=PydanticModel)` or `output_config={"format": {...}}` |
| Legacy model IDs (`claude-sonnet-5`, `claude-haiku-4-5-20251001`) as defaults | Superseded by the 5.5 generation | `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5` from config |
| Extended thinking with `budget_tokens` | Not accepted on current models (adaptive thinking only) | Steer it with the `effort` parameter |
| LangChain / LlamaIndex / agent frameworks | Heavy abstraction over three API calls, slower to debug, and they hide citation blocks | The Anthropic SDK directly |
| openai-whisper (reference impl) | About 4× slower on CPU, and pulls in the full PyTorch | faster-whisper |
| Google Scholar scraping / Sci-Hub | No API, ToS/legal problems, no reliable metadata | PubMed / Europe PMC / DOI |
| Citing from LLM memory | The core credibility risk. Fabricated or retracted references | Captions render only `sources` rows retrieved by the tooling |
| Instagram Basic Display API | Retired in Dec 2024 | Instagram Graph API on a Professional account |
| TikTok Direct Post as the publish path before an audit | Forced private (SELF_ONLY) | Buffer/Blotato, or TikTok "Upload to inbox" drafts |
| Third-party "TikTok analytics scrapers" that ask for your login | Account-safety risk for the main asset | TikTok Studio CSV export |

## Stack Patterns by Variant

**If the week-1 scan picks German (ADHS):**
- The primary authority layer is AWMF S3 guidelines (manual PDFs) plus German-language reviews where they exist. Most evidence will still be English PubMed reviews, and the draft prompt translates while keeping the cited source sentence in its original language for review.
- Use `large-v3` (not turbo) for Austrian German word timestamps in M2, and run a spot-check.

**If English (ADHD):**
- Swap the guideline layer to NICE NG87 / CG142 / CG170 (plus the CDC/AAP for the parent pillar), and keep PubMed/Europe PMC unchanged.

**If the operator wants to review on a phone in M1:**
- Write the verify report to a Markdown file and send it through a minimal Telegram `sendDocument`. Don't build a web UI.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| anthropic 2.3.x | pydantic 2.x, Python ≥3.9 | 2.x major: `messages.parse` + `output_config`. Pin the minor version |
| pymupdf 2.0 | Python 3.13 | A new major released 5 days before this research. Pin `2.0.*` and test text extraction plus page numbers on one AWMF PDF |
| sqlite-utils 4.2.x | stdlib sqlite3 | 4.x major. Use WAL for concurrent CLI and cron reads |
| remotion 4.0.538 | all `@remotion/*` 4.0.538, react/react-dom ≥16.8 (use React 19) | Mismatched `@remotion/*` versions are the most common breakage. Pin them exactly, without `^` |
| faster-whisper 1.2.1 | ctranslate2 4.x, CPU int8 | GPU not required. No PyTorch needed |

## Sources

- platform.claude.com/docs/en/models/overview: current model IDs, pricing, 1M context, adaptive thinking, legacy list (HIGH, fetched 2026-10-24)
- platform.claude.com/docs/en/build-with-claude/citations: document types, sentence chunking, `cited_text` not billed, **incompatibility with structured outputs** (HIGH)
- platform.claude.com/docs/en/build-with-claude/structured-outputs: `messages.parse`, GA, `output_config.format`, schema limits (HIGH)
- PyPI JSON API and npm registry, queried 2026-10-24: every version number above (HIGH)
- Live probe of `eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi` with `systematic[sb]`: works (HIGH). Europe PMC REST returned a transient 503 (MEDIUM). Semantic Scholar unauthenticated returned 429 (HIGH)
- NCBI Insights, "New API Keys for the E-utilities": 3 vs 10 req/s (HIGH): https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities
- register.awmf.org (bot-stopper observed). Status of S3 ADHS 028-045: [expired 2018 PDF](https://register.awmf.org/assets/guidelines/028-045l_S3_ADHS_2018-06-abgelaufen.pdf), [ADHSSpektrum: "Die neue S3-Leitlinie ADHS 2026"](https://steady.page/en/adhsspektrum/posts/ea142ed9-cbb6-4ed8-a265-c844e9962fa0) (MEDIUM)
- Remotion LICENSE.md (GitHub main): free tier ≤3 employees; 5.0 license change pending (HIGH)
- TikTok Studio CSV export, 60-day window: [Sozee guide](https://www.sozee.ai/resources/export-tiktok-analytics-data/), [Metricool](https://metricool.com/tiktok-reports/) (MEDIUM)
- TikTok Content Posting API audit / SELF_ONLY / inbox mode: [Outstand](https://www.outstand.so/blog/tiktok-content-posting-api), [PostZen](https://www.postzen.dev/blog/tiktok-api) (MEDIUM)
- Instagram insights changes: [Meta Instagram Platform insights](https://developers.facebook.com/documentation/instagram-platform/insights), [Supermetrics field changes](https://docs.supermetrics.com/docs/instagram-insights-updates) (MEDIUM)
- Buffer API relaunch 2026-05-27: [Buffer Help Center](https://support.buffer.com/article/859-does-buffer-have-an-api), [buffer.com/made-for/developers](https://buffer.com/made-for/developers) (MEDIUM)
- Metricool API plan gate: [Metricool help](https://help.metricool.com/plans-add-ons-and-api-access-explained-xux1u) (MEDIUM)
- Blotato pricing: [blotato.com/blog/tiktok-api-pricing](https://www.blotato.com/blog/tiktok-api-pricing) (MEDIUM, vendor-authored)

---
*Stack research for: faceless research-grounded neurodivergence short-form account (nd-content)*
*Researched: 2026-10-24*
