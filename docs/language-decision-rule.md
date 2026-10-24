# Language decision rule (pre-registered, MKT-02)

This rule picks the **one** language (German or English) for milestone 1. It is written down and
approved **before** any competitor scan data is fetched. The machine-readable twin is
`config/decision_rule.yaml`. Its sha256 is stored in `config/decision_rule.lock` at approval time.
`ndc scan fetch` refuses to run without a matching lock. After the first scan run,
`ndc scan decide` refuses a changed rule unless `--amend "reason"` is given, and that amendment is
logged in the `rule_amendment` table.

There is no bilingual or "both" outcome (D-08). The other language is a milestone-2 option.

## Definitions

- **Sample.** Competitor accounts in the ND niche, per language (`de` = DACH, `en`) and platform
  (TikTok, YouTube Shorts). Accounts under 1,000 followers/subscribers are excluded.
- **Size tiers** (followers on TikTok, subscribers on YouTube; inclusive bounds):
  micro 1,000–9,999 · **mid 10,000–99,999** · macro 100,000–999,999 · mega ≥ 1,000,000.
- **Account reach `M_a`** = median `view_count` of the account's newest 15 posts that are at least
  72 h old. With fewer than 8 qualifying posts the account is **excluded from reach metrics** but
  still counted for sourcing.
- **Usable mid-tier account** = a **TikTok** account in the mid tier with a valid `M_a`
  (≥ 8 qualifying posts).
- **Mid-tier reach `R_lang`** = median of `M_a` over the usable mid-tier TikTok accounts of that
  language.
- **Reach ratio `Q = R_EN / R_DE`** (TikTok only, D-18).
- **YouTube Shorts reach** (`youtube_R_DE`, `youtube_R_EN`, same definition on mid-tier YouTube
  accounts) is computed and **reported alongside, but never enters Q** (D-18).
- **Sourcing count `N_lang`** = number of sampled accounts in that language (any platform, any tier
  ≥ micro) with final source-citing score ≥ 2. One creator counts once per language: rows with the
  same lower-cased handle are merged; the creator counts if any of its rows scores ≥ 2.
- **Slot count `S_lang`** = accounts counted in `N_lang` that are also **faceless** and
  **male-voiced** (the operator's exact positioning), on the same row. `mixed` and `unknown`
  face/voice values never count.

### Account source-citing score (0–3)

| Score | Meaning | Examples |
|---|---|---|
| 0 | No reference to evidence | pure personal story or opinion |
| 1 | Vague appeal to evidence, nothing findable | "Studien zeigen…", "science says" |
| 2 | Named, findable source, no full reference | "laut S3-Leitlinie ADHS", "a 2021 meta-analysis by Faraone" |
| 3 | Full or linkable citation, or a reference list | "Faraone et al. 2021, Neurosci Biobehav Rev, doi:…" |

- `text_level` = highest level reached in **≥ 3 of the newest 15 posts'** captions/pinned comments
  (a habit, not a one-off).
- `video_level` = highest level reached in **≥ 2 of the analyzed videos** (~3 per account,
  spoken + on-screen citations, D-17).
- **Final score** = the operator's value when present, otherwise `max(text_level, video_level)`.

## Outcome table (evaluated in order; first match wins)

| # | Condition | Verdict | Inconclusive |
|---|---|---|---|
| V | fewer than 8 usable mid-tier TikTok accounts in **either** language | **German** | yes |
| R1 | `N_DE ≤ 4` **and** `Q ≤ 10` | **German** | no |
| R2 | `Q > 15` | **English** | no |
| R3 | `N_DE ≥ 8` **and** `S_DE ≥ 1` **and** `S_EN = 0` | **English** | no |
| R4 | anything else | **German** | yes |

## Rationale per row

- **V (D-07).** With fewer than 8 usable mid-tier accounts per language, the reach ratio is noise.
  Inconclusive data resolves to German.
- **R1 (D-06).** The primary signal is sourcing gap plus reachable audience: few DACH accounts cite
  sources at score ≥ 2 (≤ 4, about 10% of a ~40-account sample) **and** DACH mid-size reach is
  within roughly 5–10× of English (`Q ≤ 10`).
- **R2.** Above 15× the DACH audience is too small to be worth the sourcing gap; English wins.
- **R3.** German sourcing is no gap (≥ 8 sourced DACH accounts), a sourced, male, faceless German
  account already exists, and the same slot in English is empty: English.
- **R4 (D-07).** Everything else — the gray band `10 < Q ≤ 15`, or `5 ≤ N_DE ≤ 7` — resolves to
  German.

## Decision log

`ndc scan decide` prints every metric (`R_DE`, `R_EN`, `Q`, `n_mid_de`, `n_mid_en`, `N_DE`,
`N_EN`, `S_DE`, `S_EN`, YouTube reach reported only), the matched row and the verdict. It appends a
dated "Validation week 1" section to `docs/language-decision.md` and inserts a `language_decision`
row. The log must explicitly answer: **does a sourced, male, faceless German account exist?**
(`S_DE ≥ 1`).

## Approval

- approved_by:
- approved_at:
- sha256:
