# Competitor scan run log (MKT-01, plan 01-07)

All runs on the real DB `/data/ndc.db`, inside the `ndc` container, single-threaded, with built-in
3–6 s pacing. Every scan_run is recorded under rule sha256
`ea401c5d7fd18e598fa8f18e759b75c45cbae982e066261c4e90df0b1f904b04`. All runs were outside the
00:15–06:00 UTC quiet hours, and no `--force` was used: `scan_run` rows with
`quiet_hours_override` = 0.

## Config changes made for this run (config/scan.yaml, not the decision rule)

- `discovery.min_niche_shorts` 3 → **2**. With 3, ytsearch kept 5 DE / 0 new EN channels (01-04
  finding); most channels appear only 1–2 times across a language's queries.
- `discovery.ytsearch_results` 30 → **60**. This widens the YouTube pool. Each query is still one
  ytsearch call; yt-dlp pages internally.
- `config/decision_rule.yaml` and its lock are untouched.

## Discovery

| Source | Command | UTC start–end | scan_run | Requests | Seen | New |
|---|---|---|---|---|---|---|
| D-04 seeds | `scan import-candidates scan/candidates.csv` | 21:57 | — | 0 | 11 | 0 (already imported in 01-04) |
| YouTube ytsearch DE (N=30, min 2) | `scan discover youtube --lang de` | 21:57:29–21:58:23 | 12 | 10 | 89 | 4 |
| YouTube ytsearch EN (N=30, min 2) | `scan discover youtube --lang en` | 21:58:28–21:59:17 | 13 | 10 | 101 | 6 |
| YouTube ytsearch DE (N=60, min 2) | `scan discover youtube --lang de` | 21:59:45–22:00:40 | 14 | 10 | 174 | 10 |
| YouTube ytsearch EN (N=60, min 2) | `scan discover youtube --lang en` | 22:00:41–22:01:34 | 15 | 10 | 182 | 5 |
| Modash public pages | not run | 22:00 (1 index GET) | — | 1 | — | — |
| TikTok Creative Center / Exolyt / Favikon / in-app | operator-browser | — | — | — | — | — |

- **Modash:** one GET of the `find-influencers` index listed 851 public page paths. None is about
  ADHD, autism, neurodivergence, mental health or psychology. The nearest are generic
  `tiktok/{country}`, `tiktok/{country}/health|parenting|dad` pages: top-20 general influencers
  who would be off-niche here. Running them would add rows the operator must exclude, so
  `discover modash` was not run. **No scripted TikTok discovery source is niche-specific, so the
  TikTok pool depends on the operator (Task 2).**
- **Language mislabelling.** 11 channels found by DE queries were also found by EN queries
  ("Tourette", "AuDHD" and "Dyspraxie/dyspraxia" overlap). Most are English channels sitting
  under `de`. They are flagged in `notes`. Per the 01-04 decision nothing was relabelled
  automatically; the operator changes the `language` column.
- **Off-niche hits.** ytsearch also returns news outlets (CBC, BBC, local US news), brands
  (Goally, Healthgrades) and kids' news (logo!) that published a one-off ADHD/autism Short.
  `notes` carry an `executor suggestion: exclude …` for these. `operator_decision` is left blank,
  so the decision stays explicitly the operator's.

## Profile fetch

`scan fetch --stage profile` (scan_run 16), 22:01:53–22:05:08 UTC: ok 33, skipped fresh 2 (the
01-04 smoke accounts), failed 6, stopped platforms 0. TikTok blocked nothing.

Failures:
- 4 YouTube channels have no Shorts tab: @bvlegasthenie, @autismusspektruminfo,
  @AdventuresofNeryn, @RDXMixer. They are not usable for a Shorts sample.
- 2 TikTok seeds returned no data: verena_eisbrenner, guardianofmind. See seeds below.

## Candidate selection

`scan select --lang de` (scan_run 17) and `--lang en` (scan_run 18), 22:05 UTC.

### Pool per language × platform

