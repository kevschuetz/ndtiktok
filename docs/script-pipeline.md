# Script-Pipeline — Operator-Runbook (Phase 2)

Ein Thema rein, ein zitiertes, gegengeprüftes und freigegebenes Skript plus Quellenliste raus. Alles läuft als
`docker compose run --rm ndc <cmd>` auf dem Host; die Phone-Review-UI ist der einzige Dauerdienst (`ndc-review`).
Jeder LLM-Aufruf landet in `llm_run` (Modell, Prompt-Hash, Tokens, Kosten, Artefakte). Modelle und Prompts stehen
nur in `config/llm.yaml` und `config/prompts/`.

## 1. Befehlsfolge (ein Skript, ~15 min inkl. Review)

```bash
ndc topic list                                   # whitelist + safety ok + source_likely yes wählen
ndc source search <topic>                        # PubMed-Shortlist (Leitlinien/SR/MA zuerst; ⚠ = Safety-/Titelflag)
ndc source search <topic> --query '<MeSH AND …>' # optional: Topic-Teil der Query ersetzen (z. B. adult*[tiab] erzwingen)
ndc source pick <topic> <rang> [<rang> …]         # 2–5 Quellen; speichert Abstract (+ OA-Volltext) als Snapshot
ndc source pick-snapshot <topic> <snapshot_id>    # z. B. AWMF-Leitlinie aus `ndc source import-awmf` hinzunehmen
ndc source check-ids --topic <topic>             # PMID/DOI gegen PubMed/Crossref (läuft nach pick auch automatisch)
ndc corpus lock <topic>                          # friert die Quellen ein; warnt, wenn keine „Was hilft“-Quelle dabei ist
ndc script draft <topic> --punch                 # Draft (Opus) → TikTok-Editor (Opus) → Verify (Sonnet); 2–3 min
ndc review show <sha>                            # Gate-Banner, Warnungen, Claims nach Risiko sortiert
```

Dann Phone-Review (Abschnitt 3). Nach der Freigabe:

```bash
ndc script sources <sha> --variant caption       # Quellenliste für die Caption (nur DB-Zeilen, kein LLM)
ndc script sources <sha> --variant comment       # Langfassung für den angepinnten Kommentar
```

Hilfreich daneben: `ndc corpus show <topic>`, `ndc source list --topic <topic>`, `ndc source show <snapshot> --sample 10`,
`ndc script show <sha>`, `ndc review status`, `ndc doctor` (DB-Pfad, Migrationen, Key vorhanden ja/nein).

## 2. Verdikte, Blocker, Bestätigungen

| Anzeige | Bedeutung | Was tun |
|---|---|---|
| GESTÜTZT | Quelle deckt den Satz | nichts |
| TEILWEISE / ÜBERTRIEBEN / Sicherheits-Eskalation | Satz geht über die Quelle hinaus oder lässt Hedges weg | pro Satz bestätigen (`ndc review ack <sha> <satz>` oder in der UI) **oder** umformulieren (Abschnitt 4) |
| UNGESTÜTZT / WIDERSPRICHT | kein Beleg bzw. Gegenteil | **Blocker** — umformulieren oder streichen; ein Tipp ohne Marker ist immer UNGESTÜTZT |
| UNGESTÜTZT (versteckte Aussage) | Rahmen-Satz enthält eine Sachaussage über die Studienlage ohne Zitat | Aussage zitieren oder in echten Rahmen umschreiben („Vielleicht kennst du das.“) |
| RAHMEN | Hook, Überleitung, CTA ohne Sachaussage | nichts |
| Begriffswarnung ohne Override | `config/terminology.yaml` (z. B. „Symptome“, „Störung“) | Wort ersetzen (Vorschlag steht in der Warnung) oder `ndc check … --override` |
| ⚠ Wörter (Ziel 140–190) | Wortbudget aus `style_guide.md` | kürzen; nur Warnung |
| ⚠ AWMF-Leitlinie … abgelaufen seit | Leitlinie nicht mehr gültig (D-13a, zurückgenommen: warnt nur) | Aussagen bewusst prüfen |
| Bewertungen aus Vorversion übernommen: n | byte-identische Sätze mit identischer Evidenz behalten ihr Verdikt | nichts |

Freigabe ist an den exakten Hash gebunden: jede Textänderung erzeugt eine neue Version, alte Freigaben verfallen.

## 3. Phone-Review

