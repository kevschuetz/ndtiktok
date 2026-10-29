# Phase 3: Launch Readiness & First Publish - Research

**Researched:** 2026-10-29 (inline, operator: no subagents)
**Domain:** recording transcript diff + hash-bound approval, publish/metrics ledger with pre-registered readout, launch surface (moderation playbook, accounts, platform eligibility)
**Confidence:** HIGH on the in-repo mechanics (everything reuses Phase-2 code), MEDIUM on platform facts (TikTok export columns, FYF labels, Creator Rewards country list — verify in-app during execution)

<user_constraints>
## User Constraints (from 03-CONTEXT.md)

### Locked Decisions
- D-01 fuzzy per-sentence diff (alignment + similarity threshold; claim-wording changes, dropped/weakened hedges, new sentences = deviations)
- D-02 deviations → existing verifier against the locked corpus → operator ack/fix on the phone → recording transcript gets its own hash-bound approval; publish log blocks without it; no deviation → automatic approval with the diff stored
- D-03 video 1 = topic 3 „Starke Gefühle bei ADHS" v7 (`fd07bd2c…`)
- D-04 captions = word-timed SRT from the diffed Whisper transcript, imported into CapCut/TikTok by the operator; no Remotion
- D-05 CLI-first entry: `ndc publish log`, `ndc metrics import` (TikTok Studio CSV), `ndc metrics add` for missing fields; phone UI review-only
- D-06 TikTok full snapshots; YouTube/Instagram post id + views only
- D-07 `ndc metrics due` + daily cron writing the due list to a file the phone UI shows; no Telegram
- D-08 snapshot ages 24 h / 72 h / 7 d; FYF eligibility yes/no/unknown + reason
- D-09 MedienG §25 disclosure stays deferred (operator risk decision) — no Impressum work in this phase
- D-10 bio: „ADHS & Autismus, erklärt aus Studien. Keine Diagnosen, keine Therapie – Quellen in jedem Video."
- D-11 moderation = research protocol (canned human replies with AT/DE/CH numbers, keyword filters, pinned resources, spike protocol at ~10× median views)
- D-12 plan proposes 5–8 handle candidates; operator checks availability and picks; TikTok Personal, YouTube channel, Instagram Professional (Creator)
- D-13 Creator Rewards checked in-app; YPP path documented; template unchanged

### Claude's Discretion
- Readout rule content (research defaults) + lock mechanism; similarity metric/threshold; transcript hash; SRT format; CSV column mapping; cron cadence; schema; recording approval table shape; canned-reply wording (operator approves)

### Deferred Ideas (OUT OF SCOPE)
- Telegram reminders/approve card; phone-UI logging forms; Impressum page/address service; hook A/B re-cuts; full YT/IG snapshots + Instagram Graph API
</user_constraints>

<research_summary>
## Summary

Nothing in this phase needs a new dependency. The recording diff is Phase-2 plumbing turned around: faster-whisper (already installed in `ndc-heavy`) yields segments with word timestamps; the approved side is already sentence-split and hashed (`script_sentence`); alignment is a monotone sequence match of normalized spoken sentences against approved sentences; deviations are verified with the existing `build_verify_request` / `force()` path by handing the spoken sentence the cited source sentences of its matched approved sentence; the approval reuses the `review` / `claim_ack` shape keyed on the transcript hash. The SRT is produced from the same word timings with the approved text substituted for matched sentences, so captions can never say something the verifier did not see.

The publish log and metric snapshots are two append-only tables plus three CLI commands and a cron line (the host already runs cron for polymarkt-watch via `docker exec`). The readout rule copies the Phase-1 pre-registration pattern (`decision_rule.yaml` + `.lock`, `scan/prereg.py` refusing a changed rule) with the research defaults from FEATURES.md.

The launch surface is documents and config: a validated `config/moderation.yaml` rendered to a playbook, a launch doc with the bio, handle candidates and platform settings, and an eligibility doc the operator fills from the apps. Platform facts below are directional and must be confirmed in-app.
</research_summary>

<findings>
## Key Findings