| Language | Platform | Candidates | Followers fetched | ≥ 1000 followers |
|---|---|---|---|---|
| de | tiktok | 5 | 3 | 2 |
| de | youtube | 19 | 15 | 9 |
| en | tiktok | 4 | 4 | 4 |
| en | youtube | 13 | 13 | 12 |
| **total** | | **41** | **35** | **27** |

### Tier counts of the pool (followers ≥ 1000)

| Language | micro (1k–10k) | mid (10k–100k) | macro (100k–1M) | mega (> 1M) |
|---|---|---|---|---|
| de | 6 (TT 1, YT 5) | 1 (YT 1) | 3 (TT 1, YT 2) | 1 (YT 1) |
| en | 3 (TT 1, YT 2) | 3 (TT 1, YT 2) | 8 (TT 2, YT 6) | 2 (YT 2) |

### Proposed sample (status `selected`)

| Language | mid | micro | macro | mega | total | TikTok | YouTube | target |
|---|---|---|---|---|---|---|---|---|
| de | 1 | 6 | 3 | 1 | **11** | 2 | 9 | 40 (28 TT / 12 YT) |
| en | 3 | 3 | 8 | 2 | **16** | 4 | 12 | 40 (28 TT / 12 YT) |

Shortfalls, verbatim from `scan select`:
- de: `mid tier shortfall: 1 of 12`
- en: `mid tier shortfall: 3 of 12`

The selected set is everything with ≥ 1000 followers. The pool is far below the quota, so the
quota itself never cut anything.

**What is actually usable is smaller than "selected".** After the executor's exclude/relabel
suggestions (news outlets, brands, and English channels under `de`):
- DE: about 3 German ND accounts are left: TikTok nessadhs (macro), TikTok kirmesimkopf (micro),
  and YouTube @adhsautismus (micro).
- EN: TikTok danidonovan, howtoadhd (macro), adhddude (mid), adhd_alien (micro); YouTube
  @HowtoADHD (mega), @ADHDDude (mid), @additudemag (macro), plus about 4 relabelled DE→EN
  micro channels and 4 "check niche" channels.

**Validity floor (≥ 8 usable mid-tier TikTok accounts per language): DE 0 of 8, EN 1 of 8.**

### Seeds (D-04)

| Seed | Platform | Handle | Status |
|---|---|---|---|
| kirmesimkopf | TikTok | kirmesimkopf | resolved, 5,046 followers (micro), selected |
| kirmesimkopf | YouTube | — | no handle known; not searched (not in ytsearch results) |
| nessadhs | TikTok | nessadhs | resolved, 122,400 (macro), selected |
| nessadhs | YouTube | — | no handle known; not in ytsearch results |
| hey_mamaleben | TikTok | hey_mamaleben | fetched, 3 followers: handle probably wrong. Not selected; operator to supply the correct handle |
| hey_mamaleben | YouTube | — | no handle known |
| verena_eisbrenner | TikTok | verena_eisbrenner | no data (handle wrong, private or absent). Recorded "not on platform" by `select`; operator to confirm or supply the handle |
| verena_eisbrenner | YouTube | — | no handle known |
| guardianofmind | TikTok | guardianofmind | no data. Recorded "not on platform"; operator to confirm or supply the handle |
| guardianofmind | YouTube | — | no handle known |
| How to ADHD | TikTok | howtoadhd | resolved, 100,800 (macro), selected (guess confirmed as existing; operator to confirm it is the official account) |
| How to ADHD | YouTube | @HowtoADHD | resolved, 1.96 M (mega), selected |
| Dani Donovan | TikTok | danidonovan | resolved, 623,200 (macro), selected (guess; operator to confirm identity) |
| Dani Donovan | YouTube | — | no handle known |
| ADHD Alien | TikTok | adhd_alien | resolved, 1,061 (micro), selected. **Suspicious:** the real ADHD Alien is much larger, so this is probably the wrong account. Operator to check |
| ADHD Alien | YouTube | — | no handle known |
| ADHD Dude | TikTok | adhddude | resolved, 58,000 (mid), selected (guess; operator to confirm) |
| ADHD Dude | YouTube | @ADHDDude | resolved, 92,900 (mid), selected (guess; operator to confirm) |

