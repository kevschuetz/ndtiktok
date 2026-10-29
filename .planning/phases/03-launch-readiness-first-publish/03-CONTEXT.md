# Phase 3: Launch Readiness & First Publish - Context

**Gathered:** 2026-10-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Everything that must exist before video 1 is in place, and video 1 goes out through the full chain: the operator's recording is transcribed and diffed against the approved script, deviations are verified and the recording approved, the post is logged at publish time, and its 24 h / 72 h / 7 d metric snapshots are captured. Before that: crisis/moderation playbook (no auto-reply anywhere), live accounts with bio + sourcing statement, Creator Rewards / YouTube Partner Program check, and the pre-registered go/no-go readout rule committed in the repo. Requirements: SCR-05, OPS-01, OPS-02, MEAS-01, MEAS-02, MEAS-03, LEGAL-02. Not in scope: the 24–28-video run and the readout report (Phase 4), monetization, Remotion/TTS/scheduler automation (M2), Telegram cards (M2).

</domain>

<decisions>
## Implementation Decisions

### Recording → publish chain (SCR-05)
- **D-01:** Deviation rule is **fuzzy per sentence**: each spoken sentence of the Whisper transcript is aligned to its approved sentence (same `script_version`); fillers, word order and ASR slips on Austrian German pass under a similarity threshold (planner/researcher pick the metric and threshold and calibrate on the first real take). Sentences that change the wording of a claim, drop or weaken a hedge, or have no counterpart in the approved text are deviations. Framing lines are compared too, but only a smuggled claim matters there.
- **D-02:** On deviation: the deviating sentences run through the **existing verifier** (`script/verify.py`) against the script's locked corpus; the operator acks or fixes on the phone; the recording transcript gets its **own hash-bound approval** (same `review`/`claim_ack` pattern keyed on a transcript hash, channel web/cli). The publish log refuses an entry whose recording is not approved. No deviation → the recording approval is granted automatically with the diff result stored.
- **D-03:** Video 1 = **topic 3 „Starke Gefühle bei ADHS", script version 7** (sha `fd07bd2c…`, approved 2026-10-26, challenge+science+help pillar).
- **D-04:** Captions: `ndc` produces a **word-timed SRT from the same Whisper transcript it diffs**; the operator imports the SRT into CapCut/TikTok and adds simple visuals on the phone. No Remotion in M1. The SRT text is the approved recording transcript, so captions never drift from what was verified.
- Recording file handoff: operator copies the take (audio or video) to the data volume; `ndc` transcribes it in the `ndc-heavy` container (faster-whisper already installed, `src/ndc/scan/transcribe.py`), outside quiet hours.

### Publish log + metric snapshots (MEAS-02, MEAS-03)
- **D-05:** Entry is **CLI-first**: `ndc publish log` at post time (platform, post id/url, topic, pillar, angle, hook tactic, script sha, recording sha, posted_at), `ndc metrics import` for the TikTok Studio CSV export, hand entry (`ndc metrics add`) only for fields the CSV lacks (retention / watched-full %, FYF status). The phone UI stays review-only in this phase.
- **D-06:** Platforms: **TikTok gets full snapshots**; YouTube Shorts and Instagram Reels cross-posts are logged with post id + views only (readout runs on TikTok, consistent with Phase-1 D-18).
- **D-07:** Reminders: `ndc metrics due` lists videos whose snapshot window is open; a **daily cron** (inside the box, no new messaging channel) writes the due list to a file the phone review UI shows. No Telegram in M1.
- **D-08:** Snapshot ages **24 h, 72 h, 7 d** (fixed-horizon windows with tolerance, actual post age stored). Fields: views, completion/retention, average watch time if visible, saves, shares, comments, follows, **For-You-feed eligibility as yes / no / unknown plus free-text reason** (TikTok post status / analytics wording).

