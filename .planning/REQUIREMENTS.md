# Requirements: nd-content

**Defined:** 2026-10-24
**Core Value:** Every video makes only claims grounded in a retrieved, citable source — and shows the sources.

## v1 Requirements (Milestone 1 — validation + light tooling)

### Market & language

- [x] **MKT-01**: Operator has a competitor-scan sheet for ADHS (DACH) vs ADHD (English) accounts recording, per account: median views of last 15 posts, source-citing score (0–3), face/faceless, voice gender, format, cadence, pillars covered, monetization
- [x] **MKT-02**: The language decision rule is written down before the scan, and the language is decided from the scan data in validation week 1
- [x] **MKT-03**: Hashtag/keyword set and crisis-line set are fixed for the chosen language

### Content foundation

- [x] **CONT-01**: Operator can browse a topic matrix (pillar × condition × domain × audience × angle) stored in SQLite, each topic tagged whitelist/blacklist
- [x] **CONT-02**: A style guide defines the fixed video template (60–75s, hook in first 1–2s spoken + on-screen, one topic per video, hedged non-diagnostic tone, calm visuals, burned-in accurate captions)
- [x] **CONT-03**: A German+English terminology table exists, and every script is automatically checked against it (bans functioning labels, "superpower" hype, "leidet an", "Asperger" outside quotes, ABA-adjacent framing; identity-first default)
- [x] **CONT-04**: The safety filter rejects blacklisted subjects (medication, diagnosis questions, ABA, "is my child autistic?") at topic, script and claim level

### Sources & retrieval

- [x] **SRC-01**: Operator can retrieve candidate sources for a topic from PubMed (reviews/guidelines first) and Europe PMC, cached with citation metadata (PMID/DOI)
- [ ] **SRC-02**: Operator can manually import AWMF S3 guideline PDFs (ADHS, Autismus), with the version/validity status recorded
- [x] **SRC-03**: Each source is stored as an immutable, content-hashed snapshot split into addressable sentences
- [ ] **SRC-04**: Every cited DOI/PMID is automatically checked against Crossref/PubMed; an unresolvable or mismatched identifier blocks the script

### Script & fact-check

- [x] **SCR-01**: Operator can generate a 60–75s script with a hook for a topic, using only the retrieved sources (Claude Citations), with each claim cited to source sentences
- [x] **SCR-02**: A separate adversarial verification pass (different model, structured output) classifies every claim (supports / partial / overstated / unsupported / contradicts) and flags any certainty escalation vs the source
- [ ] **SCR-03**: Operator reviews claim ↔ source-sentence pairs sorted by risk, in ≤10 min per script, and the approval is bound to the exact script hash (any edit voids it)
- [x] **SCR-04**: The source list for the caption/pinned comment is rendered from stored sources only (never model-written)
- [ ] **SCR-05**: After recording, a Whisper transcript of the operator's take is diffed against the approved script; deviating sentences are fact-checked before publishing
- [x] **SCR-06**: Model IDs and prompts are config, not hard-coded, and each LLM call is logged (model, prompt hash, inputs, output)

### Production & safety operations

- [ ] **OPS-01**: A crisis/comment-moderation playbook exists before the first post (manual moderation only, AT/DE hotlines e.g. 142/147/TelefonSeelsorge, spike protocol); comments are never auto-replied
- [ ] **OPS-02**: A Personal TikTok account (plus YouTube Shorts/Instagram Reels for watermark-free cross-posts) is set up with a bio and sourcing statement
- [ ] **OPS-03**: Operator publishes 24–28 videos at 4–5/week in batched production, rotating pillars in a pre-planned schedule

### Measurement & decision

- [ ] **MEAS-01**: The go/no-go readout rule is written down and committed before video 1 (pillar is the primary variable, ≤4–6 arms, rate metrics, thresholds for "winner" vs "inconclusive")
- [ ] **MEAS-02**: Operator logs each published video (platform, post id, topic, pillar/angle/hook, script hash) at publish time
- [ ] **MEAS-03**: Operator records metric snapshots at fixed post ages (e.g. 72h and 7d): views, completion/retention, saves, shares, follows, For You feed eligibility
- [ ] **MEAS-04**: A readout report ranks the formats against the account's own median and names the top 1–2 formats (or "inconclusive") as the milestone-2 input

### Legal (pre-monetization)

- [ ] **LEGAL-01**: A legal/tax checklist (Impressum MedienG §25/ECG §5 via an address service, AMG/UWG/HWG/EU 1924/2006, protected titles, trade/tax registration, AI labeling) is resolved with WKO/Steuerberater before any monetization
- [ ] **LEGAL-02**: TikTok Creator Rewards eligibility for Austria is checked in-app, and the YouTube Partner Program path is documented

## v2 Requirements (Milestone 2 — automation of winning formats)

- **AUTO-01**: Visuals + captions are rendered automatically (Remotion, faster-whisper word timestamps) in a CPU-capped container
- **AUTO-02**: A Telegram approve/reject card shows the video, script and sources
- **AUTO-03**: Publishing via an audited scheduler (Buffer/Blotato) or the TikTok inbox/draft flow
- **AUTO-04**: Analytics are pulled where APIs allow and fed back into topic selection
- **AUTO-05**: TTS fallback voice (the operator's own voice stays primary)
- **AUTO-06**: Topic intake from Reddit/trends
- **MON-01**: Digital products (parent guides, routine toolkits), email list, ND app sponsorships/affiliates — after LEGAL-01

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-replying to comments | Mental-health crisis risk; LLM may only flag, never reply |
| AI avatar / faked female persona | Authenticity; male voice is the differentiator |
| Symptom checklists / self-tests | Top misinformation format; diagnostic framing |
| Medication, diagnosis, ABA topics | Conservative whitelist |
| Supplements, telehealth, medication offers | Credibility and legal risk |
| Web app, task queue, vector DB in M1 | Over-building before traction; CLI + SQLite is enough |
| Daily posting | Burnout risk; 4–5/week chosen |
| Impressum before monetization | Operator accepted the risk while non-commercial (research flagged MedienG §25 may apply earlier) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MKT-01 | Phase 1 | Complete |
| MKT-02 | Phase 1 | Complete |
| MKT-03 | Phase 1 | Complete |
| CONT-01 | Phase 1 | Complete |
| CONT-02 | Phase 1 | Complete |
| CONT-03 | Phase 1 | Complete |
| CONT-04 | Phase 1 | Complete |
| SRC-01 | Phase 2 | Complete |
| SRC-02 | Phase 2 | Pending |
| SRC-03 | Phase 2 | Complete |
| SRC-04 | Phase 2 | Pending |
| SCR-01 | Phase 2 | Complete |
| SCR-02 | Phase 2 | Complete |
| SCR-03 | Phase 2 | Pending |
| SCR-04 | Phase 2 | Complete |
| SCR-05 | Phase 3 | Pending |
| SCR-06 | Phase 2 | Complete |
| OPS-01 | Phase 3 | Pending |
| OPS-02 | Phase 3 | Pending |
| OPS-03 | Phase 4 | Pending |
| MEAS-01 | Phase 3 | Pending |
| MEAS-02 | Phase 3 | Pending |
| MEAS-03 | Phase 3 | Pending |
| MEAS-04 | Phase 4 | Pending |
| LEGAL-01 | Phase 4 | Pending |
| LEGAL-02 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-24*
*Last updated: 2026-10-24 after roadmap creation*