### What the operator needs to do (Task 2)

TikTok has no niche-specific scripted source, so the TikTok sample must come from operator
collection. Use one or more of these:
- **TikTok in-app search (D-16 fallback, ~30–45 min).** For each config query (DE: ADHS,
  Autismus, ADHS Eltern, ADHS Männer, ADHS Papa, Neurodivergenz, Legasthenie, Dyspraxie, Tourette,
  AuDHD; EN: ADHD, autism, ADHD parenting, ADHD men, ADHD dad, neurodivergent, dyslexia,
  dyspraxia, Tourette, AuDHD), open the Accounts tab and the top videos. Note recurring creators
  with ≥ 10 niche posts. Prioritise **mid tier (10k–100k followers)**.
- **Creative Center / Exolyt / Favikon.** Click paths are in `docs/scan-discovery-sources.md`.

Row format for each added handle (8 columns, header unchanged):

```
handle,platform,language,discovery_source,query,seed_named,operator_decision,notes
someadhscreator,tiktok,de,tiktok_app,ADHS Papa,0,include,
someadhdcreator,tiktok,en,creative_center,ADHD men,0,,
```

- `handle`: the TikTok handle without `@` (`^[A-Za-z0-9._]{2,24}$`).
- `discovery_source`: one of `tiktok_app`, `creative_center`, `exolyt`, `favikon` or `modash`.
- `operator_decision`: `include`, `exclude` or blank (quota decides).

For existing rows, act on the `executor suggestion` notes: set `exclude`, or edit `language` for
the English channels currently under `de`. Fix the seed handles hey_mamaleben, verena_eisbrenner,
guardianofmind and adhd_alien if the correct ones are known.

Targets: ~40 per language (28 TikTok / 12 YouTube), and **≥ 8 usable mid-tier TikTok accounts per
language**. Currently: DE has 2 TikTok and 0 mid TikTok; EN has 4 TikTok and 1 mid TikTok.

## Operator review (Task 2)

Operator reply: "list edited". Two orchestrator commits applied the edits:
- `48f0b68`: the executor's exclude/relabel suggestions, as approved by the operator. 12 rows
  set to `exclude` (news outlets, brands, kids' news, off-niche channels, and the suspect seeds
  hey_mamaleben and adhd_alien). 5 YouTube rows relabelled `de` → `en`.
- `704bd89`: 36 TikTok handles the operator collected in the app (`discovery_source=tiktok_app`),
  18 `en` and 18 `de`. Two are `include`: adhsabenteuer and meinadhsleben.
- The four "check niche" YouTube rows (@GenericArtDad, @Gossipduckling, @SquirrelDad,
  @olivialutfallah) were left blank, so the quota decides.

| discovery_source | rows | include | exclude | blank |
|---|---|---|---|---|
| seed_d04 | 11 | 0 | 2 | 9 |
| ytsearch | 30 | 0 | 10 | 20 |
| tiktok_app (added) | 36 | 2 | 0 | 34 |
| **total** | **77** | **2** | **12** | **63** |

## Final sample

Runs on 2026-10-25, outside the quiet hours, no `--force`, rule sha256 `ea401c5d…1b904b04`:

| Step | Command | UTC | scan_run | Result |
|---|---|---|---|---|
| Re-import | `scan import-candidates scan/candidates.csv` | 07:21 | — | inserted 36, updated 41, rejected 0 |
| Profile fetch | `scan fetch --stage profile` | 07:22:06–07:25:15 | 19 | ok 36, skipped fresh 24, failed 5, stopped 0 |
| Select DE | `scan select --lang de` | 07:25:26 | 20 | total 20 |
| Select EN | `scan select --lang en` | 07:25:28 | 21 | total 30 |

All 36 operator-added TikTok handles resolved; none failed. The 5 failures are the same ones as
before: 3 YouTube channels without a Shorts tab (@bvlegasthenie, @autismusspektruminfo,
@AdventuresofNeryn), plus the seeds verena_eisbrenner and guardianofmind (no data). The fetch
also retried @RDXMixer, which is excluded.

