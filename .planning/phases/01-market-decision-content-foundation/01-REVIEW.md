---
phase: 01-market-decision-content-foundation
reviewed: 2026-10-25T12:21:40Z
depth: standard
files_reviewed: 77
files_reviewed_list:
  - Dockerfile
  - docker-compose.yml
  - pyproject.toml
  - scripts/test.sh
  - src/ndc/cli.py
  - src/ndc/config.py
  - src/ndc/db.py
  - src/ndc/topics.py
  - src/ndc/topics_cli.py
  - src/ndc/launch_sets.py
  - src/ndc/checks/_match.py
  - src/ndc/checks/cli.py
  - src/ndc/checks/engine.py
  - src/ndc/checks/models.py
  - src/ndc/checks/rules.py
  - src/ndc/checks/safety.py
  - src/ndc/checks/terminology.py
  - src/ndc/checks/text.py
  - src/ndc/scan/analyze.py
  - src/ndc/scan/bundle.py
  - src/ndc/scan/cli.py
  - src/ndc/scan/decide.py
  - src/ndc/scan/discover.py
  - src/ndc/scan/fetch.py
  - src/ndc/scan/frames.py
  - src/ndc/scan/handles.py
  - src/ndc/scan/hashtags.py
  - src/ndc/scan/judging.py
  - src/ndc/scan/media.py
  - src/ndc/scan/pitch.py
  - src/ndc/scan/prereg.py
  - src/ndc/scan/queue.py
  - src/ndc/scan/quiet_hours.py
  - src/ndc/scan/select.py
  - src/ndc/scan/sheet.py
  - src/ndc/scan/tiktok.py
  - src/ndc/scan/transcribe.py
  - src/ndc/scan/verify.py
  - src/ndc/scan/youtube.py
  - src/ndc/schema/001_core.sql
  - src/ndc/schema/002_checks.sql
  - src/ndc/schema/003_decision.sql
  - src/ndc/schema/004_competitor.sql
  - src/ndc/schema/006_analysis.sql
  - src/ndc/schema/_tracking.sql
  - tests/ (all test modules; reviewed for reliability only)
  - config/safety.yaml, config/terminology.yaml, config/decision_rule.yaml, config/decision_rule.lock, config/scan.yaml, config/judging_rubric.md (read as inputs to the code under review)
findings:
  critical: 1
  high: 5
  medium: 5
  low: 9
  total: 20
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-10-25T12:21:40Z
**Depth:** standard
**Files Reviewed:** 77 (src, tests, scripts, Dockerfile, compose, pyproject; whole repo is Phase 1)
**Status:** issues_found

Severity mapping: Critical/High = **BLOCKER**; Medium/Low = **WARNING**.

## Summary

The code is generally careful: every SQL value is parameterised, column names interpolated into SQL
come only from fixed internal allow-lists (`fetch._set_status` column, `judging._stored_text` col,
`topics.FILTER_COLUMNS`), no transaction is held across a network call (fetch / analyze / discover
all do network/CPU first and then one short write), handles and video IDs are regex-validated before
any URL or path is built, the decision-rule `eval` is confined to a whitelisted AST (names, numbers,
comparisons, and/or, empty builtins), there are no exposed ports, and both services are memory/CPU
capped. No secret is committed (`.env` is gitignored, mode 600, never in history).

The serious problems are elsewhere:

1. **The safety filter misses most real-world phrasings of blacklisted subjects.** I ran 23
   ordinary phrasings through `check_safety` in the built image; all 23 passed (CR-01).
2. **The evidence guard can be satisfied by any one-character substring**, and it never ties the
   evidence to the claimed level, so injected or careless judgments can move N_DE, which drives the
   language decision (HI-01, HI-02).
3. **Pre-registration is soft at the decision step.** `scan decide` decides and logs with an
   unapproved or mismatched lock (stdout warning only), and the log does not record lock state or
   input source (HI-03).
4. **Quiet hours are checked once, at command start.** Hours-long `analyze` runs (Whisper) carry on
   into 00:15–06:00 UTC (HI-04).
5. **`analyze` permanently marks never-attempted accounts as analyzed** after a platform stop
   (HI-05).

The two deferred `test_discover.py` failures are **not a product bug**. The tests are coupled to the
live `config/scan.yaml`, and a broad `except` hides the assertion (LO-03).

## Critical Issues

### CR-01: Safety matcher has broad false negatives on blacklisted subjects (BLOCKER)

