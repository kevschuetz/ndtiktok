# Project brief — faceless neurodivergence content account (working name: nd-content)

Seed input for `/gsd-new-project`. Decisions below were made with the operator on 2026-10-16.

## Goal
A faceless short-form video account (TikTok first, cross-posted to YouTube Shorts + Instagram Reels)
in the health → mental health → neurodivergence niche. Ultimate goal: monetization. Target: production
fully automated; human judgment kept as a ~10 min/day review gate ("automate production, not judgment").

## Content pillars
1. **Challenge + science + help** — "Some people with ADHD experience X" → short scientific explanation
   → how the environment can help and/or how the person can handle it → how it can be a strength.
2. **Strengths** — strengths neurodivergent people often have.
3. **Parents of neurodivergent children** — how parents can handle situations (highest-value audience).
4. **Extra pillar (early bet):** ADHD in men, dads of ND kids, partners of people with ADHD.

Tone: neurodiversity-affirming, hedged ("some people…"), never diagnostic.

## Decisions
- **Language:** decide by data in validation week 1 — competitor scan of ADHS (German/DACH) vs ADHD
  (English): account count, size, source-citing. Operator is Austrian; assistant leans German
  (less competition, native voice, S3/AWMF guidelines), operator comfortable reviewing English papers.
- **Voice:** operator records own voice (male, Austrian standard German or English). No faked female
  AI persona. Male voice = differentiator for the men/dads pillar.
- **Credibility:** no clinician. Positioning: "not a therapist — I read the research and translate it,
  with sources". Anonymized, consented lived-experience stories from operator's circle.
- **Fact-checking:** claims grounded only in retrieved sources (reviews, guidelines incl. S3-Leitlinien
  ADHS/Autismus, PubMed). Adversarial LLM verification pass; operator reviews claim ↔ source-sentence pairs.
  Conservative topic whitelist initially: no medication, no diagnosis questions, no ABA, no "is my child autistic?".
  Sources in caption/pinned comment every video.
- **Comments:** never auto-reply (mental-health crisis risk).
- **Monetization (beyond platform payouts):** own digital products (parent guides, routine toolkits),
  ND app sponsorships, book/planner/app affiliates, email list. Avoid supplements, telehealth, medication offers.

## Sequencing
1. **Phase 1 — manual validation (2–3 weeks):** competitor scan → language decision; Claude-assisted scripts,
   operator records, ~20–30 videos across pillars/angles; measure retention/shares/saves per angle.
2. **Then automation** only for formats that got traction.

## Target automation architecture (later phases)
Topic backlog (matrix: condition × domain × audience × angle + Reddit/trend input, SQLite)
→ grounding/retrieval → script (Claude, style guide, hook, 60–75s)
→ fact-check pass → voice (operator recording; TTS fallback) → visuals + captions
(Remotion, Whisper word timestamps, stock/illustration) → render
→ Telegram approve/reject card (video + script + sources)
→ publish (scheduler API, e.g. Metricool/Buffer/Blotato; TikTok Content Posting API needs app audit)
→ analytics feedback into topic selection.
Runs on the same Linux box as polymarkt-watch (Docker). Est. cost ~$30–80/month.

## Open items to verify (Austria, not legal advice — check WKO / Steuerberater)
- Offenlegung/Impressum: MedienG §25 + ECG §5 — faceless ≠ anonymous; consider Impressum/address service.
- Health advertising: AMG (drug ads), UWG (misleading claims), EU Health Claims Reg. 1924/2006; German rules
  may apply to ads targeting German viewers.
- Tax/trade registration for creator income in Austria.
- Whether TikTok Creator Rewards Program is available in Austria.
- AI-content labeling rules (TikTok) for any AI-generated visuals/voice.
