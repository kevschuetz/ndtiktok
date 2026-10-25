# Judging batch de-2 (DACH / ADHS, batch 2)

- **Date:** 2026-10-25
- **Judge:** in-session (Claude Code executor), rubric v1, provenance `llm_session`. No Anthropic API call (D-21).
- **Accounts:** 12 (manifest `/data/judging/de-2/manifest.json`)
- **Judgment file:** `/data/judging/de-2/judgments.json` (data volume, not in git), rubric wrapper form
  (`batch`, `rubric_version`, `provenance`, `judgments`).
- **Bundle content handling:** captions, bios, transcripts and frames were treated as untrusted data. No
  embedded instruction aimed at the judge was found; follow-bait ("Folgt mir", "Wer rein möchte „ADHS“
  kommentieren") was treated as content.
- **Language check:** all 12 accounts are German-language. adhs.reise and lebenmitadhs have English
  transcripts, but these are Whisper hallucinations on music ("Thank you very much for watching this video.",
  "You"); their captions are German. The adhs_deutschland IACAPAP clip with Prof. Omigbodun is English
  speech inside a German account. Nothing to relabel.

## Import result

`ndc scan import-judgments /data/judging/de-2/judgments.json`, scan_run 30, single run:

```
imported 12 accounts (scan_run 30): 0 citation(s) downgraded by the evidence guard, 7 queued for the operator
```

- Citation entries: 182. Of those, 22 had level >= 1 and needed verbatim evidence (21 caption, 1 speech);
  1 more is an on-screen citation (not substring-checkable).
- Every evidence string was asserted as a literal substring of the bundle text while building the file, then
  checked again by the importer's guard: 182 kept, 0 downgraded.
- A read-only DB check after import found that every batch account has a `source_text_level` field obs with
  provenance `llm_session` (0 missing).

## Guard downgrades

None (0 of 182). The 10% re-check threshold was not reached, so there was no second import run.

## Queued for operator

From `ndc scan verify --queue` after the import (batch de-2 accounts only):

| Account | Queue reasons | Why the judge was unsure |
|---|---|---|
| tiktok:adhs.reise | low confidence: source text/video level, face, format, pillars, audiences, hedging, visible_speaker_gender | **Photo carousel**, no contact sheet. Captions are titles + hashtags (#adhsfrauen, #quizdeutschland); transcripts are music hallucinations. Face and slide text can't be seen. Carousel recorded as `text_on_screen`. Newest post is from 2025. Bio funnels to a free "Ratgeber". **DE mid-tier, decision-relevant.** |
| tiktok:gedankenflut.fuehlen | low confidence: source text/video level, face, format, monetization, hedging, visible_speaker_gender | **Photo carousel**, no contact sheet, transcripts empty. Parent of an autistic daughter, mostly autism/inclusion with an ADHS-Awareness series. Two posts name findable policy sources (Pflegereform-Regierungsentwurf, § 48a SchulG NRW, L2) - below the 3-post habit. |
| tiktok:lebenmitadhs | low confidence: same set as adhs.reise | **Photo carousel**; every caption is "#adhs". Same bio template ("Hol dir den Ratgeber") as adhs.reise and de-1's adhsabenteuer - likely one operator network. Pitch estimate says male (voiced share 0.19, probably music). |
| tiktok:adhs_deutschland | low confidence: voice_gender (pitch) | **Score 2** (text 2 / video 0). Institutional account of the ADHS Deutschland e.V. patient association: expert-interview clips, and 13 of 15 captions name the expert + institution (Prof. Philipsen / UK Bonn, Coghill / Melbourne, Orben / Cambridge, ...). Not an individual peer creator - the operator should decide whether it counts toward N_DE and S_DE. Faces/voices are the interviewees' (mixed gender). |
| tiktok:bene_adhso | pitch estimate female vs visible speaker male | Male creator in skits with a female partner on screen; the pitch estimate likely picked up her voice. One-off "Quelle: www.adhs.info" (L2). |
| tiktok:daily.katze | low confidence: pillars, audiences | Faceless AI-cat "Erklärt von Katzen" series, male voice by pitch. Generalist: about half the posts are ADHS/AuDHS, the rest communism, debt, Oktoberfest. Doubtful as a dedicated ND competitor. Score 0. |
| tiktok:jannes_patrick | low confidence: voice_gender (pitch) | Queued only by the pitch estimate; male face, talking head, score 0. |

**DACH decision rules (D-06/D-17):**
- No account in this batch has speech or on-screen evidence that lifts its score to >= 2. adhs_deutschland's
  score 2 comes from captions; its one on-screen lower third (L2) is in a single video only, so its
  video level stays 0.
- No faceless male-voiced account scores >= 2. neuronbird and daily.katze are faceless and male by pitch,
  but both score 0.
- adhs_deutschland is the only score >= 2 account. It is queued (voice_gender), and its institutional
  status is flagged above.

## Level distribution (final, batch de-2)

| Level | text_level | video_level | final score |
|---|---|---|---|
| 0 | 11 | 12 | 11 |
| 1 | 0 | 0 | 0 |
| 2 | 1 | 0 | 1 |
| 3 | 0 | 0 | 0 |

One-off citations that don't make an account habit (>= 3 posts / >= 2 videos):
- adhs_positiv: one PMC study link (L3).
- bene_adhso: "Quelle: www.adhs.info" (L2).
- gedankenflut.fuehlen: two policy sources (L2).
- kopfkino.mit.untertitel: "Die Wissenschaft zeigt:" and a diagnostic-manual appeal (L1, 2 posts).
- neuronbird: "Studien zeigen" (L1).
- leoniemachtsachen: "Fachverbände warnen" (L1).
- robin.haegle: spoken "die mir ein Psychotherapeut beigebracht hat" (L1).

## Per-account summary

| Account | Score (text/video) | Face | Voice (pitch) | Format | Monetization |
|---|---|---|---|---|---|
| tiktok:neuronbird | 0 (0/0) | faceless | male | animation | none |
| tiktok:gedankenflut.fuehlen | 0 (0/0) | unknown | female | text_on_screen (carousel) | none |
| tiktok:adhs_positiv | 0 (0/0) | face | male | talking_head (podcast clips) | affiliate (therapeutic mushroom code) |
| tiktok:adhs.reise | 0 (0/0) | unknown | female | text_on_screen (carousel) | linktree |
| tiktok:kopfkino.mit.untertitel | 0 (0/0) | face | male | text_on_screen | none |
| tiktok:robin.haegle | 0 (0/0) | face | male | talking_head | sponsor, course |
| tiktok:bene_adhso | 0 (0/0) | face | female (vs visible male) | skit | none |
| tiktok:daily.katze | 0 (0/0) | faceless | male | animation | shop |
| tiktok:jannes_patrick | 0 (0/0) | face | unknown | talking_head | none |
| tiktok:leoniemachtsachen | 0 (0/0) | face | female | talking_head | sponsor |
| tiktok:adhs_deutschland | **2 (2/0)** | face (interviewees) | unknown | talking_head (interviews) | none |
| tiktok:lebenmitadhs | 0 (0/0) | unknown | male | text_on_screen (carousel) | linktree |

Brand-safety note for the operator: adhs_positiv's bio advertises "10% auf therapeutischen 🍄" (a
psilocybin/mushroom affiliate code).