Check: 0 mismatches between `operator_decision` and `status`. Both `include` rows are
`selected`, and no `exclude` row is.
Status counts: 50 selected, 12 excluded, and 15 candidate (below 1000 followers or no data).

### Selected, by language × platform × tier

| Language | Platform | micro | mid | macro | mega | total |
|---|---|---|---|---|---|---|
| de | tiktok | 9 | 7 | 2 | 0 | 18 |
| de | youtube | 2 | 0 | 0 | 0 | 2 |
| **de** | | **11** | **7** | **2** | **0** | **20** |
| en | tiktok | 6 | 7 | 6 | 1 | 20 |
| en | youtube | 4 | 2 | 3 | 1 | 10 |
| **en** | | **10** | **9** | **9** | **2** | **30** |
| **total** | | **21** | **16** | **11** | **2** | **50** |

Against a target of ~40 per language (28 TT / 12 YT, ~80 total), the sample is **50**: DE 20, EN 30.
Shortfalls, verbatim from `scan select`:
- de: `mid tier shortfall: 7 of 12`
- en: `mid tier shortfall: 9 of 12`

Shortfall reason: the selected set is again everything with ≥ 1000 followers that is not
excluded. The quota cut nothing; the pool is the limit. DE YouTube is down to 2 because most
DE-query channels were English (relabelled) or off-niche (excluded). Neither language reaches 30.

### Mid-tier TikTok vs the validity floor (≥ 8 per language)

| Language | mid TikTok selected | of which clearly ND-niche by bio | floor |
|---|---|---|---|
| de | 7: adhsabenteuer, robin.haegle, bene_adhso, neuroceline, adhs.reise, susis_synapsensalat, daily.katze | 6 (daily.katze unclear) | 8 → **short by 1–2** |
| en | 7: adhdventurers, theautismspectrum, messagetodaniel, adhddude, tim.adhd, adhdautism4, le0zs | 6 (le0zs unclear) | 8 → **short by 1–2** |

The operator's in-app collection raised the counts from DE 0 / EN 1 to DE 7 / EN 7. Both
languages are still below the validity floor of 8. This is a finding for MKT-01. Two to four more
mid-tier (10k–100k) ND TikTok handles per language would close the gap.

### Flags on operator-added or blank rows (not excluded; the decision stays the operator's)

Judged from the fetched bio only:
- **daily.katze** (de, TikTok, mid 22.2k): bio "Dinge erklärt von Kadse 👇 Merch👇". This looks
  like a general explainer or cat account, not obviously ND. It counts toward DE mid.
- **le0zs** (en, TikTok, mid 56.9k): bio "See you in hell for the sequel". No ND signal; it may
  be a personal account. It counts toward EN mid.
- **goxlr__** (en, TikTok, micro 1.1k): bio "Berserk X StarWars". Looks off-niche, a personal or
  fandom account.
- **user8445982006957** (de, TikTok, micro 1.8k): the handle is an auto-generated default and the
  bio is empty. Identity and niche are unverifiable.
- **christian_durstewitz** (de, TikTok, macro 330k): bio "MENTAL HEALTH Safespace Depressionen |
  ADHS". ND-adjacent: general mental health with ADHS. Probably fine.
- **@Gossipduckling** (en, YouTube, mid 17.4k, left blank by the operator): bio is celebrity
  gossip. Likely off-niche, and it counts toward EN mid (YouTube).
- Not selected (below 1000 followers): bitecheesechili (945, personal "isfp sx 4w5" bio),
  adhs.wissen (554), and audhs.info (7 followers).
- The seeds verena_eisbrenner and guardianofmind are still "not on platform" (no data). Nobody has
  supplied a corrected handle.

If the operator excludes daily.katze and le0zs, mid-tier TikTok falls to DE 6 / EN 6. Plan 08
collects posts for exactly the 50 `selected` rows unless the operator changes decisions first.

## Operator top-up (2026-10-25 07:43 UTC)

