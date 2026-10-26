# Phase 2 — Live-Run (Plan 02-10)

**Topic 2 · „Wenn Anfangen schwerer ist als Durchhalten“** (ADHS, Exekutivfunktionen, nd_adults, whitelist, safety ok) ·
Datum 2026-10-26, 18:18–18:30 UTC (außerhalb der Ruhezeit 00:15–06:00) · DB `/data/ndc.db` · Operator-Workflow inline, keine Subagenten.

Ablauf: `source search` → `source search --query` → `source pick` → `check-ids` → `corpus lock` → `script draft --punch`
(Draft + Editor + Verify) → 2 × `script export` / `script import` (selektives Re-Verify) → Phone-Review → `script sources`.

---

## Kriterium 1 — Retrieval + unveränderliche Snapshots

```
docker compose run --rm ndc source search 2
```
Query: `("Attention Deficit Disorder with Hyperactivity"[MeSH] AND ("executive function"[tiab] OR procrastination[tiab] OR "task initiation"[tiab] OR planning[tiab])) NOT "Retracted Publication"[pt] NOT ("animals"[MeSH] NOT "humans"[MeSH])`
→ search_run 7, 26 Kandidaten, Facetten phenomenon/mechanism/help; Treffer kinderlastig und off-target (Schwangerschafts-Leitlinie, Concussion). Zwei Pharmakologie-Titel ⚠ geflaggt (`title:pharmacolog`, `en.supplements`).

```
docker compose run --rm ndc source search 2 --query '"Attention Deficit Disorder with Hyperactivity"[MeSH] AND adult*[tiab] AND (procrastination[tiab] OR "task initiation"[tiab] OR "executive function*"[tiab] OR "delay aversion"[tiab] OR "motivational deficit*"[tiab] OR "getting started"[tiab])'
```
→ search_run 8, 28 Kandidaten (Facette `custom`), 7 SR/MA in den Top 11. Auswahl nach Script-Bogen (Erleben → Warum → Was hilft):

```
docker compose run --rm ndc source pick 2 9 10 11 6
```
| Rang | Quelle | Tier | Snapshot(s) | Sätze | OA-Volltext |
|---|---|---|---|---|---|
| 9 | Boonstra et al. 2005, *Psychol Med* — EF in adult ADHD: meta-analytic review (PMID 16116936) | SR/MA | 7 | 6 | nein |
| 10 | Lopez et al. 2018, *Cochrane* — CBT for ADHD in adults (PMID 29566425) | SR/MA | 8 | 25 | nein (PMC-ID vorhanden, kein OA-XML) |
| 11 | Cortese et al. 2012, *Am J Psychiatry* — meta-analysis of 55 fMRI studies (PMID 22983386) | SR/MA | 9 | 12 | nein |
| 6 | Kim et al. 2025, *Medicine* — MBIs for adults with ADHD: SR + MA (PMID 40958241) | SR/MA | 10 (Abstract), 11 (Volltext) | 14 / 127 | **ja** (Europe PMC, Sektionen Abstract/Introduction/Results 3.1–3.6/Discussion/Conclusion) |

`source_snapshot`: sha256-gehashte, append-only Snapshots; `source_sentence` nummeriert mit Sektion. Insgesamt jetzt 11 Snapshots / 9 Quellen in der DB.

**AWMF S3 (028-045):** nicht Teil dieses Runs — der Operator hat die PDF noch nicht hochgeladen (Plan 02-06 Task 2 offen; Anubis-Bot-Check, kein programmatischer Download). Import-Pfad `ndc source import-awmf` ist mit Tests belegt (584b801).

```
docker compose run --rm ndc corpus lock 2
→ corpus 3 sha256 95185f942b0ac369db3dc3f0a329e9858d10ae78c9f978457bf5b063036b8731 (5 Snapshots)
```
Beobachtung: die Lock-Warnung „keine help-Quelle" feuerte nicht, weil `--query`-Kandidaten die Facette `custom` tragen (Lopez/Kim sind inhaltlich help). Follow-up: `custom`-Kandidaten in der Warnung gesondert behandeln oder Facette beim Pick setzen lassen.

