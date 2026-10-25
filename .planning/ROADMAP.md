# Roadmap: nd-content

## Overview

Milestone 1 tests which content format gets traction before any automation is built. The work runs in four
steps:

1. Decide the language from competitor data and lay down the content rules: matrix, style guide, terminology
   and safety filter.

2. Build the grounded script chain: sources, then a cited script, then an adversarial fact-check, then a
   hash-bound review, then the source list.

3. Get everything ready for launch before video 1: recording diff, crisis playbook, accounts, a pre-registered
   readout rule and the metrics log.

4. Run the 24–28-video validation and read out the top 1–2 formats as the input for milestone 2.

## Phases

- [ ] **Phase 1: Market Decision & Content Foundation** - Language chosen from competitor data; topic matrix, style guide, terminology check and safety filter in place
- [ ] **Phase 2: Grounded Script Pipeline** - A topic goes in; a cited, adversarially fact-checked, operator-approved script and its rendered source list come out
- [ ] **Phase 3: Launch Readiness & First Publish** - Recording diff, crisis playbook, accounts, pre-registered readout and metrics log all exist, and video 1 is published and logged
- [ ] **Phase 4: Validation Run & Go/No-Go** - 24–28 videos published on the rotation, readout names the winning formats (or "inconclusive"), and the monetization legal checklist is resolved

## Phase Details

### Phase 1: Market Decision & Content Foundation

**Goal**: The operator knows which language the account runs in, backed by data, and has a browsable, safety-tagged topic backlog plus mechanical checks for terminology and blacklisted subjects
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: MKT-01, MKT-02, MKT-03, CONT-01, CONT-02, CONT-03, CONT-04
**Success Criteria** (what must be TRUE):

  1. A language decision rule is committed before the scan, a filled competitor sheet for ADHS (DACH) and ADHD (English) accounts exists with every MKT-01 field recorded, and the decision plus its reasoning is logged in validation week 1
  2. A fixed hashtag/keyword set and a crisis-line set exist for the chosen language
  3. Operator can list and filter the SQLite topic matrix by pillar, condition, domain, audience and angle, and each topic shows a whitelist or blacklist tag
  4. Running the checker on a sample script flags the terminology violations from the DE+EN table (functioning labels, "superpower", "leidet an", "Asperger" outside quotes, ABA-adjacent framing)
  5. The safety filter rejects a blacklisted subject (medication, diagnosis question, ABA, "is my child autistic?") at topic level and again when it appears in script or claim text; the style guide documents the fixed 60–75s template