Operator added 9 TikTok handles (EN: neuroduck0, adhdminds111, unique_adhd, hypeneo1, lix.psl; DE: jannes_patrick, leoniemachtsachen, adhs_deutschland, lebenmitadhs) and declared the list final ("So thats it"). Operator chose to KEEP the flagged possibly-off-niche accounts (daily.katze, le0zs, goxlr__, user8445982006957, @Gossipduckling).
scan_run 22 (profile): ok 9, failed 5 (known). Re-select: de total 24 (mid 8), en total 35 (mid 13).
Mid-tier TikTok after top-up: DE 8 (adhs.reise, adhsabenteuer, bene_adhso, daily.katze, jannes_patrick, neuroceline, robin.haegle, susis_synapsensalat) — exactly at the validity floor before the ≥8-posts check; EN 11.

## Collection — posts

Plan 01-08, 2026-10-25, outside the quiet hours, no `--force`, rule sha256 `ea401c5d…1b904b04`.
Pre-registration ordering holds: rule commit b644eae (2026-10-24T21:03:08Z) precedes the first
scan_run (2026-10-24T21:18:20Z). No scan_run note contains `quiet_hours_override`.

| Step | Command | UTC | scan_run | Result |
|---|---|---|---|---|
| Posts DE | `scan fetch --stage posts --lang de` | 07:45:58–07:51:24 | 25 | ok 23, skipped fresh 1 (kirmesimkopf, plan 04), failed 0, stopped 0 |
| Posts EN | `scan fetch --stage posts --lang en` | 07:56:34–08:16:06 | 26 | ok 34, skipped fresh 1 (@HowtoADHD, plan 04), failed 0, stopped 0 |

Requests: TikTok one flat listing per account (playlistend 30); YouTube one Shorts listing plus
18 per-video calls per channel (12 channels → ~228 calls). 3–6 s jitter throughout. No 429/403,
no platform stop, so no `add-manual` / `operator_entered` fallback was needed.

Selected accounts with posts: 59 of 59 (DE 24, EN 35). 1681 posts stored, 861 in the reach
window (newest 15 posts ≥ 72 h old, pinned excluded).

### Accounts by language × platform × tier, with ≥ 8 reach-window posts (usable for reach metrics)

| Language | Platform | micro | mid | macro | mega | total | ≥ 8 reach posts |
|---|---|---|---|---|---|---|---|
| de | tiktok | 11 | 8 | 3 | 0 | 22 | 22 |
| de | youtube | 2 | 0 | 0 | 0 | 2 | 2 |
| **de** | | 13 | 8 | 3 | 0 | **24** | **24** |
| en | tiktok | 6 | 11 | 7 | 1 | 25 | 24 |
| en | youtube | 4 | 2 | 3 | 1 | 10 | 10 |
| **en** | | 10 | 13 | 10 | 2 | **35** | **34** |

**Usable mid-tier TikTok (n_reach_posts ≥ 8): DE 8 / EN 11.** DE is exactly at the validity
floor of 8 (susis_synapsensalat, adhsabenteuer, neuroceline, adhs.reise, robin.haegle,
bene_adhso, daily.katze, jannes_patrick — all 15 reach posts). EN: 11 (neuroduck0 has 13, the
rest 15).

Short of 8 reach posts:
- **audhd30** (en, TikTok, micro): 30 posts, 0 in reach window. All 30 listed posts were
  published between 2026-10-24 07:55 and 2026-10-25 08:08 UTC (a burst of ~30 posts in one
  day), so none is ≥ 72 h old within the 30-entry listing. It drops out of reach metrics per
  the rule; not mid-tier, so the floor is unaffected.
- neuropinguin (de, TikTok, micro) has exactly 8 (only 9 posts total) — usable.

Saves/shares per 1k views are exposed on TikTok only; YouTube rows carry views, likes and
comments (saves/shares NULL), as designed.

## Collection — analysis

`ndc-heavy` (3g cap, 1 CPU, nice 19, one thread), outside the quiet hours, no `--force`.
`free -m` during the DE run: ~4.5 GB available (stop threshold 1.5 GB); container at
~1.15 / 3 GiB.