Der Container `ndc-review` lauscht nur auf `127.0.0.1:8090` und kennt keine Secrets (kein `.env`, read-only, keine Capabilities).
Vom Telefon aus über den eigenen Tunnel/Pi erreichen (Host-Header muss in `NDC_REVIEW_ALLOWED_HOSTS` stehen, sonst 400).
Dort: Claims nach Risiko lesen → ⚠-Sätze bestätigen → **Freigeben**, **Ablehnen** oder **Änderungen** mit Notiz.
Ziel ≤ 10 min pro Skript. CLI-Äquivalent: `ndc review ack <sha> <satz> [--note]`, `ndc review decide <sha> approved|rejected|changes_requested --note "…"`.

## 4. Einen Blocker beheben (Export → Edit → Import)

```bash
ndc script export <sha>                 # schreibt /data/edits/<sha10>.txt: ein Satz pro Zeile, Marker ⟦snapshot:satz⟧ am Ende
# Datei bearbeiten (Host-Pfad /home/nd-content-volumes/data/edits/). Marker nur aus dem Korpus; Satznummern mit
#   ndc source show <snapshot> nachsehen. Zeilen löschen/ergänzen ist erlaubt, reine Marker-Änderung ohne Textänderung nicht.
ndc script import /data/edits/<sha10>.txt   # neue Version; nur geänderte Sätze werden neu geprüft (≈ 0.02–0.03 USD)
ndc review show <neue-sha>
```
Alternativ `ndc script punch <sha>` (neuer Editor-Durchlauf, voll re-verifiziert) oder ein neuer `ndc script draft` auf demselben Korpus.

## 5. Kosten lesen

`cost_usd` in `llm_run` kommt aus den Preisen in `config/llm.yaml` (`prices:`). Fehlt ein Preis → `cost_usd` NULL und eine WARNING.
Richtwerte (Live-Run 2026-10-26, Thema 2): Draft 0.13–0.23 USD (≈ 85 % Thinking bei `effort: high`), Editor 0.10–0.12,
Verify 0.03–0.07, Import-Re-Verify 0.02–0.03. Ein Skript inkl. zwei Edits ≈ 0.45 USD.
Abfrage: `select id, stage, model, input_tokens, output_tokens, thinking_tokens, cost_usd from llm_run order by id desc limit 10;`
(z. B. `docker compose run --rm --entrypoint uv ndc run --no-sync python -c "import sqlite3; …"`; `sqlite3` ist auf dem Host nicht installiert).

## 6. Fehlerbehebung

| Symptom | Ursache | Behebung |
|---|---|---|
| `error: Quelle nicht verifizierbar: … (unresolvable|mismatch|error)` beim Draft/Approve | PMID/DOI nicht auflösbar, Titel/Jahr passt nicht, oder PubMed/Crossref nicht erreichbar (fail-closed) | `ndc source check-ids --topic <t> --force`; bei echtem Fehlidentifikator Quelle verwerfen und neu picken; bei Netzfehler später erneut |
| Europe PMC `503` / `FullTextError` beim Pick | transiente Störung der Europe-PMC-REST-API | Pick wiederholen (tenacity-Retries laufen bereits); ohne Volltext bleibt der Abstract-Snapshot nutzbar |
| `LlmTruncated` | `max_tokens` erreicht (Thinking zählt mit) | `draft.max_tokens` / `editor.max_tokens` in `config/llm.yaml` erhöhen (8000 reicht normalerweise) |
| `LlmRefused` | Modell hat die Anfrage abgelehnt (`stop_reason: refusal`) | Thema/Prompt prüfen; erneut versuchen; ggf. anderes Thema |
| `CitationMismatch` | Draft zitiert Text, der nicht im Korpus liegt (sollte nicht vorkommen) | **Bug — melden**, Artefakt unter `/data/artifacts` beilegen; nicht manuell „reparieren“ |
| `PunchError: neuer Marker …` | Editor hat einen Marker erfunden | Editor-Pass wiederholen; der Draft bleibt als Version erhalten |
| Gate „abgelaufen seit <Datum>“ | AWMF-Leitlinie ist veraltet | nur Warnung (operator-Entscheid); Aussagen bewusst prüfen |
| `cost_usd` NULL, WARNING „no complete price“ | Preis in `config/llm.yaml` fehlt | `prices:` ergänzen (USD per MTok) |
| `error: keine Änderung am Text` beim Import | nur Marker geändert | Text mitändern oder Version so lassen |
| `Begriffswarnung ohne Override` | Terminologie-Treffer | Wort ersetzen oder bewusst `ndc check … --override` |
| `ANTHROPIC_API_KEY missing` | `.env` fehlt oder nicht geladen | `/home/nd-content/.env` (chmod 600) prüfen; `ndc doctor` zeigt „present/missing“ |
| Phone-UI antwortet 400 | Host-Header nicht in `NDC_REVIEW_ALLOWED_HOSTS` | Adresse in `docker-compose.yml` ergänzen, `docker compose up -d ndc-review` |
| Phone-UI OOM / Neustart | 256 MB Limit; schwere Imports im Web-Prozess | `pymupdf` bleibt lazy; keine neuen Top-Level-Imports in `review/web.py` |
| Quiet-hours-Abbruch | Befehle 00:15–06:00 UTC | außerhalb laufen lassen (Host teilt sich Ressourcen mit polymarkt-watch) |