## Kriterium 2 — Grounded Draft, zitierte Satz-IDs, ID-Check blockt

```
docker compose run --rm ndc source check-ids --topic 2
```
| Quelle | PMID | Status |
|---|---|---|
| 6 Boonstra 2005 | 16116936 | ok |
| 7 Lopez 2018 | 29566425 | ok |
| 8 Cortese 2012 | 22983386 | ok |
| 9 Kim 2025 | 40958241 | ok |

```
docker compose run --rm ndc script draft 2 --punch        # 2 min 17 s wall clock
```
- Version 8 (v1, `draft`, 182 Wörter, checks ok) → Version 9 (v2, `edit` durch Editor-Pass, 186 Wörter), sha `5e437e1b…`.
- Jeder zitierende Satz trägt `script_citation`-Zeilen auf `source_sentence` (Marker `⟦snapshot:ordinal⟧`), z. B. `⟦7:3⟧` = Boonstra RESULTS Satz 3, `⟦11:64⟧` = Kim Volltext Discussion Satz 64.

**Negativfall (Scratch-DB, kein LLM-Spend):**
```
cp /home/nd-content-volumes/data/ndc.db /home/nd-content-volumes/data/tmp/neg.db
# source 9 (Kim 2025) DOI → 10.1371/journal.pone.9999999
docker compose run --rm -e NDC_DB=/data/tmp/neg.db ndc source check-ids --topic 2 --force
→ source 9: unresolvable
docker compose run --rm -e NDC_DB=/data/tmp/neg.db ndc script draft 2
→ error: Quelle nicht verifizierbar: Kim et al. 2025 (unresolvable); Kim et al. 2025 (Volltext) (unresolvable)
```
`llm_run` in der Scratch-DB blieb bei 13 Zeilen = identisch zur Live-DB vor dem Draft → der Block greift **vor** dem LLM-Aufruf.

## Kriterium 3 — Adversarialer Verifier, Risiko-Review, hash-gebundene Freigabe

Verdikte Version 9 (23 Sätze, 23 Verdikte; Sonnet 5.5, llm_run 13):

