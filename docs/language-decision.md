# Language decision log (MKT-02)

## Validation week 1 — language decision 2026-10-25T11:07:11Z

- verdict: **de** (row R1)
- R_DE: 8423.00
- R_EN: 4722.00
- Q: 0.56
- n_mid_de: 8
- n_mid_en: 9
- N_DE: 2
- N_EN: 1
- S_DE: 0
- S_EN: 0
- YouTube Shorts reach (reported only, not in Q): DE n/a, EN 5984.50
- Does a sourced, male, faceless German account exist? **no** (S_DE = 0)
- rule sha256: `ea401c5d7fd18e598fa8f18e759b75c45cbae982e066261c4e90df0b1f904b04`
- sourced DE accounts (N_DE): tiktok:adhs_deutschland, tiktok:luciemenow
- sourced EN accounts (N_EN): youtube:@additudemag
- sample: 55 accounts; per language/platform/tier:
  - de tiktok macro: 3
  - de tiktok micro: 11
  - de tiktok mid: 8
  - de youtube micro: 2
  - en tiktok macro: 7
  - en tiktok mega: 1
  - en tiktok micro: 5
  - en tiktok mid: 9
  - en youtube macro: 2
  - en youtube mega: 1
  - en youtube micro: 4
  - en youtube mid: 2
- pre-registration: rule lock committed 2026-10-24T21:03:08+00:00; first scan_run started 2026-10-24T21:18:20Z; commit precedes the first scan_run: yes
- Q uses TikTok mid-tier reach only; YouTube Shorts reach is reported alongside (D-18). Milestone 1 runs in one language only (D-08).

### Reasoning (validation week 1, 2026-10-25)

**Verdict: German.** Rule row **R1** (`N_DE <= 4 and Q <= 10 -> de`) matched; it is a decisive row, not the
inconclusive fallback.

1. **Validity (V) passed.** Both languages have at least 8 usable TikTok mid-tier accounts (10k–99.9k
   followers, ≥ 8 posts in the reach window): DE 8, EN 9.
2. **Reach ratio Q = R_EN / R_DE = 4722 / 8423 = 0.56.** Typical German mid-tier TikTok reach is *higher* than
   the English one in this sample, so Q is nowhere near the R2 English threshold (> 15).
   - DE mid-tier medians: neuroceline 32,000, jannes_patrick 11,100, adhsabenteuer 10,400, daily.katze 8,914,
     adhs.reise 7,932, bene_adhso 5,816, robin.haegle 1,156, susis_synapsensalat 561 → median 8,423.
   - EN mid-tier medians: adhdminds111 131,900, neuroduck0 65,100, adhdautism4 41,500, messagetodaniel 5,415,
     adhdventurers 4,722, theautismspectrum 2,583, tim.adhd 2,011, unique_adhd 1,097, adhddude 751 → median 4,722.
     English has a few large outliers but a lower middle.
3. **Sourcing gap.** Only 2 German accounts cite sources at level ≥ 2 (N_DE = 2: tiktok:adhs_deutschland,
   tiktok:luciemenow), against 1 English (youtube:@additudemag). N_DE ≤ 4 means German source-citing
   short-form is an open lane.
4. **S_DE = 0 — no sourced, male, faceless German account exists.** Faceless + male German accounts exist
   (daily.katze, neuronbird, neuropinguin), but none cites sources at ≥ 2. The planned slot (sourced,
   male, faceless, German) is empty. S_EN is also 0 after the operator's repost-credit ruling.
5. YouTube Shorts reach is reported only (D-18): DE n/a (no usable DE YouTube mid-tier account), EN 5,984.5.
   It does not enter Q.

Milestone 1 runs in **German only** (D-08). Plans 14 and 15 consume this verdict.

### Operator spot-check (D-17) — rulings 2026-10-25

The uncertainty queue held 32 accounts. The operator ruled by category instead of checking accounts one by one;
every ruling was recorded through `ndc scan verify` (provenance `operator_verified`). No DB row was hand-edited.

1. *"Institutional accounts COUNT as source-citing competitors"* — tiktok:adhs_deutschland and
   youtube:@additudemag keep source_citing_score 2 (operator_verified). (No youtube:adhs_deutschland account
   exists in the sample; only the TikTok one.)
2. *"Repost credits are NOT source citing"* — tiktok:theautismspectrum and tiktok:hypeneo1 set to
   source_citing_score 0 (operator_verified). Both were faceless + male English accounts that would otherwise
   have made S_EN = 2.
3. *"Exclude off-niche English accounts"* — youtube:@GenericArtDad, tiktok:le0zs, tiktok:goxlr__, tiktok:lix.psl
   set to `operator_decision=exclude` in scan/candidates.csv and re-imported (`ndc scan import-candidates`),
   so they left the selected sample before `decide`. tiktok:daily.katze (DE mid-tier) is **kept** — the
   operator's explicit choice.
4. *"Carousel accounts and uncertain face/voice/format fields: accept as unknown/low-confidence"* — the other
   28 queued accounts (incl. the four excluded ones) were closed with `ndc scan verify HANDLE --accept`,
   which logs an operator review and leaves every value as judged.

Effect on the decision: the exclusions removed le0zs (EN mid) and lix.psl (EN mid) from the EN reach set
(n_mid_en 11 → 9); R_EN stayed 4,722 and Q 0.56. The repost ruling moved S_EN from 2 to 0 and N_EN from 3 to 1.
None of the rulings could change the matched row: R1 holds for any Q ≤ 10.

Competitor sheet: `scan/competitor_sheet.csv` (86 accounts incl. non-selected, every MKT-01 field with
per-field provenance; the decision used the 55 selected).
