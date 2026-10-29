# Phase 3: Launch Readiness & First Publish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-29
**Phase:** 03-launch-readiness-first-publish
**Areas discussed:** Recording → publish chain, Publish log + metric snapshots, Launch surface (accounts, bio, legal, moderation)
**Not selected:** Readout rule (pre-registered) → Claude's discretion on research defaults

---

## Recording → publish chain

| Option | Description | Selected |
|---|---|---|
| Fuzzy per sentence | Align spoken to approved sentence; fillers/word order/ASR slips pass a similarity threshold; claim changes, dropped hedges, new sentences are deviations | ✓ |
| Only new or changed claims | Framing may be improvised; only cited/claim sentences compared | |
| Exact match | Every sentence must match after normalization | |

| Option | Description | Selected |
|---|---|---|
| Verify + approve the recording | Deviating sentences → existing verifier; ack/fix on phone; transcript gets hash-bound approval; publish log blocks without it | ✓ |
| Warn only | Diff shown, operator decides, override logged | |
| Always re-record | Any deviation → new take | |

| Option | Description | Selected |
|---|---|---|
| Topic 3: Starke Gefühle (v7) | Approved, stronger script | ✓ |
| Topic 2: Anfangen (v11) | Approved but judged clumsy/technical | |
| Fresh draft on another pillar | Start rotation on strengths/parents, one more draft cycle | |

| Option | Description | Selected |
|---|---|---|
| Whisper SRT from ndc + phone editor | Word-timed SRT from the diffed transcript; import into CapCut/TikTok | ✓ |
| Platform auto-captions, corrected by hand | Zero tooling, captions not tied to verified transcript | |
| You decide | | |

**Notes:** none beyond the selections.

---

## Publish log + metric snapshots

| Option | Description | Selected |
|---|---|---|
| CLI + TikTok CSV import | `ndc publish log`, `ndc metrics import` (TikTok Studio CSV), hand entry for missing fields; phone UI review-only | ✓ |
| Phone UI forms | Forms in the review web app | |
| Spreadsheet, imported later | | |

| Option | Description | Selected |
|---|---|---|
| TikTok full, YouTube/Instagram views only | Readout on TikTok; cross-posts keep post id + views | ✓ |
| All three in full | | |
| TikTok only | | |

| Option | Description | Selected |
|---|---|---|
| `ndc metrics due` + daily cron note | Due list written to a file shown in the phone UI | ✓ |
| Telegram ping | Separate bot (M2 pulled forward) | |
| No reminders | | |

| Option | Description | Selected |
|---|---|---|
| 24 h + 72 h + 7 d, FYF yes/no/unknown | Extra 24 h point; eligibility with free-text reason | ✓ |
| 72 h + 7 d only | | |
| You decide | | |

---

## Launch surface: accounts, bio, legal, moderation

| Option | Description | Selected |
|---|---|---|
| Disclose from video 1 via bio link | Small-medium MedienG §25 disclosure page within two clicks | |
| Disclose via an address service | c/o address, small monthly cost | |
| Keep accepting the risk until monetization | Documented operator decision; revisit in Phase 4 with WKO | ✓ |

| Option | Description | Selected |
|---|---|---|
| „Kein Therapeut. Ich lese die Forschung zu ADHS & Autismus und übersetze sie – mit Quellen." | Mirrors positioning line | |
| „ADHS & Autismus, erklärt aus Studien. Keine Diagnosen, keine Therapie – Quellen in jedem Video." | Topic first, two boundaries, sources promise | ✓ |
| „Was die Forschung über ADHS & Autismus weiß – kurz, ehrlich, mit Quellen. Nicht diagnostisch." | Softer tone | |

| Option | Description | Selected |
|---|---|---|
| Research protocol as written | Canned human replies w/ hotlines, keyword filters, pinned resources, spike protocol at ~10× median (2 sweeps/day for 72 h or restrict) | ✓ |
| Stricter: hold all comments for approval | | |
| Lighter: filters + pinned resources only | | |

| Option | Description | Selected |
|---|---|---|
| I already have them | | |
| Propose candidates | Planner proposes 5–8 German handles, availability-checked on all three platforms | ✓ |
| Decide during execution | | |

**Notes:** Operator asked mid-discussion to push the repo to a new GitHub remote (github.com/kevschuetz/ndtiktok); remote added, push blocked on credentials (operator to run `git push -u origin master`).

## Claude's Discretion
- Readout rule content and lock mechanism (research defaults), diff similarity metric/threshold, transcript hash, SRT format, CSV mapping, schema, cron cadence, canned-reply wording (operator approves the file).

## Deferred Ideas
- Telegram reminders/approve card (M2); phone-UI forms for logging; Impressum page / address service (Phase 4); hook A/B re-cuts (after readout); full YT/IG snapshots + Instagram Graph API (M2).
