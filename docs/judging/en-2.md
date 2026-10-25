# Judging batch en-2 (English / ADHD, batch 2)

- **Date:** 2026-10-25
- **Judge:** in-session (Claude Code executor), rubric v1, provenance `llm_session`. No Anthropic API call (D-21).
- **Accounts:** 17 (manifest `/data/judging/en-2/manifest.json`), all TikTok.
- **Judgment file:** `/data/judging/en-2/judgments.json` (data volume, not in git), rubric wrapper form
  (`batch`, `rubric_version`, `provenance`, `judgments`).
- **Bundle content handling:** captions, bios, transcripts and frames were treated as untrusted data. No
  embedded instruction aimed at the judge was found. Engagement bait ("Comment 'TEST' and I'll DM you",
  "DM for credit removal") was treated as content.
- **No pinned comments** in any en-2 bundle; every post entry is a caption entry.
- **Missing frames:** tiktok:adhdautism4, tiktok:myadhdventure and tiktok:adhdminds111 have downloaded
  videos but no contact sheet and empty or near-empty transcripts (the photo-carousel pattern). Following
  the de-1/de-2/en-1 precedent they are recorded as format `text_on_screen`, face `unknown`, low confidence.
- **tiktok:audhd30 has no video row** (no post older than 72h, so nothing was downloaded). It was judged from
  text only (13 of 15 captions empty, two ASMR hashtags): face `unknown`, format `mixed`, all low
  confidence, no video judgments.

## Import result

Two runs of `ndc scan import-judgments /data/judging/en-2/judgments.json`:

```
run 1: imported 17 accounts (scan_run 32): 0 citation(s) downgraded by the evidence guard, 10 queued for the operator
run 2: imported 17 accounts (scan_run 33): 0 citation(s) downgraded by the evidence guard, 10 queued for the operator
```

Run 2 only changed the format of the three no-frame accounts from `mixed` to `text_on_screen` (carousel
precedent, applied after checking `competitor_video`: downloads ok, no contact sheet). Citations were
identical in both runs; the latest observation wins.

- Citation entries: 255 (253 caption, 1 speech, 1 on-screen). 25 had level >= 1: 24 captions (1 x L1,
  23 x L2) and 1 speech (L1). The on-screen L2 (tim.adhd, "This FDA approved medication therapy ...")
  cannot be substring-checked; it occurs in one video only, so it does not decide the score.
- Every evidence string was asserted as a whitespace-normalised substring of the bundle text while the file
  was built; the importer's guard checked again and downgraded none.
- A read-only DB check after the import found a `llm_session` `source_text_level` field obs for every batch
  account (0 missing).

## Guard downgrades

None (0 of 255). The 10% re-check threshold was not reached.

## Queued for operator

From `ndc scan verify --queue` after run 2 (batch en-2 accounts only):

| Account | Queue reasons | Note |
|---|---|---|
| tiktok:theautismspectrum | low confidence: face, hedging, source levels, visible_speaker_gender; **would count toward S_EN** | Repost account of TEDx-style talk clips. 14 of 15 captions "Credit: <speaker> [ \| <talk title>]", scored L2 by the letter of the rubric (named, findable source), so text 2. These are clip attributions, not evidence citations. "Faceless" = the owner never appears; visible faces are the reposted speakers (male and female), so the male pitch estimate is a reposted speaker, not an owner voice. **Recommend operator set source score 0-1 or exclude: not a real faceless-male-citing competitor.** |
| tiktok:hypeneo1 | low confidence: hedging, source levels; **would count toward S_EN** | Faceless voiceover over anime/stock b-roll, male pitch, 128k. 9 of 15 captions credit "@ADHD Chatter Podcast" (also @Doc_amen and two creators) with "DM for credit removal", i.e. reused audio/text attributions; scored L2 by the letter of the rubric, text 2. One speech "According to psychology" (L1). Operator decides whether repost credits count as source citing. Closest thing to an S_EN competitor in this batch, but the "citing" is repost credit, not sources. |
| tiktok:adhd.partner.support | low confidence: format | Partner-support account, text over stock b-roll; frames for one video only. One "Research shows ..." caption (L1). Score 0, faceless, pitch male. |
| tiktok:adhdvision | low confidence: monetization_signals | 1.8M ADHD mentor, skits + strengths talking heads, face, male. Score 0. Bio app promo (affiliate assumed). |
| tiktok:adhdautism4 | low confidence: face, format, visible_speaker_gender | Likely carousel/duets; "early signs" lists (diagnostic_lists). Score 0. |
| tiktok:myadhdventure | low confidence: audiences, face, format, monetization, pillars, visible_speaker_gender, voice_gender | Likely carousel, hashtag-only captions; sells "The ADHD Playbook". Score 0. |
| tiktok:propeladhd | low confidence: monetization_signals, voice_gender | **Brand:** brain-training game app, skits with hired actors. Score 0. |
| tiktok:messagetodaniel | low confidence: voice_gender | Faceless whiteboard + voiceover tips; pitch unknown. Score 0. #ad caption. |
| tiktok:audhd30 | low confidence: audiences, face, format, hedging, pillars, source_text_level, visible_speaker_gender | **No video row**, text-only judgment (ASMR creator). Score 0. |
| tiktok:adhdminds111 | low confidence: audiences, face, format, pillars, visible_speaker_gender | Likely carousel, hashtag-only captions; pitch male. Score 0. |