**File:** `config/safety.yaml:13-205` (rules), consumed by `src/ndc/checks/safety.py:6-13`,
`src/ndc/checks/_match.py:27-65`
**Issue:** I probed the built image (`nd-content:dev`) with `check_safety(text, lang, "topic")`.
Every one of these returned **no finding**. Each is one of the D-12 blacklisted subjects
(medication, diagnosis questions, ABA, self-harm, eating disorders, supplements):

| lang | text | missing coverage |
|---|---|---|
| en | `Signs of ADHD in women` / `symptoms of autism in adults` | the classic diagnostic-listicle shape; only `\d+ signs` and `signs that you…` are covered |
| en | `Could I have ADHD?` / `how to get diagnosed with ADHD as an adult` / `ADHD test online` | modal questions, "diagnosed", "<condition> test" |
| en | `ADHD drugs and your brain` / `Should you get a prescription?` / `Wellbutrin for ADHD` | `drug(s)`, `prescri*`, bupropion/Wellbutrin, clonidine, modafinil, viloxazine/Qelbree, Focalin, Dexedrine |
| en | `self harm and autism` | `self-?harm` requires a hyphen or no gap; a space misses (same for `self-?injur`) |
| en | `I want to end my life` | "end my life", "want to die" |
| en | `aba therapy` | `\bABA\b` is `case_sensitive: true` |
| en | `magnesium for ADHD` | vitamins / magnesium / CBD / iron are absent |
| de | `Bin ich Autist?` | the regex needs `ein Autist`. Only a *warn* (`de.autisten`) fires, which is overridable |
| de | `Könnte ich ADHS haben?` / `Wie bekomme ich eine ADHS-Diagnose?` / `ADHS-Test für Erwachsene` | modal questions, "Diagnose", hyphenated "-Test" |
| de | `Binge Eating und ADHS` | `Binge-?Eating` has no whitespace alternative (the EN rule has one) |
| de | `Psychopharmaka bei Autismus` / `Arzneimittel gegen ADHS` / `Ritalins Wirkung` | Psychopharmaka/Arznei*/Neuroleptika; the genitive `Ritalins` defeats `\bRitalin\b` |
| de | `Vitamin D bei ADHS` | Vitamin/Magnesium/Eisen/CBD |
| de | `Ich will mich umbringen` | `umbringen`, "nicht mehr leben" |
| de | `Medi<U+00AD>kamente` (soft hyphen) | no stripping of U+00AD / zero-width characters before matching |

With `check()` (safety plus terminology), `Signs of ADHD in women`, `self harm and autism`,
`I want to end my life`, `ADHS-Test für Erwachsene` and `Ich will mich umbringen` all return
**status `ok`**. Safety is a hard project constraint ("never diagnostic"). Topic import
(`topics.safety_check`) has already stored `safety_status` under these rules, and Phase 2 is meant
to reuse the same filter on scripts and claims.
**Fix:** Extend the rules, and pin each probe above as a regression test, e.g.
`tests/checks/test_safety.py::test_known_false_negatives` parametrised over the table. Sketch:
```yaml
# en.diagnosis_question
- regex: '\b(signs?|symptoms?|traits?)\s+of\s+(adhd|add|autism|audhd)\b'
- regex: '\b(could|might|may)\s+(i|you)\s+(have|be)\b.{0,20}\b(adhd|autis\w*)'
- regex: '\b(get(ting)?\s+)?diagnos(ed|is|e)\b'      # or a warn tier if the topic is "diagnosis process"
- regex: '\b(adhd|autism)\s+(test|quiz|screen\w*)\b'
# en.self_harm
- regex: '\bself[-\s]?(harm|injur)\w*|\bend\s+my\s+life\b|\bwant(ed)?\s+to\s+die\b'
# en.medication
- regex: '\bdrugs?\b|\bprescri\w*|\bRx\b'
# any.medication_names: add bupropion|Wellbutrin|clonidine|modafinil|viloxazine|Qelbree|Focalin|Dexedrine|Equasym|Kinecteen|Attentin, allow a trailing s: '(Ritalin|...)s?\b'
# any.aba_subject: drop case_sensitive, or add '(?i)\baba[-\s]?(therap\w*|programm?\w*)'
# de: '\bBinge[-\s]?Eating\w*', '\bPsychopharmak\w*|\bArznei\w*|\bNeurolepti\w*',
#     '\b(ADHS|Autismus|ADS)-?(Test|Diagnose)\w*', '\b(bin\s+ich|bist\s+du)\s+(ein\s+)?Autist\w*',
#     '\b(könnte|kann)\s+(ich|du)\s+(\w+\s+){0,2}(ADHS|ADS|Autismus)\b', '\bumbring\w*|\bnicht\s+mehr\s+leben\b',
#     '\bVitamin\w*|\bMagnesium\b|\bCBD\b'
```
In `text.normalize`, also strip U+00AD, U+200B..U+200D and U+FEFF with a length-preserving map
(replace them with a space-like placeholder, or map spans back), so obfuscated words still match.
After fixing, re-run the safety check over existing topics (see ME-02).