### Transcription and alignment (SCR-05)
- `src/ndc/scan/transcribe.py` wraps `faster_whisper.WhisperModel` (CPU, int8, lazy load, weights in `/data/models`). It currently joins segment text only. Extend with `word_timestamps=True` (each segment exposes `.words` with `start`, `end`, `word`, `probability`) and `language="de"`; keep `vad_filter=True`. Use `large-v3` for Austrian German (STACK.md), configurable via a new `config/recording.yaml` (`whisper_model`, `compute_type`, `cpu_threads`, `similarity_threshold`, `language`). Decode audio with the existing `scan/pitch.decode_audio` (PyAV) — works for video containers too.
- Alignment: normalize both sides with `sources/split.normalize` + casefold + strip punctuation; split spoken text with `split_sentences(text, "de")`; align with `difflib.SequenceMatcher` over token lists (monotone, handles merged/split sentences by also trying 2-sentence windows); per pair compute a token-level ratio. Default threshold 0.80 — calibrate on the first real take and record the chosen value in the plan summary. Statuses: `match`, `deviation` (aligned but below threshold or hedge token missing), `extra` (spoken, no counterpart), `missing` (approved sentence not spoken).
- Hedge check (cheap, deterministic, from PITFALLS Pitfall 1): a configurable hedge word list (`manche`, `häufig`, `könnte`, `kann`, `deuten darauf hin`, `vielleicht`, `oft`, …); a match whose approved sentence contains a hedge token that the spoken sentence lacks becomes a `deviation` regardless of ratio.
- Verification of deviations: build the payload with `script/verify.build_verify_request` using `{ordinal, text=spoken, cited=<cited sentences of matched approved sentence>}`; extra sentences get `cited=[]` (→ `force()` makes any non-framing extra sentence `unsupported`); store in a new `recording_verdict` table with the same columns as `claim_verdict`. Model/prompt from `config/llm.yaml verify` (logged in `llm_run`, `subject_kind='recording'`).
- Approval: sibling tables `recording_review` and `recording_ack` keyed on `transcript_sha256` (same CHECKs as `review`/`claim_ack`, append-only triggers). Gate logic mirrors `review/gate.py`: blockers = any `unsupported`/`contradicts` deviation or extra; needs_ack = `partial`/`overstated`/escalation; warnings = `missing` approved sentences (dropped content is not a false claim) and low ASR confidence. No deviations → auto approval row (`reviewer='system'`, `channel='cli'`, note „keine Abweichungen").
- `recording.transcript_sha256 = sha256(NFC(final transcript text))` where the final text uses approved sentence text for matches and spoken text for approved deviations — this is what Phase 4 publishes and what the SRT carries.

### SRT (D-04)
- Build cues from Whisper word timings grouped per aligned sentence (start of first word, end of last word), text = final transcript sentence; split cues longer than ~42 characters × 2 lines at word boundaries; standard `HH:MM:SS,mmm` format. CapCut and TikTok import `.srt`; the operator sets styling in the app.

### Publish log and snapshots (MEAS-02/03)
- Tables: `publication` (id, script_version_id, recording_id, platform CHECK IN ('tiktok','youtube','instagram'), post_id, post_url, posted_at, pillar, angle, hook_tactic, caption_sha256, pinned_comment_sha256, created_at) — insert refused unless `review` approved for the script sha AND `recording_review` approved for the recording (TikTok row required first; cross-post rows reference the same recording). `metric_snapshot` (publication_id, age_label CHECK IN ('24h','72h','7d','adhoc'), captured_at, post_age_hours, views, likes, comments, shares, saves, follows, avg_watch_s, watched_full_pct, retention_json, fyf_status CHECK IN ('yes','no','unknown'), fyf_reason, source CHECK IN ('csv','manual'), raw_json). Both append-only; corrections are new rows.
- TikTok Studio CSV: the native export (desktop TikTok Studio → Analytics → Export data) covers overview/content/followers tabs for a selectable period ≤ 60 days; column names are not documented officially and vary by locale (German UI → German headers). Design `ndc metrics import` around a **configurable column map** in `config/metrics.yaml` (`post_id` / `Video-Link`, `Videoaufrufe`, `Likes`, `Kommentare`, `Geteilt`, `Favoriten`/`Speichern`, `Durchschnittliche Wiedergabezeit`, `Vollständig angesehen`) with unknown columns kept in `raw_json`; the first real export fixes the map (plan task). Retention curve and watched-full % may only exist on the per-video page → `ndc metrics add` hand entry.
- FYF eligibility: TikTok shows it per post under *More insights* → Overview as „Your post is unavailable to some audiences" / „ineligible for the For You feed" with a reason and appeal link; record `fyf_status` + verbatim reason. TikTok Studio also has *Content Check (Lite)* to pre-check a draft — optional pre-publish step for sensitive topics.
- Due list: `ndc metrics due` compares `posted_at` with now; windows 24 h (20–30 h), 72 h (66–84 h), 7 d (6.5–8 d) — tolerant windows, actual `post_age_hours` stored. Cron on the host (pattern already present: `0 9 * * 0 /usr/bin/docker exec … polymarket-watcher …`): add `*/30 * * * * docker compose -f /home/nd-content/docker-compose.yml run --rm ndc metrics due --write /data/due.json` (or a long-running loop is overkill); the phone UI reads `/data/due.json` (read-only route, no path from request).

### Readout rule (MEAS-01, discretion → research defaults)
- `config/readout_rule.yaml` v1: primary variable pillar (4 arms: challenge_science_help, strengths, parents, men_dads_partners); rotation Latin square P1-P2-P3-P4 / P2-P3-P4-P1 / …; constants held: template 60–75 s, voice, caption style, hashtag scheme v1, posting slot; metrics: saves/1k, shares/1k, follows/1k, completion % (watched_full_pct), views as context; snapshot of record = 7 d (72 h fallback if 7 d missing); minimum exposure 250 views at the snapshot of record; scoring relative to account median (medians, not means); winner = top pillar on composite rank of saves/1k + shares/1k with ≥ 4 of 6 (≥ 5 of 7) videos above the account median on the composite; tie-break completion %; ≥ 2× ratio difference counts as „large"; otherwise „inconclusive"; cross-platform replication reported, not blended; hook tactic logged as exploratory only. Lock: `config/readout_rule.lock` (sha256) written by `ndc readout lock`, refused on change without `ndc readout amend --reason`; the lock row is also stored in a `readout_rule` table with `committed_at` so „before video 1" is provable (publication insert refuses when no lock exists).

### Launch surface (OPS-01/02, LEGAL-02)
- `config/moderation.yaml`: canned replies (crisis disclosure AT/DE/CH, diagnosis request, medication request, „source?" request, hostile/ableist, scam), each ≤ 150 chars for TikTok comments, German, hedged, no diagnosis; keyword filter list; spike protocol numbers (trigger 10× rolling median views of the last 10 posts; 2 sweeps/day for 72 h; restrict comments if sweep capacity exceeded); DM policy restricted; escalation (in-app report for imminent risk). Validate with a pydantic loader like `launch_sets.py`; run `checks.engine.check(reply, "de", "claim")` on every reply (crisis numbers exempt via the existing exemption pattern); render `docs/moderation-playbook.md` with Jinja from the YAML so the doc never drifts from the config.
- Accounts: TikTok **Personal** account (not Business — Business accounts lose Creator tools), YouTube channel with Shorts, Instagram **Professional → Creator** (needed for Graph insights in M2). Settings checklist: comment keyword filter on, „filter spam and offensive" on, DMs restricted, duet/stitch allowed, download off (keeps cross-posts watermark-free when exported via the app's „save without watermark"? — no: record from the source file instead; cross-post the original render, never the TikTok download).
- Handle candidates (German, no clinical words, same on three platforms): e.g. `quellenkopf`, `studienkopf`, `nd.quellen`, `adhs.belegt`, `forschungskurz`, `neurokurz`, `adhs.erklaert`, `kopfsache.studien` — availability must be checked in each app by the operator (programmatic checks hit bot walls; D-16 forbids workarounds).
- Creator Rewards (TikTok): third-party 2026 lists name 8 eligible countries (US, UK, DE, FR, JP, KR, BR, MX); **Austria is not among them** (MEDIUM — no official enumerated list; Effect Creator Rewards is separately available in AT and irrelevant here). Confirm in-app under Creator tools → Creator Rewards and record the screen text.
- YouTube Partner Program: available in Austria; full monetization = 1 000 subscribers + 4 000 public watch hours/12 mo **or 10 M public Shorts views/90 d**; fan-funding tier at 500 subs + 3 uploads/90 d + 3 M Shorts views/90 d; **from 2027-02-01 the bar doubles for new applicants (8 000 h / 20 M Shorts views)** — document both.

### Security / safety (ASVS L1, D-19 carry-over)
- Web UI additions keep the four-route discipline: regex routes `GET /rec/<sha>`, `POST /rec/<sha>/ack`, `POST /rec/<sha>/decide`, `GET /due`; no path from request input; due-list file path is a constant; nonce + Host allow-list unchanged; recording transcripts rendered escaped.
- `publication` insert validates post_url host against an allow-list (tiktok.com, youtube.com/youtu.be, instagram.com) and stores the operator-entered values only; no network calls to platforms (no scraping, D-16).
- Uploaded recordings live under `/data/recordings/`; `ndc recording add` accepts a path inside that directory only (no arbitrary host paths through the container).
</findings>

<validation_architecture>
## Validation Architecture (Nyquist disabled in config — informal)
- Unit tests with a fake transcriber (segments + words fixtures) for alignment statuses, hedge rule, SRT formatting, gate outcomes, publish-log refusal paths, due-window maths, CSV column mapping, readout lock refusal. Live checks in the 03-LIVE-RUN: one real take through the whole chain, timed; one real TikTok CSV import.
</validation_architecture>

## Sources
- Repo: `src/ndc/scan/transcribe.py`, `scan/pitch.py`, `script/verify.py`, `review/{gate,store,web}.py`, `schema/008_ledger.sql`, `009_review.sql`, `scan/prereg.py`, `config/decision_rule.yaml`, host crontab (polymarkt pattern)
- `.planning/research/FEATURES.md` §Validation Experiment Design; `PITFALLS.md` Pitfalls 1, 9, 10, launch checklist; `STACK.md` (faster-whisper large-v3, TikTok CSV 60-day window)
- Web (2026-10-29, MEDIUM): TikTok Creator Rewards eligible countries 2026 (ttcalculator.net, shortsync.app — third-party); YouTube Partner Program requirements 2026 and the 2027-02-01 change (support.google.com/youtube/answer/13429240, vidiq.com, ppc.land); TikTok FYF ineligibility label under More insights and Content Check Lite (shortimize.com, conductatlas.com); TikTok Studio export scope (third-party tool docs — column names unverified)
