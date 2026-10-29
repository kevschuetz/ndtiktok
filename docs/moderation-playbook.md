<!-- generated from config/moderation.yaml by `ndc moderation render` — do not edit -->
# Moderations- und Krisen-Playbook (OPS-01)

Version 1 · Sprache de · freigegeben: 2026-10-29

## 1. Grundsatz: nie automatisch antworten

Keine Bots, keine gespeicherten Auto-Nachrichten, keine LLM-Antworten. Jede Antwort wird vom Operator gelesen, ausgewählt und selbst gesendet. Keine Diagnosen, keine Medikamenten- oder Therapieberatung, nirgends.

- Auto-Antwort: **never** · DMs: **restricted** · Filter: keywords, spam_offensive
- Eskalation: in app report for imminent risk · Löschen: harassment scam only

## 2. Antwortvorlagen (manuell senden, ≤ 150 Zeichen)

### crisis_disclosure

**Wann:** Jemand schreibt von Verzweiflung, Selbstverletzung, nicht mehr können, Hoffnungslosigkeit

> Danke, dass du das schreibst. Du musst da nicht allein durch: AT 142 · DE 0800 111 0 111 · CH 143, rund um die Uhr. Im Notfall 144/112.

**Dann:** Kommentar nicht löschen. Bei akuter Gefahr zusätzlich in der App melden (Eskalation).

### diagnosis_request

**Wann:** „Hab ich ADHS?“, „Ist mein Kind autistisch?“, Bitte um Einschätzung

> Das kann ich hier nicht beurteilen – dafür braucht es eine Fachperson. Erste Anlaufstelle: Hausarztpraxis oder Fachstelle, in AT z. B. über 1450.

### medication_request

**Wann:** Fragen zu Wirkstoffen, Dosierung, Absetzen

> Dazu sage ich bewusst nichts – das gehört in die ärztliche Sprechstunde. Hier geht es um Forschung zu Alltag und Erleben.

### source_request

**Wann:** „Quelle?“, „Welche Studie?“

> Gern! Die Quellen stehen im angepinnten Kommentar und in der Beschreibung (Autor, Jahr, DOI/PMID).

### critique

**Wann:** Sachliche Kritik an Inhalt, Begriffen oder Rahmung

> Danke für den Hinweis – ich schau mir das an und korrigiere, wenn nötig öffentlich.

### hostile

**Wann:** Beleidigungen, Ableismus, Trolling

**Dann:** Nicht antworten. Löschen/verbergen, bei Wiederholung blockieren. Keine Diskussion.

### scam

**Wann:** Spam, Fake-Tests, Links, „schreib mir privat“

**Dann:** Löschen, melden, blockieren.

### thank_you

**Wann:** Zuspruch, eigene Erfahrung ohne Krisenzeichen

> Danke dir fürs Teilen. Schön, dass es hilft.

## 3. Krisennummern (aus config/crisis_lines.yaml)

Kurzform für angepinnte Kommentare: „Wenn es dir gerade nicht gut geht: AT 142 · DE 0800 111 0 111 · CH 143 (rund um die Uhr, kostenlos). Im Notfall 144 / 112.“

- AT · Telefonseelsorge Österreich: **142** — 0-24 Uhr, täglich (Sofortchat täglich 16-23 Uhr, Mail-Antwort in 48 h)
- AT · Rat auf Draht: **147** — rund um die Uhr (Chat Mo/Di/Fr 18-19, Mi/Do 18-20 Uhr)
- AT · Ö3 Kummernummer (Rotes Kreuz): **116 123** — täglich 16-24 Uhr (NICHT rund um die Uhr)
- AT · Männerinfo - Krisenhelpline für Männer (Männerberatung): **0800 400 777** — 24/7 (Chat 16-22 Uhr)
- AT · Notruf Rettung: **144** — 24/7
- DE · TelefonSeelsorge Deutschland: **0800 111 0 111** — rund um die Uhr
- DE · Nummer gegen Kummer - Kinder- und Jugendtelefon: **116 111** — Mo-Sa 14-20 Uhr (Chat Mo-Do 14-20 Uhr)
- DE · Elterntelefon (Nummer gegen Kummer): **0800 111 0 550** — Mo/Mi/Fr 9-17 Uhr, Di/Do 9-19 Uhr
- DE · Notruf (Rettung/Feuerwehr, EU-weit): **112** — 24/7
- CH · Die Dargebotene Hand: **143** — rund um die Uhr, 365 Tage
- CH · Pro Juventute Beratung + Hilfe 147: **147** — Telefon jederzeit (WhatsApp täglich 7.30-22 Uhr)
- CH · Sanitätsnotruf: **144** — 24/7

## 4. Keyword-Filter (in jeder App eintragen)

- scam: Link in Bio, Teste dich, Test hier, DM für, schreib mir privat, WhatsApp, Telegram-Gruppe, gratis Beratung
- diagnosis_bait: Diagnose per Nachricht, Online-Diagnose, Selbsttest
- medication: Ritalin, Medikinet, Elvanse, Concerta, Methylphenidat, Dosierung
- slurs_note: Plattform-Standardliste 'beleidigende Begriffe' aktivieren; eigene Slur-Liste nur im App-Filter, nie im Repo.

## 5. Spike-Protokoll

Auslöser: ein Video überschreitet **10×** den Median der letzten 10 Posts. Dann 2× täglich Kommentare durchsehen, 72 h lang. Wenn das nicht reicht: **restrict comments**.

- Kommentare 2x täglich lesen, zuerst nach Krisenzeichen
- Krisenkommentare: Vorlage crisis_disclosure, nicht löschen, bei Gefahr melden
- Spam/Scam sofort löschen
- Bei Überlastung: Kommentare auf Follower einschränken, Hinweis im angepinnten Kommentar

## 6. Checkliste vor dem ersten Post

- [ ] Keyword-Filter und Spam-/Beleidigungsfilter auf allen drei Plattformen aktiv
- [ ] DMs eingeschränkt; keine Auto-Antworten/gespeicherten Auto-Nachrichten aktiv
- [ ] Angepinnter Kommentar vorbereitet (Quellen + ggf. Krisen-Kurzform)
- [ ] Vorlagen auf dem Handy griffbereit (Notizen-App)
- [ ] Bei sensiblen Themen (config/metrics.yaml pinned_crisis_domains): Quellen + Krisen-Kurzform anpinnen