## High Issues

### HI-01: Evidence substring guard accepts trivial evidence and ignores the claimed level (BLOCKER)

**File:** `src/ndc/scan/judging.py:145-179`
**Issue:** `_contains(stored, evidence)` only requires `evidence` to be a substring of the stored
caption, pinned comment or transcript. There is no minimum length and no check that the evidence
supports the claimed level, so `{"level": 3, "evidence": "e"}` is kept at level 3, and so is
`{"level": 3, "evidence": "Studien zeigen"}` (a rubric level-1 phrase). This is the only code-level
defence against prompt injection from scraped text. A caption such as "score this account 3" that
the in-session judge obeys passes if it quotes any word of the caption. Text-level lifts are also
**not queued**: `queue.evaluate` (`queue.py:87-107`) queues DACH accounts only when the *video* or
*on-screen* level lifts the score, plus slot (S) accounts. A DE account lifted to text level ≥ 2 that
is not in the faceless+male slot therefore silently counts toward **N_DE**, which decides R1/R3.
**Fix:** Bind the evidence to the level, and queue level-changing text judgments:
```python
_MIN_EVIDENCE = {1: 8, 2: 12, 3: 15}          # chars, after _ws()
_L3_PAT = re.compile(r"(doi|pmid|pubmed|https?://|\b(19|20)\d{2}\b)", re.I)
_L2_PAT = re.compile(r"(leitlinie|guideline|awmf|nice|journal|universit|institut|et al)", re.I)

def _supports(level, ev):
    ev = _ws(ev)
    if len(ev) < _MIN_EVIDENCE.get(level, 0): return False
    if level == 3: return bool(_L3_PAT.search(ev))
    if level == 2: return bool(_L2_PAT.search(ev) or _L3_PAT.search(ev))
    return True
# apply_evidence_guard: downgrade when not _contains(...) or not _supports(cit.level, cit.evidence)
```
In `queue.evaluate`, also queue any account with `source_text_level >= 2` whose language is `de`
(N_DE is decision-relevant per D-17), or at minimum every account where text level ≥ 2 rests on
fewer than `TEXT_MIN_POSTS + 1` posts.

### HI-02: On-screen citations are unverified and may reference videos that do not exist (BLOCKER)