## 7. AWMF-Leitlinie einbinden (manuell)

PDF im Browser von register.awmf.org laden (Bot-Check — niemals skripten), nach `/home/nd-content-volumes/data/awmf/` kopieren, dann:
```bash
ndc source import-awmf /data/awmf/<datei>.pdf --register 028-045 --version "<Text von der AWMF-Seite>" \
  --valid-until YYYY-MM-DD --status abgelaufen|in_ueberarbeitung|gueltig --title "ADHS bei Kindern, Jugendlichen und Erwachsenen" [--topic <t>]
ndc source show <snapshot_id> --sample 10
```

## 8. Aufnahme → Diff → Freigabe (SCR-05, Phase 3)

Geprüft wird das, was wirklich gesagt wurde — nicht der Entwurf.

```bash
# Aufnahme (Audio oder Video vom Handy) auf den Host kopieren:
#   /home/nd-content-volumes/data/recordings/<datei>
docker compose run --rm ndc-heavy recording add /data/recordings/<datei> --script <skript-sha>   # 1. Lauf lädt large-v3 (~3 GB) nach /data/models
ndc recording show <aufnahme-sha|id>     # Satz für Satz: stimmt / Abweichung / nicht im Skript / nicht gesprochen, Ähnlichkeit, Prüfer-Verdikt
ndc recording ack <sha> <satz>           # TEILWEISE / ÜBERZOGEN bestätigen (oder auf dem Handy)
ndc recording decide <sha> approved|changes_requested|rejected --note "…"
```

- **Ohne Abweichung** wird die Aufnahme automatisch freigegeben (Zeile `reviewer=system`), der Diff bleibt gespeichert.
- **Abweichung** = anderer Wortlaut einer Aussage, ein weggelassener Hedge („häufiger“, „könnte“, „manche“ … aus `config/recording.yaml hedge_tokens`) oder ein Satz, der nicht im Skript steht. Solche Sätze gehen durch denselben Prüfer wie das Skript, gegen die zitierten Quellensätze des passenden Skriptsatzes. Ein neuer Satz mit Aussage ist immer UNGESTÜTZT → neu aufnehmen oder streichen (Schnitt).
- **Schwelle** `similarity_threshold: 0.80` (Token-Ähnlichkeit). Fällt ein eindeutig gleicher Satz darunter (Aussprache/ASR), Schwelle einmal senken und im Summary festhalten; fällt ein geänderter Satz als „stimmt“ durch, erhöhen.
- Die Freigabe hängt am **Transkript-Hash**; eine neue Aufnahme ist immer ein neuer Hash. `ndc publish log` verweigert ohne freigegebene Aufnahme (`--recording <sha>`).
- Läuft nicht 00:15–06:00 UTC (`--force` überschreibt).

## 9. Untertitel (SRT)

```bash
ndc recording srt <sha> -o /data/recordings/<name>.srt
```
Cue-Text = finales Transkript (Skript-Wortlaut bei „stimmt“, gesprochener Wortlaut bei freigegebenen Abweichungen), Zeiten aus den Whisper-Wortzeiten, ≤ 2 Zeilen à 42 Zeichen. Datei in CapCut/TikTok importieren; Styling in der App.

## 10. Veröffentlichen