| Verdikt | Art | n | Sätze |
|---|---|---|---|
| supports | empirical | 6 | 7, 8, 11, 12, 13, 14 |
| partial | empirical | 1 | 15 (Achtsamkeit: „den Alltag" ≠ „overall functioning") |
| unsupported (forced `hidden_claim`) | framing | 2 | 16 („Aber: mit Vorsicht zu lesen" — Modell-Verdikt *supports*, Regel erzwingt unsupported), 18 (unzitierte Meta-Aussage über die Studienlage) |
| unsupported (`uncited`) | advice | 1 | 20 — **erfundener Tipp** („Mach nur den allerersten Handgriff"), vom Editor-Pass aus dem Draft übernommen |
| not_applicable | framing | 13 | Hook, Überleitungen, CTA |

Gate: ✗ 3 Blocker. Over-flag-Prüfung (must_have): 8 zitierte Sätze, 2 vom Operator als „eigentlich ok" einschätzbar (15, 16) = 25 % < 30 % → **Rubrik nicht getunt** (verify_de.md prompt_sha `564da54cd841…` unverändert). Beobachtung für später: `hidden_claim` erzwingt UNGESTÜTZT auch wenn der Prüfer die Quelle als deckend beurteilt (Satz 16) — Kandidat für eine Regelverfeinerung, kein Fehler des Runs.

**Edit 1** (`ndc script export 5e437e1b` → Datei → `ndc script import`): Satz 15 auf Quellenbegriffe, Satz 16 explizit („Die Forschenden selbst sagen …" ⟦11:64⟧), neuer zitierter Was-hilft-Satz aus Cochrane ⟦8:20⟧, Satz 18 als zitierte Zusammenfassung ⟦7:3⟧, erfundener Tipp gestrichen.
→ Version 10 `abbbf630…`, 209 Wörter, „4 neu geprüft · 18 übernommen"; Gate: 1 Blocker = **Begriffswarnung ohne Override** (`de.krankheit`: „Symptome"), ⚠ Wortbudget 140–190, Satz 19 TEILWEISE (eigene Deutung „nicht ein einzelner Schalter").

**Edit 2**: „Symptome" → „Kernmerkmale von ADHS", Satz 19 nach Prüfer-Vorschlag gekürzt, zwei Füllsätze gestrichen (190 Wörter).
→ Version 11 `4299e91ab4f0654378c7b2550e8608ba77c8316235b615b97a95068511eb90b0`, „5 neu geprüft · 15 übernommen"; Gate: **0 Blocker, 1 Bestätigung offen** (Satz 17 TEILWEISE: „Nicht eine Stelle, sondern mehrere zugleich" — Prüfer: Gruppenvergleich von Testleistungen, nicht „Stellen"/„zugleich").

Verdikte Version 11 (20 Sätze): supports 9 (7 empirical, 2 advice), partial 1, framing 10; 15 von 20 Verdikten aus der Vorversion übernommen (byte-identischer Satz + identische Evidenz).

**Phone-Review (Task 2):** Operator öffnet http://10.0.0.213:8090 (Pi-Tunnel → 127.0.0.1:8090), ackt/ändert Satz 17, entscheidet.
Review-Zeit: *(ausstehend)*
Entscheidung: *(ausstehend)*

## Kriterium 4 — Quellenliste nur aus DB-Zeilen

`ndc script sources <sha> --variant caption|comment` rendert ausschließlich `source`-Zeilen der zitierten Snapshots einer **freigegebenen** Version (Jinja-Template `config/source_list.yaml`, kein LLM). Ausgabe wird nach der Freigabe hier eingefügt:

*(ausstehend — nach Approval)*

## Kriterium 5 — Modelle/Prompts aus Config, jeder Call im Log

`config/llm.yaml`: draft + editor `claude-opus-5-5` (effort high, max_tokens 8000), verify `claude-sonnet-5-5`; Prompts `config/prompts/{draft,editor,verify}_de.md` + `style_guide.md` + `engagement_playbook.md` (verbatim angehängt, gemeinsam gehasht). Sonnet-5.5-Preise heute eingetragen (2.0 / 10.0 / 0.20 / 2.5 USD per MTok) → `cost_usd` ab llm_run 13 befüllt.

| llm_run | stage | model | prompt_sha256 | in | out | cache_write | thinking | cost_usd | subject |
|---|---|---|---|---|---|---|---|---|---|
| 11 | draft | claude-opus-5-5 | 42fa3dae2435… | 130 | 5870 | 21483 | 5085 | 0.2253 | topic 2 |
| 12 | editor | claude-opus-5-5 | 1eb3afd7aefb… | 7214 | 4799 | 0 | 3905 | 0.1248 | version 8 |
| 13 | verify | claude-sonnet-5-5 | 564da54cd841… | 6341 | 5391 | 0 | 2772 | 0.0666 | version 9 |
| 14 | verify (import) | claude-sonnet-5-5 | 564da54cd841… | 3623 | 800 | 0 | 0 | 0.0152 | version 10 |
| 15 | verify (import) | claude-sonnet-5-5 | 564da54cd841… | 3960 | 2398 | 0 | 1440 | 0.0319 | version 11 |

Request-/Response-Artefakte existieren für alle fünf Runs (`request_artifact_path`/`response_artifact_path` unter `/data/artifacts`), `request_id` erfasst (z. B. `req_011CgRK5jUmSywcbReqvoARz`).

**Gesamtkosten des Live-Runs: 0.464 USD** (Draft 49 %, Editor 27 %, 3 × Verify 25 %). Der Draft ist zu 87 % Thinking (5085 von 5870 Output-Tokens) → `draft.effort: medium` bleibt die Stellschraube, wenn die Qualität hält.

## Offene Punkte aus dem Run
- Facette `custom` bei `--query`-Suchen umgeht die help-Lock-Warnung.
- Draft/Editor erzeugten einen unzitierten Tipp trotz Prompt-Verbot; der Verifier hat ihn gefangen (Gate funktioniert), aber Prompt-Schärfung („kein Tipp ohne Marker") spart einen Edit-Zyklus.
- `hidden_claim`-Regel überstimmt ein *supports*-Modellverdikt (Satz 16 v9).