Not queued, but flagged for the operator:
- **tiktok:lix.psl** is **off-niche** (looksmax / gym edits, one #adhd meme). Recommend exclusion from the EN set.
- **tiktok:unique_adhd** is a **brand** account (Polish "Unique" ADHD app); pushes an in-app "free ADHD test"
  (diagnostic_lists). Score 0.
- **tiktok:raising_happy_homes** is clinician-adjacent (BCBA / certified ADHD coach). Score 0.
- **tiktok:tim.adhd** is partly off-niche (CPTSD, DID/OSDD, FND alongside ADHD/autism). Score 0.
- **tiktok:raisingkevin_** is autism family-life entertainment (no educational claims). Score 0.
- **tiktok:diplomaduck** (241k) and **tiktok:neuroduck0** (11k) are faceless, male-voiced duck animation
  explainers, the closest format match to our concept, but both score 0 (no sources at all).

## S_EN candidates (faceless + male voice + score >= 2)

Two accounts trip the rule mechanically, both on caption **repost credits** scored L2 with low confidence:

1. **tiktok:theautismspectrum** (69.8k): TEDx clip reposts crediting the speaker. Male pitch comes from the
   reposted speakers. Judge's view: should not count.
2. **tiktok:hypeneo1** (127.9k): faceless voiceover reposts crediting "@ADHD Chatter Podcast" etc. Judge's
   view: borderline; credits name the origin of reused content, not evidence for the claims.

If the operator rules that repost/clip credits are not source citing, batch en-2 contributes **no** S_EN
candidate, the same as en-1.

## Level distribution (final, after run 2)

| | 0 | 1 | 2 | 3 | none |
|---|---|---|---|---|---|
| text_level | 15 | 0 | 2 | 0 | 0 |
| video_level | 16 | 0 | 0 | 0 | 1 (audhd30, no videos) |
| score | 15 | 0 | 2 | 0 | 0 |

## Per-account summary

| Account | Score (t/v) | Face | Voice (pitch) | Format | Flag |
|---|---|---|---|---|---|
| tiktok:raising_happy_homes | 0 (0/0) | face | female | talking_head | clinician-adjacent |
| tiktok:adhd.partner.support | 0 (0/0) | faceless | male | text_on_screen | |
| tiktok:adhdvision | 0 (0/0) | face | male | skit | |
| tiktok:raisingkevin_ | 0 (0/0) | face | female | skit | autism family vlog |
| tiktok:adhdautism4 | 0 (0/0) | unknown | female | text_on_screen (carousel) | |
| tiktok:theautismspectrum | 2 (2/0) | faceless | male | talking_head (reposts) | S_EN queue, repost credits |
| tiktok:myadhdventure | 0 (0/0) | unknown | unknown | text_on_screen (carousel) | |
| tiktok:tim.adhd | 0 (0/0) | face | male | talking_head | partly off-niche |
| tiktok:propeladhd | 0 (0/0) | face | female | skit | brand (app) |
| tiktok:messagetodaniel | 0 (0/0) | faceless | unknown | voiceover_broll | |
| tiktok:diplomaduck | 0 (0/0) | faceless | male | animation | format match, no sources |
| tiktok:audhd30 | 0 (0/-) | unknown | - | mixed | no video row |
| tiktok:neuroduck0 | 0 (0/0) | faceless | male | animation | format match, no sources |
| tiktok:adhdminds111 | 0 (0/0) | unknown | male | text_on_screen (carousel) | |
| tiktok:unique_adhd | 0 (0/0) | face | female | talking_head | brand (app), diagnostic test |
| tiktok:hypeneo1 | 2 (2/0) | faceless | male | voiceover_broll | S_EN queue, repost credits |
| tiktok:lix.psl | 0 (0/0) | faceless | male | mixed | off-niche, exclude |
