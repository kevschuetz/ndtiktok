# Competitor-scan discovery sources: live verification (D-04, D-16)

Verified 2026-10-24, 21:15–21:26 UTC, from the nd-content container. Method for the TikTok
sources: at most 3 plain HTTP GET requests per source, ~4 s apart, one fixed desktop User-Agent,
no cookies, no login, no JavaScript execution, no impersonation library, no paid API. A page that
needs JS, an account or a bot check is never worked around; it becomes `operator-browser` or
`unavailable`.

| Source | Verdict | Use |
|---|---|---|
| Research-named seeds (D-04) | scripted | Always in `scan/candidates.csv` (`seed_named=1`) |
| YouTube `ytsearch` | scripted | `ndc scan discover youtube --lang de|en` |
| TikTok Creative Center | operator-browser | Operator's own browser, CSV import |
| Exolyt | operator-browser | Operator's own browser (free account), CSV import |
| Favikon | operator-browser | Operator's own browser (free account), CSV import |
| Modash public pages | scripted | `ndc scan discover modash --lang de --path tiktok/<page>` |
| TikTok in-app search (D-16 fallback) | operator-browser | Fallback only, see the end of this doc |

Every operator-collected handle goes into `scan/candidates.csv` with `discovery_source` set to the
source name (`creative_center`, `exolyt`, `favikon`, `modash`, `tiktok_app`) and `query` set to the
term searched. Then run `ndc scan import-candidates scan/candidates.csv`.

## Research-named seeds (D-04)

- Date: 2026-10-24. Method: `config/scan.yaml` `seeds:` → `scan/candidates.csv`.
- DE: kirmesimkopf, nessadhs, hey_mamaleben, verena_eisbrenner, guardianofmind (TikTok handles).
- EN: How to ADHD (YouTube `@HowtoADHD`, TikTok guess `howtoadhd`), Dani Donovan (TikTok guess
  `danidonovan`), ADHD Alien (TikTok guess `adhd_alien`), ADHD Dude (YouTube guess `@ADHDDude`,
  TikTok guess `adhddude`). The guesses are marked "handle unverified" in the CSV notes;
  `ndc scan fetch --stage profile` confirms or rejects them.
- Live: `kirmesimkopf` (TikTok, 5,046 followers) and `@HowtoADHD` (YouTube, 1.96 M subscribers)
  were fetched end-to-end on 2026-10-24.
- **Verdict: scripted.**

## YouTube ytsearch

- Date: 2026-10-24 21:15 UTC (shape probe), 21:20–21:26 UTC (real discovery runs).
- Request: yt-dlp Python API, `extract_info("ytsearch30:<query> #shorts")`, flat, one request per
  query, 3–6 s apart.
- Result: entries carry `channel_id`, `channel`, `uploader_id` (`@handle`) and `duration`, with no
  login. Creator handles are present.
- Real run, `discover youtube --lang de`: 10 queries, 100 distinct channels seen, 5 new candidates
  with ≥ 3 niche Shorts (@SensoryBlum, @DyspraxieOnline, @PashaMarlowe, @Clips4Freedoom,
  @bvlegasthenie).
