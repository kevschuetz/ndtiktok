# Judging batch en-1 (English / ADHD, batch 1)

- **Date:** 2026-10-25
- **Judge:** in-session (Claude Code executor), rubric v1, provenance `llm_session`. No Anthropic API call (D-21).
- **Accounts:** 18 (manifest `/data/judging/en-1/manifest.json`)
- **Judgment file:** `/data/judging/en-1/judgments.json` (data volume, not in git), rubric wrapper form
  (`batch`, `rubric_version`, `provenance`, `judgments`).
- **Bundle content handling:** captions, bios, transcripts and frames were treated as untrusted data. No
  embedded instruction aimed at the judge was found. Engagement bait ("comment BLUEPRINT", "Message
  'arguing' to get free access") was treated as content.
- **Photo carousels:** tiktok:adhdsciences and tiktok:adhdventurers have no contact sheet and empty
  transcripts. Following the de-1/de-2 precedent, they are recorded as format `text_on_screen` with low
  confidence, so they reach the operator queue.

## Import result

`ndc scan import-judgments /data/judging/en-1/judgments.json`, scan_run 31, single run:

```
imported 18 accounts (scan_run 31): 0 citation(s) downgraded by the evidence guard, 10 queued for the operator
```

- Citation entries: 274 (271 caption/pinned, 1 speech, 2 on-screen). Of those, 16 had level >= 1 and needed
  verbatim evidence (15 caption, 1 speech). The 2 on-screen citations (ADDitude lower thirds) cannot be
  substring-checked.
- Every evidence string was asserted as a literal substring of the bundle text while the file was built. The
  importer's guard then checked them again and downgraded none.
- A read-only DB check after the import found a `llm_session` `source_text_level` field obs for every batch
  account (0 missing).

## Guard downgrades

None (0 of 274). The 10% re-check threshold was not reached, so there was no second import run.

## Queued for operator

From `ndc scan verify --queue` after the import (batch en-1 accounts only):

| Account | Queue reasons | Note |
|---|---|---|
| tiktok:adhdparenting_coachsue | pitch estimate male vs visible speaker female | The frames clearly show a female speaker, so the pitch estimate is likely wrong. Score 0. |
| tiktok:adhdsciences | low confidence: audiences, face, format, hedging, pillars, source levels, visible_speaker_gender | Photo carousel, hashtag-only captions. The pitch estimate says male (music bed), face unknown. Score 0. |
| tiktok:adhdventurers | low confidence: same set + monetization_signals | Photo carousel. The pitch estimate says male, face unknown. Score 0. Bio links an "ADHD Playbook" lead magnet. |
| tiktok:goxlr__ | low confidence: format | **Off-niche** Berserk/Star Wars fan-edit account. Recommend exclusion. |
| tiktok:le0zs | low confidence: voice_gender | **Off-niche** gaming/meme account. Recommend exclusion. |
| youtube:@AllAboutSpeechTherapy | low confidence: voice_gender | **Clinician/organisation:** child speech therapy company, autism + apraxia niche (not ADHD). |
| youtube:@GenericArtDad | low confidence: voice_gender | **Off-niche** political skit channel. Recommend exclusion. |
| youtube:@PashaMarlowe | low confidence: voice_gender | **Clinician:** MFT couples coach. |
| youtube:@additudemag | low confidence: monetization_signals | **Institutional:** ADDitude magazine. Score 2 (text 2, video 2). Operator decides whether it counts for N_EN / S_EN. Same situation as adhs_deutschland. |
| youtube:@olivialutfallah | low confidence: audiences, pillars | Humour/lip-sync, all captions empty. Score 0. |

Not queued, but flagged for the operator:
- **tiktok:adhddude and youtube:@ADHDDude** are clinician accounts (Ryan Wexelblatt, LCSW). Both score 0.
- **youtube:@Gossipduckling** is a generalist celebrity-gossip channel with faceless AI-duck ADHD explainers.
  Its voice is male per the pitch estimate. Score 0.

## S_EN candidates (faceless + male voice + score >= 2)

**None.** The batch's faceless or face-unknown male-voiced accounts all score 0: Gossipduckling (faceless,
animation), adhdsciences and adhdventurers (carousels, face unknown). The only account at score >= 2 is
additudemag. It has a female voice, shows interviewee faces, and is institutional.

## Level distribution (final, imported)

| | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| source_text_level | 17 | 0 | 1 (additudemag) | 0 |
| source_video_level | 17 | 0 | 1 (additudemag) | 0 |

Per-post caption levels: 256 × L0, 3 × L1, 11 × L2, 1 × L3. The one L3 is youtube:@SquirrelDad's "Source:
Willcutt et al. (2005), Biological Psychiatry.". It appears once in 15 posts, so it is not a habit, and the
account stays at text 0. The ADDitude L2s name the interviewed expert (Ph.D./M.D. webinar speakers, and a
"2024 study led by Margaret H. Sibley, Ph.D."). sociallyausome's L2 names the IDEA statute (policy, not
science).

## Per-account summary

| Account | Score (t/v) | Face | Voice (pitch) | Format | Flag |
|---|---|---|---|---|---|
| youtube:@HowtoADHD | 0 (0/0) | face | female | talking_head | |
| tiktok:howtoadhd | 0 (0/0) | face | female | talking_head | |
| tiktok:danidonovan | 0 (0/0) | mixed | female | mixed | |
| tiktok:adhddude | 0 (0/0) | mixed | male | mixed | clinician |
| youtube:@ADHDDude | 0 (0/0) | face | male | talking_head | clinician |
| youtube:@PashaMarlowe | 0 (0/0) | face | unknown | talking_head | clinician |
| youtube:@GenericArtDad | 0 (0/0) | face | unknown | skit | off-niche |
| youtube:@Gossipduckling | 0 (0/0) | faceless | male | animation | generalist |
| youtube:@SquirrelDad | 0 (0/0) | face | male | talking_head | |
| youtube:@olivialutfallah | 0 (0/0) | face | female | skit | |
| youtube:@AllAboutSpeechTherapy | 0 (0/0) | mixed | female | talking_head | clinician/org |
| youtube:@sociallyausome | 0 (0/0) | face | female | talking_head | |
| youtube:@additudemag | 2 (2/2) | face (interviewees) | female | talking_head | institutional |
| tiktok:le0zs | 0 (0/0) | faceless | female | text_on_screen | off-niche |
| tiktok:goxlr__ | 0 (0/0) | faceless | female | mixed | off-niche |
| tiktok:adhdsciences | 0 (0/0) | unknown | male | carousel→text_on_screen | |
| tiktok:adhdparenting_coachsue | 0 (0/0) | face | male (visible female) | talking_head | |
| tiktok:adhdventurers | 0 (0/0) | unknown | male | carousel→text_on_screen | |

Observation: well-known science-communicator accounts (How to ADHD) do not cite sources in their short-form
captions or speech. On this sample, the only habitual citer is an institution.