```bash
ndc publish caption <skript-sha>         # Caption (Quellenliste + 3–5 Hashtags) und angepinnter Kommentar (+ Krisen-Kurzform bei sensiblen Themen)
# posten: TikTok zuerst, dann Original-Render (nie der TikTok-Download) auf YouTube Shorts und Instagram Reels
ndc publish log --platform tiktok --script <sha> --recording <aufnahme-sha> --post-url <url> [--posted-at ISO] [--hook <taktik>]
ndc publish log --platform youtube  --script <sha> --recording <aufnahme-sha> --post-url <url>
ndc publish log --platform instagram --script <sha> --recording <aufnahme-sha> --post-url <url>
ndc publish list
```
Verweigert: Skript nicht freigegeben, Aufnahme nicht freigegeben oder zu einer anderen Skriptversion, Readout-Regel nicht gesperrt, fremder URL-Host, Cross-Post vor dem TikTok-Eintrag.

## 11. Kennzahlen (24 h · 72 h · 7 d)

```bash
ndc metrics due                          # was gerade fällig ist (Fenster: 20–30 h, 66–84 h, 156–192 h)
ndc metrics add <publication-id> --age 24h --views N --likes N --comments N --shares N --saves N --follows N \
  --avg-watch-s F --watched-full-pct F --fyf yes|no|unknown --fyf-reason "…"
ndc metrics import /data/exports/<tiktok-studio>.csv [--age 72h]   # Desktop: TikTok Studio → Analytics → Daten exportieren
ndc metrics show <publication-id>
```
- TikTok vollständig; YouTube/Instagram nur Views bei 7 d. Zeilen sind append-only (Korrektur = neue Zeile).
- CSV-Spalten werden über `config/metrics.yaml csv_columns` erkannt; unbekannte Spalten landen in `raw_json`. Beim ersten echten Export die Kopfzeilen prüfen und ergänzen.
- **For-You-Feed-Status**: in der App Video → „Mehr Insights“ → Übersicht; Hinweis „für einige Zielgruppen nicht verfügbar“/„nicht für den Für-dich-Feed geeignet“ wörtlich in `--fyf-reason`.
- Erinnerung: Cron schreibt alle 30 min `/data/due.json` (`docs/ops-cron.md`); die Handy-UI zeigt es unter `/due`.

## 12. Readout-Regel (vorregistriert)

`config/readout_rule.yaml` ist mit `ndc readout lock` gesperrt (Datei `.lock` + DB-Zeile mit committed_at). `ndc readout show` zeigt den Zustand; eine Änderung braucht `ndc readout amend --reason "…"` (im Container mit `--lock-out /data`, Datei dann in `config/` kopieren). Ohne Sperre lässt sich nichts veröffentlichen.

## 13. Fehlerbehebung (Aufnahme, Veröffentlichung, Kennzahlen)

| Symptom | Ursache | Behebung |
|---|---|---|
| `recording add` sehr langsam beim ersten Mal | large-v3-Gewichte werden geladen | warten; Modell liegt danach in `/data/models` |
| `quiet hours` (Exit 4) | 00:15–06:00 UTC | später oder `--force` |
| `Aufnahme muss unter /data/recordings liegen` | Datei außerhalb des erlaubten Ordners | nach `/home/nd-content-volumes/data/recordings/` kopieren |
| fast alle Sätze „Abweichung“ mit niedriger Ähnlichkeit | falsche Sprache/Modell oder falsches Skript | `config/recording.yaml language/whisper_model` prüfen; richtige `--script` sha |
| `identische Aufnahme (Transkript) existiert bereits` | gleicher finaler Text schon gespeichert | bestehende Aufnahme verwenden (`ndc recording list`) |
| `Satz n: Abweichung nicht geprüft` | `--no-verify` benutzt | `ndc recording add` ohne `--no-verify` wiederholen (neue Datei) oder Verifikation nachholen |
| `PublishRefused: Aufnahme fehlt / nicht freigegeben` | kein `--recording` oder Aufnahme nicht approved | Aufnahme freigeben (Handy oder CLI), Sha mitgeben |
| `Readout-Regel ist nicht gesperrt` / `geändert` | Lock fehlt oder Datei geändert | `ndc readout show`; `amend --reason` oder Datei zurücksetzen |
| `CSV: keine Spalte für post_url/post_id erkannt` | Export-Kopfzeilen unbekannt | Kopfzeilen in `config/metrics.yaml csv_columns` eintragen |
| `/due` zeigt nichts, obwohl fällig | Cron läuft nicht / Datei fehlt | `crontab -l`, `cat /home/nd-content-volumes/data/due.json`, `ndc metrics due --write /data/due.json` |
