# nd-content — faceless neurodivergence short-form account

## What This Is

A faceless short-form video account (TikTok first, cross-posted to YouTube Shorts and Instagram Reels) in the
health → mental health → neurodivergence niche (ADHD/ADHS, autism). The voice is the operator's own (male,
Austrian), positioned as "not a therapist — I read the research and translate it, with sources". The audiences
are neurodivergent adults, parents of ND children, and an early bet on men, dads and partners. The end goal is
monetization. Production should eventually be fully automated, with human judgment kept as a ~10 min/day review
gate: "automate production, not judgment".

## Core Value

Every video makes only claims grounded in a retrieved, citable source, and the sources are shown. Credibility is
the whole moat for an anonymous, non-clinician health account. If fact-grounding fails, nothing else matters.

## Milestone 1 scope (v1): Validation + light tooling

Prove which format gets traction before building any automation. The full automation pipeline is **milestone 2**,
built only for the formats that win here.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Competitor scan of the ADHS (German/DACH) vs ADHD (English) landscape: account count, size and
      source-citing practice, leading to a data-backed language decision in validation week 1
- [ ] Style guide plus content matrix: pillars × condition × domain × audience × angle, with the conservative topic
      whitelist and a blacklist
- [ ] Light script helper: Claude drafts a 60–75s script with a hook from retrieved sources only (reviews,
      S3/AWMF guidelines, PubMed)
- [ ] Adversarial fact-check pass that outputs claim ↔ source-sentence pairs for operator review, plus the source
      list formatted for the caption or pinned comment
- [ ] 24–28 manually recorded and published videos at 4–5/week (batched), rotating pillars on a pre-planned
      schedule
- [ ] Safety tooling in M1: automatic DOI/PMID check, terminology word-list check, Whisper final-recording diff vs
      approved script, crisis/moderation playbook before the first post
- [ ] Per-video metrics log (retention/watch-through, shares, saves, views, follows) tagged by pillar/angle/hook
- [ ] Go/no-go readout: the top 1–2 pillar/angle formats by retention/saves/shares relative to the account's own
      median, which feeds milestone 2
- [ ] Austrian legal/tax checklist (Impressum MedienG §25/ECG §5, AMG/UWG/EU Health Claims, trade/tax
      registration, Creator Rewards availability in AT, AI labeling), resolved before any monetization

### Out of Scope (milestone 1)

- Automated end-to-end pipeline (Remotion render, Whisper captions, TTS, scheduler publishing, Telegram approve
  card, analytics feedback loop): milestone 2, and only for formats with traction
- Auto-replying to comments: never, because of mental-health crisis risk
- Faked female AI persona / AI voice as the primary voice: the operator's own voice is the differentiator
- Topics on medication, diagnosis questions, ABA, or "is my child autistic?": conservative whitelist at first
- Monetization offers for supplements, telehealth or medication: credibility and legal risk
- Monetization itself (products, affiliates, sponsorships, email list): only after traction plus the legal
  checklist
- Clinician-led content or a credentials claim: there is no clinician; positioning is translator-of-research

## Content pillars

1. **Challenge + science + help**: "Some people with ADHD experience X" → short scientific explanation → how the
   environment can help / how the person can handle it → how it can be a strength.
2. **Strengths**: strengths neurodivergent people often have.
3. **Parents of ND children**: how parents can handle situations (highest-value audience).
4. **Early bet**: ADHD in men, dads of ND kids, partners of people with ADHD.

Tone: neurodiversity-affirming, hedged ("some people…"), never diagnostic.

## Context

- Seed brief: `PROJECT-BRIEF.md` (decisions made with the operator on 2026-10-16).
- The operator is Austrian, comfortable reviewing English papers, and records in Austrian standard German or
  English. The assistant leans German (less competition, native voice, S3/AWMF guidelines); the competitor scan
  decides.
- Lived-experience stories come anonymized and with consent from the operator's circle.
- Monetization paths, later: platform payouts, own digital products (parent guides, routine toolkits), ND app
  sponsorships, book/planner/app affiliates, email list.
- Target automation architecture (milestone 2): topic backlog (SQLite matrix + Reddit/trend input) → grounding
  → script → fact-check → voice (operator recording; TTS fallback) → visuals + captions (Remotion, Whisper word
  timestamps) → render → Telegram approve/reject card → publish (Metricool/Buffer/Blotato; the TikTok Content
  Posting API needs an app audit) → analytics feedback into topic selection.
- Runs on the same Linux box as polymarkt-watch (Docker), in a separate repo and with separate infra.

## Constraints

- **Operator time**: ~30–60 min/day during validation, so tooling must keep script + fact-check review fast.
- **Budget**: ~$30–80/month at full automation; well below that during validation.
- **Safety**: never diagnostic, no auto-replies, conservative topic whitelist, sources on every video.
- **Legal (Austria, not legal advice)**: faceless ≠ anonymous (Impressum duty); health-claim/advertising rules;
  verified with WKO/Steuerberater before monetization.
- **Infra**: Docker on the shared polymarkt-watch host; must not interfere with that system's resources.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Milestone 1 = validation + light tooling; automation is milestone 2 | Automate only formats with proven traction | — Pending |
| Traction = relative winners (top 1–2 formats vs own median on retention/saves/shares) | No arbitrary absolute bar on a brand-new account | — Pending |
| Language decided by data in week 1 (ADHS vs ADHD competitor scan) | German leaning, but the market decides | — Pending |
| Operator's own male voice, no AI persona | Authenticity; differentiator for the men/dads pillar | — Pending |
| Positioning: "not a therapist, I translate research with sources" | No clinician; credibility comes from sourcing | — Pending |
| Claims grounded only in retrieved sources + adversarial verification + operator review | Core value: credibility | — Pending |
| Never auto-reply to comments | Mental-health crisis risk | — Pending |
| Legal/tax checklist (incl. Impressum) gates monetization, not the first post | Operator accepted the risk while non-commercial; research flagged MedienG §25 may apply from the first regular post | ⚠️ Revisit |
| Cadence 4–5/week batched, not daily | Real cost is 60–120 min/video; burnout risk | — Pending |
| Keep the fixed 60–75s template; verify Creator Rewards in-app | Creator Rewards likely unavailable in AT; a fixed template keeps the experiment clean | — Pending |
| Model IDs live in config | The lineup changes; never hard-code | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-24 after initialization*