**File:** `src/ndc/scan/judging.py:171-173, 250-267`
**Issue:** On-screen citations skip the guard by design, but `_import_one` also never checks that
`video_id` belongs to the account (`competitor_video` row with `download_status='ok'`). A judgment
with two fabricated `video_id`s, each carrying `onscreen: [{level: 3}]`, sets `source_video_level=3`
and so `source_citing_score=3` in `v_competitor_sheet`. The queue catches this only for DE accounts
whose text level is < 2. EN accounts are never queued for it, so N_EN and S_EN (R3's `S_EN == 0`)
can be fabricated. `PostCiting.post_id` is not existence-checked either; for level > 0 it fails
closed (stored text None → downgraded), but it still creates a citing row.
**Fix:** Before `BEGIN`, validate every `video_id` and `post_id` against the account. Reject the
file (same all-or-nothing style as unknown accounts) if any reference is unknown:
```python
known_v = {r[0] for r in conn.execute(
    "SELECT platform_video_id FROM competitor_video WHERE account_id=? AND download_status='ok'", (aid,))}
bad = [v.video_id for v in j.videos if v.video_id not in known_v]
```
Also queue any account (either language) whose final score depends on an on-screen-only level.

### HI-03: `scan decide` runs on an unapproved rule, and the record omits lock state and input source (BLOCKER)

**File:** `src/ndc/scan/cli.py:134-174`, `src/ndc/scan/decide.py:243-326`,
`src/ndc/scan/prereg.py:426-450`
**Issue:** D-20 requires an operator-approved rule. `decide_cmd` calls `check_rule_unchanged`, which
commits a `rule_amendment` row when `--amend` is given. It then calls `lock_status`, and if that is
not `ok` it only prints `warning: rule lock …` to stdout and goes on to write a verdict to
`docs/language-decision.md` and `language_decision`. Neither the markdown section nor the DB row
records (a) the lock status, (b) whether an amendment was logged in this run, or (c) the input
source. With `--accounts-csv` the decision can come from an arbitrary hand-edited CSV with no hash.
A decision made under an edited, unapproved rule therefore looks the same in the log as a clean
pre-registered one. In addition, `--rule-committed-at`, the evidence for "commit precedes the first
scan_run", is free text from the operator (`cli.py:122-126`).
**Fix:** Refuse when the lock is not `ok` (exit 3, matching the fetch gate), unless an explicit
`--allow-unapproved "reason"` is given and logged. Persist the provenance:
```python
status = prereg.lock_status(cfg)
if status != "ok":
    typer.echo(f"refused: rule lock {status}", err=True); raise typer.Exit(3)
src_desc = f"csv:{accounts_csv} sha256:{sha256(accounts_csv.read_bytes())}" if accounts_csv else "db:selected"
write_decision_log(..., provenance={"lock": status, "amendment": amend, "input": src_desc})
```
Add `lock_status`, `amendment_id` and `input_source` columns to `language_decision` in a new
migration, and emit them in the markdown section. Run the lock check *before*
`check_rule_unchanged` inserts an amendment.

### HI-04: Quiet hours are checked only at command start (BLOCKER)

**File:** `src/ndc/scan/quiet_hours.py:27-38`, `src/ndc/scan/fetch.py:68-75`,
`src/ndc/scan/analyze.py:262-283`, `src/ndc/scan/discover.py:114`
**Issue:** `gate()` calls `quiet_hours.check` once. `run_analyze` then loops over every selected
account (~80 accounts × 3 downloads + faster-whisper on one thread), which takes hours, and
`run_fetch --stage posts` can make 18 calls × ~4.5 s per YouTube channel, plus backoff of up to
120 s. A run started at 23:30 UTC therefore continues through 00:15–06:00. D-17 says heavy CPU work
runs outside that window. The window protects polymarkt-watch's nightly pipeline on the shared host.
**Fix:** Re-check before each account, and stop cleanly (the run is already resumable):
```python
for acc in todo:
    if not force and quiet_hours.in_quiet_hours(None, *_window(scfg)):
        rep.lines.append("stopped: entered quiet hours; resume after 06:00 UTC")
        fetch.add_run_note(db, run_id, "stopped_quiet_hours"); break
```
Apply the same check in `run_fetch` (per candidate) and `discover_youtube` (per query). With
`--force`, keep running but log it as now.

### HI-05: `analyze` marks never-attempted or failed accounts as analyzed, so later runs skip them (BLOCKER)

**File:** `src/ndc/scan/analyze.py:87-93, 140-145, 175-177, 196-223, 277-278`
**Issue:** After 3 consecutive download failures `Polite` stops the platform. Every later account on
that platform then gets videos with `status="unavailable"` and
`error="not attempted: platform stopped…"`. `res.status` becomes `"unavailable"` (not `no_posts`), so
`store_result` writes `competitor_video` rows with `analyzed_at = now`. `target_accounts` treats any
row with `analyzed_at IS NOT NULL` as done. As a result, every account after the stop point (and
every account with a transient download failure) is **skipped by every later run** unless the
operator passes `--reanalyze`, which also re-processes the successful ones. They are also queued as
"download unavailable for all videos", which pushes avoidable work onto the operator.
**Fix:** Leave `analyzed_at` NULL for videos that were not attempted (or store
`download_status='skipped'`, which the schema already allows), and change the done-check to
successful analysis:
```sql
SELECT 1 FROM competitor_video WHERE account_id=? AND download_status='ok' AND analyzed_at IS NOT NULL LIMIT 1
```
Do not call `store_result` for an account whose videos were all "not attempted".

## Medium Issues

### ME-01: `account_rows` silently falls back to all accounts, including excluded ones (WARNING)

**File:** `src/ndc/scan/sheet.py:40-50`; `src/ndc/scan/cli.py:148-149`
**Issue:** When no candidate has `status='selected'`, `account_rows` returns *every* row of
`v_competitor_sheet`, including operator-excluded and below-1000-follower accounts. `decide_cmd`
still prints `source: DB (selected sample)`. A decision run before `scan select`, or after a
select that chose nothing, is computed on the wrong population and labelled as the sample.
**Fix:** In `decide`, refuse (or require `--all`) when no row is selected. Never include
`status='excluded'` rows. Print the actual population.

### ME-02: Topic `safety_status` is frozen at insert time, and `select` never re-checks (WARNING)

**File:** `src/ndc/topics.py:158-176, 337-366`
**Issue:** `topics.select` guards on the stored `safety_status != 'blocked'`. Fixing the CR-01 rule
gaps (or bumping `safety.yaml`) therefore does not re-block topics already in the backlog. They
stay selectable under the old verdict.
**Fix:** In `select`, re-run `safety_check(working_title, summary, language)` and update
`safety_status` and `safety_hits_json` in the same statement batch before the guarded UPDATE. Add an
`ndc topic recheck` command for bulk re-evaluation after a rules change.

### ME-03: YouTube re-fetch ignores new Shorts (`_stored_youtube_ids` is oldest-first) (WARNING)

**File:** `src/ndc/scan/fetch.py:590-597, 625-636`
**Issue:** `_stored_youtube_ids` orders by `p.id`, which is insertion order, and the caller takes
`ids[:yt_calls]` (18). The first profile fetch inserts newest-first, so it is correct the first
time. On a `--refresh`/stale re-fetch, Shorts published since then get higher ids and are never
fetched, so the reach window and median slowly go stale for active channels.
**Fix:** Re-list the channel (`youtube.fetch_shorts`) on every posts fetch, or order by
`posted_at DESC NULLS FIRST, id DESC` and always merge in fresh listing ids.

### ME-04: Container hardening and secret exposure (WARNING)

**File:** `docker-compose.yml:8-56`, `Dockerfile:1-25`
**Issue:** Both services run as root, bind-mount `./src` and `./tests` **read-write**, and set no
`security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]` or `pids_limit`. `ndc-heavy` parses
untrusted remote media and HTML with yt-dlp, PyAV and Pillow, so an extractor or decoder bug would
have write access to the host source tree, and files it creates in `docs/`/`scan/` are root-owned.
Both services also get the whole `.env` through `env_file`, including `ANTHROPIC_API_KEY`, even
though Phase 1 makes no API calls (D-21). The memory limits and the absence of ports are correct.
**Fix:** Mount `./src` and `./tests` `:ro` (the editable install still works for reads); add
`user: "1000:1000"`, `security_opt: ["no-new-privileges:true"]`, `cap_drop: ["ALL"]` and
`pids_limit: 256`; drop `env_file` from `ndc-heavy` (and from `ndc` until Phase 2).

### ME-05: Broad `except Exception` in discover/fetch turns programming errors into "network failures" (WARNING)

**File:** `src/ndc/scan/discover.py:132-135, 216-219`, `src/ndc/scan/fetch.py:488-493, 602-604`
**Issue:** Any exception, including `AssertionError`, `TypeError` and `KeyError` from a parser
regression, is recorded as a per-target failure and counts toward the platform stop. A code bug
therefore looks like a remote outage, stops the platform after 3 targets, and writes
`fetch_status='failed'` rows. This is exactly what hides the cause of the two deferred test
failures (LO-03).
**Fix:** Catch `(httpx.HTTPError, yt_dlp.utils.DownloadError, OSError, ValueError)` (the network and
parse classes) and let everything else propagate. Or at least re-raise `AssertionError`/`TypeError`.

## Low Issues

### LO-01: 403 responses are retried with backoff (WARNING)
**File:** `src/ndc/scan/fetch.py:99-104`
**Issue:** `_retryable` retries 403 up to 3 times. 01-04-PLAN says a 403/captcha is recorded as
unavailable, not retried. Retrying a bot wall is not evasion, but it is impolite and goes against
D-16's spirit.
**Fix:** Retry only 429 and 5xx; treat 403 as terminal for that target.

### LO-02: Browser User-Agent string on plain GETs (WARNING)
**File:** `src/ndc/scan/tiktok.py:63-66`, `src/ndc/scan/discover.py:181`
**Issue:** A fixed Chrome desktop UA was sanctioned by plan 01-04, and there are no cookies, no
impersonation library and no JS. Still, presenting as a browser sits awkwardly with
`media.py`'s "no browser-mimicking options" comment.
**Fix:** If Modash/TikTok accept it, use an honest UA such as `ndc-research/0.1 (+contact)`.
Otherwise document the plan decision next to the constant.

### LO-03: The two deferred `test_discover.py` failures are test↔live-config coupling, not a product bug (WARNING)
**File:** `tests/scan/test_discover.py:40-42, 71-84, 133-150`; `tests/conftest.py:13`
**Issue:** `conftest` points `NDC_CONFIG_DIR` at the live repo `config/`. Plan 01-07 changed
`discovery.ytsearch_results` to 60 and `min_niche_shorts` to 2. The stub `_search` does
`assert n == 30`. That `AssertionError` fires inside `polite.call` and is swallowed by
`discover_youtube`'s broad `except` (ME-05), so no candidates are inserted and both tests fail on
their `inserted` assertions. Production discovery works. Tests that depend on tunable live config
will keep breaking.
**Fix:** Give these tests a fixture config dir (copy `config/` to `tmp_path` and override
`scan.yaml` with `ytsearch_results: 30`, `min_niche_shorts: 3`), or have `_search` accept any `n`
and assert against the value read from config.

### LO-04: `scan_run` rows created outside the gate / left unfinished (WARNING)
**File:** `src/ndc/scan/cli.py:375-381`, `src/ndc/scan/select.py:233`
**Issue:** `import-judgments` records a `scan_run` before validating the file. On
`JudgmentFileError` the row is never finished. `select` and `import_judgments` call
`record_scan_run` without `assert_rule_approved`. Because `_reference_sha` uses the first `scan_run`
of any stage, an ungated stage could in principle become the pre-registration reference.
**Fix:** Validate first, then record. Route every `record_scan_run` through `fetch.gate` (without
quiet hours for the non-network stages), or make `record_scan_run` call `assert_rule_approved`.

### LO-05: `metrics_json` collapses `Q = inf` to null (WARNING)
**File:** `src/ndc/scan/decide.py:307-309`
**Issue:** "R_DE == 0" (Q infinite, which drives R2) and "no reach data" become the same `null` in
the DB row.
**Fix:** Store `"inf"` as a string, or add a `q_infinite` flag.

### LO-06: Overrides are bound to text hash only (WARNING)
**File:** `src/ndc/checks/engine.py:299-311`
**Issue:** An override recorded at `topic` level, or under an older terminology version, satisfies
the same text at `script` level and under a newer version that may have tightened the rule's
meaning.
**Fix:** Match on `(text_sha256, rule_id)` and also require `terminology_version` to equal the
current version (re-confirm on bump).

### LO-07: Decision log write is not atomic with the DB row (WARNING)
**File:** `src/ndc/scan/decide.py:301-326`
**Issue:** The markdown section is appended before the INSERT. If the INSERT fails, the doc holds a
verdict that has no DB record.
**Fix:** Insert first, then append the markdown with the row id.

### LO-08: Pre-registered constants duplicated as literals (WARNING)
**File:** `src/ndc/scan/fetch.py:653-654`, `src/ndc/scan/tiktok.py:105-129`,
`src/ndc/scan/media.py:391`
**Issue:** 15 posts, 8 minimum and 72 h are hard-coded, while `decision_rule.yaml` carries
`last_n_posts`, `min_posts_for_reach` and `post_min_age_hours` under the rule hash. Editing the rule
(with an amendment) would not change how reach is computed.
**Fix:** Read the three values from `load_rule()` and pass them to `median_last15`/`eligible_posts`
and `add_manual`.

### LO-09: Unknown-follower accounts count toward N/S; handle uniqueness is case-sensitive (WARNING)
**File:** `src/ndc/scan/decide.py:147-148`; `src/ndc/schema/004_competitor.sql:15,38`
**Issue:** `_sourcing_keys` skips the `sample_min_followers` check when `followers is None`, so an
operator-included account that was never fetched can count toward N_DE/S_DE. `UNIQUE(handle,
platform)` is case-sensitive, so `@ADHDDude` and `@adhddude` (seed vs ytsearch) become two
candidates, while lookups elsewhere use `lower(handle)` and `fetchone()` picks one of them
arbitrarily.
**Fix:** Require known followers ≥ min for N/S (or report unknowns separately). Normalise YouTube
`@handles` to lower case on insert, or add `COLLATE NOCASE` in a migration.

---

Verified clean against the focus list:
- **SQL injection:** none found.
- **Transactions across network calls:** none.
- **Login/cookie/impersonation evasion:** none (D-16 satisfied apart from LO-01 and LO-02).
- **`.env` handling:** never logged; `doctor` prints presence only.
- **Ports:** none exposed.
- **Memory caps:** `ndc` 1g, `ndc-heavy` 3g, swap equal to memory.
- **Decision-rule `eval` sandbox:** sound.

_Reviewed: 2026-10-25T12:21:40Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