| Step | Command | UTC | scan_run | Result |
|---|---|---|---|---|
| Analyze DE | `ndc-heavy scan analyze --lang de` | 08:17:14–08:47:38 | 27 | 26 accounts processed, 1 already analyzed (kirmesimkopf, plan 06) |
| Analyze EN | `ndc-heavy scan analyze --lang en` | 08:48:00–09:23:08 | 28 | 32 accounts processed |
| Language sync | `scan import-candidates scan/candidates.csv` (unchanged CSV, after fix 056a77f) | 09:24 | — | updated 86, 0 account/candidate language mismatches left |
| Bundles | `scan prepare-judging` | 09:25 | — | see batches below |
| Queue | `scan queue` | 09:25 | — | queued 12, clear 74 (all fetched accounts) |

`--lang` filters on the account's language. Before the fix, 3 operator-relabelled EN YouTube
channels (@PashaMarlowe, @AllAboutSpeechTherapy, @sociallyausome) still carried `de` on
competitor_account, so they were analyzed in the DE run. That changes nothing in the
analysis, but the sheet and the judging bundles group by account language, so the language
had to be synced before `prepare-judging`.

### Per selected account (grouped by candidate language)

| Language | Platform | accounts with videos | videos ok | videos unavailable | non-empty transcripts |
|---|---|---|---|---|---|
| de | tiktok | 22 / 22 | 66 | 0 | 51 |
| de | youtube | 2 / 2 | 6 | 0 | 5 |
| en | tiktok | 24 / 25 | 71 | 1 | 46 |
| en | youtube | 10 / 10 | 29 | 1 | 27 |
| **total** | | **58 / 59** | **172** | **2** | **129** |

- No account has all of its downloads unavailable.
- Unavailable videos:
  - unique_adhd: one post had no video formats (2/3 ok).
  - @SquirrelDad: one HTTP 403 (2/3 ok).
  - Neither was retried with a login.
- **audhd30** has no competitor_video row. It has 0 posts ≥ 72 h old (see Collection — posts), so
  there was nothing eligible to analyze. It drops out per the rule.
- ok videos with an empty transcript (43): music-only or no-speech clips.
- Mean wall-clock per video attempt: ~23 s (171 attempts in 3,932 s). That includes download,
  decode, whisper, pitch, frame sampling and the 3–6 s pacing. Transcription was not timed
  separately.
- Contact sheets: 48 of 58 analyzed accounts. The other 10 TikTok accounts got no frames:
  adhdsciences, adhdventurers, adhdautism4, myadhdventure, adhsabenteuer, meinadhsleben,
  gedankenflut.fuehlen, adhs.reise, adhdminds111, lebenmitadhs.
  - Probe of one adhdsciences post (one metadata request): yt-dlp exposes only an audio-only m4a
    for it. That means a TikTok photo carousel, which has no video stream to sample.
  - Their transcripts and pitch exist. The judging session sees captions and transcripts but no
    images for these accounts.
  - **Carousel/slideshow is itself a format signal.** The format, face and on-screen-citation
    fields for these 10 accounts should go to the operator queue if the judge is unsure.
- `find /home/nd-content-volumes/data/media -type f | wc -l` → **0** (probe dir also removed).

### Judging batches

| Batch | Accounts | Manifest |
|---|---|---|
| de-1 | 12 | /data/judging/de-1/manifest.json |
| de-2 | 12 | /data/judging/de-2/manifest.json |
| en-1 | 18 | /data/judging/en-1/manifest.json |
| en-2 | 17 | /data/judging/en-2/manifest.json |

59 selected accounts in total (DE 24, EN 35). Host paths are under
`/home/nd-content-volumes/data/judging/`.

## Decision (plan 01-13, 2026-10-25)

- Operator spot-check: 32 queued accounts closed by category rulings (4 score overrides, 4 exclusions,
  28 accepted as judged). Queue: 0.
- `ndc scan export --csv scan/competitor_sheet.csv` → 86 rows.
- `ndc scan decide` (DB source, 55 selected accounts) → **R1 → German** (Q 0.56, N_DE 2, S_DE 0).
- Full log with metrics and reasoning: [docs/language-decision.md](language-decision.md).