**Plans:** 13/15 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Walking skeleton: uv + Typer `ndc` + SQLite topic add/list in a memory-capped, port-free container (W1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — `ndc check`: DE+EN terminology (two tiers, hash-bound overrides), safety filter, style guide; operator approval (W2)
- [x] 01-03-PLAN.md — Pre-registered language decision rule + `decide` + hash guard; operator approval and commit before any scan (W2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — Scan tooling: D-16 discovery (live-verified), polite fetch, stratified selection, competitor sheet export (W3)
- [x] 01-05-PLAN.md — Topic matrix tooling: vocab, safety-checked import, filters, keep/kill, select guard, stats (W3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-06-PLAN.md — Local video analysis (Whisper, pitch, contact sheets) + in-session judgment import with evidence guard + operator verify (W4)
- [x] 01-07-PLAN.md — Scan run 1: discovery + followers + ~80-account sample; operator confirms list (W4)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-08-PLAN.md — Scan run 2: posts + local analysis + judging batches (W5)

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 01-09-PLAN.md — In-session judging batch de-1 (W6)
- [x] 01-10-PLAN.md — In-session judging batch de-2 (W6)
- [x] 01-11-PLAN.md — In-session judging batch en-1 (W6)
- [x] 01-12-PLAN.md — In-session judging batch en-2 (W6)

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 01-13-PLAN.md — Operator spot-check of the uncertainty queue; language decision + competitor sheet (W7)

**Wave 8** *(blocked on Wave 7 completion)*

- [ ] 01-14-PLAN.md — Hashtag/keyword set + crisis-line set for the chosen language; operator in-app check (W8)
- [ ] 01-15-PLAN.md — Topic seed (~60–80, chosen language) import + operator prune; backlog snapshot (W8)

**Cross-cutting constraints:**

- Judgments follow config/judging_rubric.md: source-citing 0–3 from captions and pinned comments plus spoken/on-screen citations from transcripts and contact sheets (D-01, D-17)
- Because this is a DACH batch, every account whose speech or on-screen evidence would lift its score to >= 2, and every faceless male-voiced account scoring >= 2, is in the operator queue — these decide N_DE and S_DE (D-06, D-17)
- Every faceless male-voiced account scoring >= 2 is in the operator queue — these decide S_EN, which drives rule R3 (D-17, D-20)

### Phase 2: Grounded Script Pipeline

**Goal**: For any whitelisted topic, the operator can produce a script in which every claim traces to a stored source sentence. The script is adversarially checked, approved by the operator in ≤10 min, and ships with a source list that no model wrote
**Mode:** mvp
**Depends on**: Phase 1 (topic matrix, language, terminology and safety checks)
**Requirements**: SRC-01, SRC-02, SRC-03, SRC-04, SCR-01, SCR-02, SCR-03, SCR-04, SCR-06
**Success Criteria** (what must be TRUE):

  1. Operator retrieves PubMed/Europe PMC candidate sources for a topic (reviews and guidelines first) and imports an AWMF S3 PDF with its version/validity recorded. Each source is stored as an immutable, content-hashed snapshot split into numbered sentences with PMID/DOI metadata
  2. Operator generates a 60–75s script with a hook from those sources only, with each claim cited to source-sentence IDs. A fake or mismatched DOI/PMID blocks the script
  3. A separate verifier model labels each claim supports / partial / overstated / unsupported / contradicts and flags certainty escalation. The operator reviews the claim ↔ source-sentence pairs sorted by risk and approves them, and the approval is bound to the script hash: editing the script voids it
  4. The caption / pinned-comment source list is rendered only from stored source records
  5. Model IDs and prompts come from config, and each LLM call appears in a log with model, prompt hash, inputs and output

**Plans**: TBD

### Phase 3: Launch Readiness & First Publish

**Goal**: Everything that must exist before video 1 is in place, and the first video goes out through the full chain with its recording verified and its metrics captured from day one
**Mode:** mvp
**Depends on**: Phase 2 (approved scripts, source lists, script hashes)
**Requirements**: SCR-05, OPS-01, OPS-02, MEAS-01, MEAS-02, MEAS-03, LEGAL-02
**Success Criteria** (what must be TRUE):

  1. A written crisis/comment-moderation playbook exists before the first post (manual-only moderation, AT/DE hotlines such as 142/147/TelefonSeelsorge, spike protocol), and no auto-reply is configured anywhere
  2. The TikTok Personal account and the YouTube Shorts/Instagram Reels accounts are live with a bio and sourcing statement. Creator Rewards eligibility in AT has been checked in-app and the YouTube Partner Program path is documented
  3. The go/no-go readout rule (pillar as primary variable, ≤4–6 arms, rate metrics, winner vs inconclusive thresholds) is committed before video 1 is posted
  4. The Whisper transcript of the operator's recording is diffed against the approved script, and any deviating sentence is fact-checked before publishing
  5. Video 1 is logged at publish time (platform, post id, topic, pillar/angle/hook, script hash), and its 72h and 7d metric snapshots are recorded (views, retention, saves, shares, follows, For You eligibility)

**Plans**: TBD

### Phase 4: Validation Run & Go/No-Go

**Goal**: The validation experiment is complete, and the operator has a pre-registered, data-backed answer on which 1–2 formats (if any) milestone 2 should automate. The legal path to monetization is cleared
**Mode:** mvp
**Depends on**: Phase 3 (published pipeline, metrics log, readout rule)
**Requirements**: OPS-03, MEAS-04, LEGAL-01
**Success Criteria** (what must be TRUE):

  1. 24–28 videos are published at 4–5/week from batched production, following the pre-planned pillar rotation. Each one has a publish log entry and its fixed-age snapshots
  2. A readout report ranks formats against the account's own median on rate metrics, applies the pre-registered rule, and names the top 1–2 formats or "inconclusive" as the milestone-2 input
  3. The legal/tax checklist (Impressum MedienG §25/ECG §5, AMG/UWG/HWG/EU 1924/2006, protected titles, trade/tax registration, AI labeling) is resolved with WKO/Steuerberater, with outcomes recorded, before any monetization step

**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Market Decision & Content Foundation | 13/15 | In Progress|  |
| 2. Grounded Script Pipeline | 0/? | Not started | - |
| 3. Launch Readiness & First Publish | 0/? | Not started | - |
| 4. Validation Run & Go/No-Go | 0/? | Not started | - |