### Launch surface (OPS-01, OPS-02, LEGAL-02)
- **D-09 (operator, conscious risk):** MedienG §25 disclosure **stays deferred until monetization**. Research says the duty applies from the first regular post; the operator keeps accepting that risk for the non-commercial validation run. Record as an explicit operator decision; revisit with WKO in Phase 4 (LEGAL-01). Plans must not add an Impressum page or address-service step.
- **D-10:** Bio sourcing statement (all three platforms, German): **„ADHS & Autismus, erklärt aus Studien. Keine Diagnosen, keine Therapie – Quellen in jedem Video."** This carries the disclaimer that D-22 (Phase 2) removed from the script.
- **D-11:** Moderation = **research protocol as written** (PITFALLS.md Pitfall 10): canned, human-sent, non-diagnostic German replies pointing to AT 142 / 147, DE 0800 111 0 111, CH 143, emergency 144/112 (numbers from `config/crisis_lines.yaml`, re-verified before launch); platform keyword filters on (slurs, scam links, „DM für Diagnose"); pinned source comment with the crisis short form on sensitive topics; **spike protocol at ~10× the account's median views: two comment sweeps a day for 72 h or temporary comment restriction**. Never auto-reply (project rule).
- **D-12:** Handles: the plan **proposes 5–8 German handle candidates** that fit the positioning (same name on TikTok, YouTube, Instagram; no implied clinical expertise; no „Dr./Therapie" words), checks availability on all three platforms, and the operator picks one before account creation. Accounts: TikTok Personal, YouTube channel, Instagram Professional (Creator) — the latter so Graph-API insights stay possible in M2.
- **D-13:** Creator Rewards eligibility is checked **in-app** by the operator and the result recorded in the repo (research expects Austria to be ineligible); the YouTube Partner Program path (thresholds, AT availability) is documented in the same doc. Neither changes the 60–75 s template in this milestone.

### Claude's Discretion
- **Readout rule (MEAS-01)** — operator did not select this area; adopt the research defaults from `.planning/research/FEATURES.md` §Validation design and commit them as `config/readout_rule.yaml` (+ lock hash, like `decision_rule.lock`) before video 1: pillar is the only primary variable (4 arms), balanced Latin-square rotation, rate metrics saves/1k, shares/1k, follows/1k and completion %, snapshots at fixed horizons (D-08), minimum-exposure filter ~200–300 views, relative-to-own-median scoring with medians, winner = top pillar on the saves+shares composite with ≥4/6 (or ≥5/7) videos above the account median, tie-break completion %, everything else „inconclusive". Hook testing is a later, smaller phase.
- Similarity metric/threshold for D-01, transcript hash definition, SRT formatting, CSV column mapping for `ndc metrics import`, cron cadence, exact DB schema (follow the Phase-2 ledger patterns: append-only, content-hashed, channel-agnostic review rows).
- Whether the recording approval reuses the `review` table with a new subject kind or a sibling table — keep the gate logic shared.
- Canned-reply wording (German, hedged, no diagnosis) drafted from the style guide; operator approves the playbook file like the hashtag/crisis sets.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Validation design, risks, legal
- `.planning/research/FEATURES.md` §Validation design (Latin-square rotation, rate metrics, minimum exposure, relative-to-median scoring, pre-registration) — source of the readout-rule defaults
- `.planning/research/PITFALLS.md` — Pitfall 1 (fact-check the final transcript), Pitfall 9 (MedienG §25 timing; operator deferral D-09), Pitfall 10 (comment crisis playbook, spike protocol), launch checklist
- `.planning/research/SUMMARY.md` — Creator Rewards / Austria caveat, 4–6 comparable cells
- `.planning/PROJECT.md` Key Decisions — never auto-reply; legal checklist gates monetization (⚠️ Revisit → resolved as D-09 for this phase)

### Existing config to reuse
- `config/crisis_lines.yaml` — verified AT/DE/CH numbers + pinned short form (re-verify before OPS-01)
- `config/hashtags.yaml` — approved German hashtag scheme for captions
- `config/style_guide.md` — template, hedge vocabulary, caption/pinned-comment rules
- `config/decision_rule.yaml` + `config/decision_rule.lock` — the pre-registration pattern to copy for the readout rule
- `config/source_list.yaml` — caption/comment source list rendering (already live)

### Phase-2 contracts this phase builds on
- `.planning/phases/02-grounded-script-pipeline/02-CONTEXT.md` — D-14..D-19 (gate, hash-bound approval, review channels, web-UI security rules), D-22 (disclaimer lives in bio + caption)
- `docs/script-pipeline.md` — operator runbook; Phase 3 adds a „Aufnahme → Veröffentlichung" section
- `.planning/phases/02-grounded-script-pipeline/02-LIVE-RUN.md` — the approved topic-3 v7 / topic-2 v11 evidence

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ndc/scan/transcribe.py` + `ndc-heavy` compose service (faster-whisper 1.2.1, CPU int8, niced, quiet hours): transcription for the recording diff and the SRT; use `large-v3` for Austrian German per STACK.md.
- `src/ndc/sources/split.py` (`normalize`, `split_sentences`) and `script_sentence` rows with `sha256`: the approved side of the diff is already sentence-split and hashed.
- `src/ndc/script/verify.py` (`verify(only_ordinals=…)`, forced rules) and `src/ndc/review/{gate,store}.py`: verify deviating sentences and bind the recording approval to a hash with the same `BEGIN IMMEDIATE` + `is_latest` pattern.
- `src/ndc/review/web.py` / `web_render.py`: four-route, secret-free phone UI — add read-only views (recording diff, due snapshots) only under the D-19 rules (no static handler, regex routes, Host allow-list, nonce on POST).
- `src/ndc/launch_sets.py` loads `crisis_lines.yaml` / `hashtags.yaml`; `src/ndc/checks/engine.py` checks canned replies and bio text for terminology/safety (crisis lines are exempt).
- `src/ndc/scan/quiet_hours.py`, `scan/media.py` (yt-dlp) — patterns for heavy, polite jobs.
- `config/llm.yaml` + `src/ndc/llm.py` — any LLM use (verifier) stays logged there; no new API surface.

### Established Patterns
- Append-only, content-hashed ledger tables with SQLite triggers; a new text = new version = new hash; approvals key on the hash.
- Channel-agnostic `review` rows (cli / web / telegram) so M2's Telegram card is a channel swap.
- Pre-registered config files locked with a sha256 `.lock` and refused on silent change (`scan/prereg.py`).
- CLI-first with Typer; phone UI only for judgment, never for editing.
- Everything runs in Docker on the shared host; heavy CPU work niced and outside 00:15–06:00 UTC; cron inside the box.

### Integration Points
- New tables: `recording` (file sha, transcript, model, created_at), `recording_sentence` + diff result, recording approval (reuse `review` with subject kind or sibling), `publication` (publish log), `metric_snapshot`, `readout_rule` lock.
- `ndc publish log` must check: script approved, recording approved for that script sha, source list rendered.
- Cron → due-list file under `/data` → phone UI read-only route.
- Runbook `docs/script-pipeline.md` gets the recording/publish/metrics sections; `docs/moderation-playbook.md` (or `config/moderation.yaml` + rendered doc) holds canned replies and the spike protocol.

</code_context>

<specifics>
## Specific Ideas

- Operator priorities: fast phone-side judgment, minimal laptop time, TikTok engagement without loosening grounding; they found the topic-2 script „too technical/detailed" — Phase 3 may include one prompt-craft pass on `draft_de.md`/`editor_de.md` (fewer numbers and test names, more everyday language) before recording more scripts, plus the 02-REVIEW follow-ups (hidden_claim rule, `custom` facet warning, „kein Tipp ohne Marker").
- Deferred human action carried in: import the real AWMF S3 ADHS PDF (028-045) once the operator uploads it (`ndc source import-awmf … --status abgelaufen`).
- Operator works inline with Claude (no subagents) and reviews from the phone through the Pi (`NDC_REVIEW_ALLOWED_HOSTS`).

</specifics>

<deferred>
## Deferred Ideas

- Telegram snapshot reminders / approve card — milestone 2 (AUTO-02).
- Phone-UI forms for publish log and metrics — only if CLI + CSV import proves too slow.
- Impressum page / address service — Phase 4 with the LEGAL-01 WKO consultation (operator decision D-09).
- Hook A/B re-cuts on the winning pillar — after the Phase-4 readout.
- Full snapshots for YouTube/Instagram and the Instagram Graph API — M2.

</deferred>

---

*Phase: 03-launch-readiness-first-publish*
*Context gathered: 2026-10-29*
