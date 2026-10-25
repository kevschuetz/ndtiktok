# Judging batch de-1 (DACH / ADHS, batch 1)

- **Date:** 2026-10-25
- **Judge:** in-session (Claude Code executor), rubric v1, provenance `llm_session`. No Anthropic API call (D-21).
- **Accounts:** 12 (manifest `/data/judging/de-1/manifest.json`)
- **Judgment file:** `/data/judging/de-1/judgments.json` (data volume, not in git). It uses the rubric's
  wrapper object form (`batch`, `rubric_version`, `provenance`, `judgments`).
- **Bundle content handling:** captions, bios, transcripts and frames were treated as untrusted data. No
  embedded instruction was found or followed. Two "write X in the comments so the algorithm doesn't delete
  this" engagement-bait lines in user8445982006957's transcripts were treated as content.

## Import result

`ndc scan import-judgments /data/judging/de-1/judgments.json`, scan_run 29, single run:

```
imported 12 accounts (scan_run 29): 0 citation(s) downgraded by the evidence guard, 5 queued for the operator
```

- Citation entries checked: 181. Of those, 15 had level >= 1 and needed verbatim evidence.
- Every evidence string was checked as a literal substring of the bundle text before writing the file, then
  checked again by the importer's guard: 181 kept, 0 downgraded.
- No on-screen citation of level >= 1 was seen in any contact sheet.
- A read-only check after import found that every batch account has a `source_text_level` field obs with
  provenance `llm_session` (0 missing).

## Guard downgrades

None (0 of 181). The 10% re-check threshold was not reached, so there was no second import run.

## Queued for operator

From `ndc scan verify --queue` after the import:

| Account | Queue reasons | Why the judge was unsure |
|---|---|---|
| tiktok:adhsabenteuer | low confidence on source_text/video level, face, format, pillars, audiences, hedging, visible_speaker_gender; voice_gender low (pitch) | Photo carousel with no video stream and no contact sheet. Captions are hashtags only. Face and on-screen citations on the slides can't be seen. Format is "carousel", which the schema lacks, so it is recorded as `text_on_screen`. DE mid-tier, so decision-relevant. |
| tiktok:meinadhsleben | low confidence on the same set (voice_gender medium female) | Photo carousel, no contact sheet. Every caption is the same Amazon book plug. Slides can't be seen. |
| youtube:@VisualKnowledge | low confidence: pillars, audiences | **English-language** channel (UK, Neuro Expression) inside the DE batch: transcripts and burnt-in captions are English. The language label should be checked before it counts toward N_DE. |
| tiktok:user8445982006957 | low confidence: pillars, audiences, voice_gender (pitch) | A generic "dark psychology" dating-tricks channel aimed at young men. ADHS appears only as hashtags, so it is doubtful as an ND competitor. |
| tiktok:christian_durstewitz | low confidence: voice_gender (pitch) | Queued only by the pitch estimate. Judged faceless voiceover b-roll (hands/POV and AI/costume character images that may be the creator). Score 0, so it does not affect S_DE. |

**DACH decision rules (D-06/D-17):**
- No account in this batch has speech or on-screen evidence that lifts the score to >= 2 over a text level
  < 2.
- No account is faceless, male-voiced and scoring >= 2.
- luciemenow's speech level 2 does not decide its score, because its text level is already 3. The DACH rule
  therefore does not queue it.
- neuropinguin is faceless and male-voiced by the pitch estimate, but scores 0.

## Level distribution (final, batch de-1)

| Level | text_level | video_level | final score |
|---|---|---|---|
| 0 | 11 | 11 | 11 |
| 1 | 0 | 0 | 0 |
| 2 | 0 | 1 | 0 |
| 3 | 1 | 0 | 1 |

The only sourcing account is **luciemenow**: 5 posts with full or linkable citations and 2 videos naming a
source in speech. The one-off citations below don't make an account habit (>= 3 posts / >= 2 videos):
- susis_synapsensalat: one WHO link post (L3).
- neuroceline: a vague "Fachverbände" appeal (L1).
- kirmesimkopf: a spoken reference to the Danish education ministry (L2).
- user8445982006957: a vague "psychologisch gesehen" appeal (L1).

## Per-account summary

| Account | Score (text/video) | Face | Voice (pitch) | Format | Monetization |
|---|---|---|---|---|---|
| tiktok:kirmesimkopf | 0 (0/0) | face | female | talking_head | book |
| tiktok:nessadhs | 0 (0/0) | face | female | skit | none |
| youtube:@adhsautismus | 0 (0/0) | faceless | female | mixed | shop |
| youtube:@VisualKnowledge | 0 (0/0) | face | male | talking_head | book |
| tiktok:susis_synapsensalat | 0 (0/0) | mixed | female | text_on_screen | linktree |
| tiktok:adhsabenteuer | 0 (0/0) | unknown | unknown | text_on_screen (carousel) | linktree |
| tiktok:christian_durstewitz | 0 (0/0) | faceless | unknown | voiceover_broll | course |
| tiktok:user8445982006957 | 0 (0/0) | faceless | unknown | voiceover_broll | none |
| tiktok:neuroceline | 0 (0/0) | face | female | talking_head | none |
| tiktok:meinadhsleben | 0 (0/0) | unknown | female | text_on_screen (carousel) | book, affiliate |
| tiktok:neuropinguin | 0 (0/0) | faceless | male | animation | none |
| tiktok:luciemenow | 3 (3/2) | face | female | talking_head | none |