- Real run, `--lang en`: 10 queries, ~101 channels seen, 0 new. The 2 hits were already listed:
  @HowtoADHD (EN seed) and @SensoryBlum (found by the DE run first, now flagged "also found by en
  ytsearch queries: check language").
- Findings for plan 07:
  - Most channels appear only 1–2 times across the query results, so `min_niche_shorts: 3` keeps
    very few. Consider 2 (config key `discovery.min_niche_shorts`).
  - "Tourette" and "AuDHD" are the same term in both languages. A channel's language is the
    language of the query that found it first; the operator checks flagged rows.
- **Verdict: scripted.**

## TikTok Creative Center

- Date: 2026-10-24 21:15 UTC. 3 GETs:
  - `https://ads.tiktok.com/business/creativecenter/inspiration/popular/creator/pc/en?region=DE`
  - `.../popular/creator/pc/en?region=AT`
  - `.../popular/hashtag/pc/en?region=US`
- HTTP status: 200 for all three, but every URL redirects to
  `https://ads.tiktok.com/creative/creativeCenter/trends?region=..`. That is a 21 KB JavaScript
  app shell ("TikTok One Creative Suite") with login prompts.
- Creator handles in the plain HTML: **none**. The data loads client-side, and the creator lists
  may need a TikTok For Business login.
- **Verdict: operator-browser.**
- Click path (operator, own browser):
  1. Open `https://ads.tiktok.com/business/creativecenter`. If it asks, log in with your own
     TikTok For Business account (free).
  2. Go to Trends → Creators (or Hashtags). Set the region to Germany, then Austria, then United
     States.
  3. Filter or search for each config query (ADHS, Autismus, ADHS Eltern … / ADHD, autism, ADHD
     parenting …).
  4. Copy each creator handle into `scan/candidates.csv` as `handle,tiktok,de|en,creative_center,
     <query>,0,,`. From the Hashtags view, open the top creators of #adhs / #autismus / #adhd /
     #autism the same way.

## Exolyt

- Date: 2026-10-24 21:16 UTC. 2 GETs:
  - `https://exolyt.com/search?q=adhs`: 200, redirected to `https://app.exolyt.com/search?q=adhs`.
    That is a Next.js app shell with a login and no creator data.
  - `https://exolyt.com/hashtag/adhs`: 404, and the body was a Cloudflare "Just a moment" /
    "Access Denied" interstitial.
- Creator handles in the plain response: **no** (only unrelated links in the error page).
- **Verdict: operator-browser.** The bot interstitial was not touched again.
- Click path: log in at `https://app.exolyt.com` with a free account. Search each config
  query/hashtag, filter by country (DE/AT or US/UK) and copy the handles into
  `scan/candidates.csv` with `discovery_source=exolyt`.

## Favikon

- Date: 2026-10-24 21:16 UTC. 2 GETs:
  - `https://www.favikon.com/`: 200, marketing page, no creator handles.
  - `https://www.favikon.com/search?q=adhs`: 200, a 13 KB "Search Results" shell whose results
    load with JavaScript. No handles.
- Creator handles in the plain response: **no**.
- **Verdict: operator-browser.**
- Click path: create or log in to a free Favikon account. Use its creator search with the
  platform set to TikTok, the country set to Germany/Austria or US/UK, and keywords from the
  config queries. Copy the handles into `scan/candidates.csv` with `discovery_source=favikon`.

## Modash (public find-influencers pages)

- Date: 2026-10-24 21:16–21:17 UTC. 3 GETs:
  - `https://www.modash.io/find-influencers`: 200, index page.
  - `https://www.modash.io/find-influencers/tiktok/germany`: 200, "Top 20 TikTok Influencers in
    Germany". Fetched twice: once for the check, once to inspect the link format.
- Creator handles in the plain HTML: **yes**. The page links them as `https://tiktok.com/@<handle>`
  (25 distinct handles). No login and no bot check was served. The page embeds a reCAPTCHA site
  key for its own forms, but none was triggered.
- Limits:
  - The public pages are generic top-20 lists (country, gender, topic such as `tiktok/skincare`).
  - No ADHD/neurodivergence topic page was confirmed; the 3-GET cap stopped further probing.
  - The full creator search behind the free account needs JS → operator-browser.
- **Verdict: scripted** for public pages (`ndc scan discover modash --lang de --path
  tiktok/germany`; the path must match `tiktok[/<slug>[/<slug>]]`). It is low-yield for this
  niche: use it only when a relevant topic page exists. **Operator-browser** for the free-account
  search, with `discovery_source=modash`.

## Fallback: operator handle collection in the TikTok app (D-16)

Not every TikTok source is unavailable (Modash public pages are scripted), but none of the
scriptable TikTok sources is niche-specific. TikTok in-app search therefore stays the documented
fallback. In one sitting outside 00:15–06:00 UTC (~30–45 min), for each config query: open the
Accounts tab and the top videos, and note the first ~8 distinct recurring creators with ≥ 10
niche posts. Add them to `scan/candidates.csv` with `discovery_source=tiktok_app` and the query.
