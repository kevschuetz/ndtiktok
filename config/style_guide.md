# Style Guide — nd-content short-form videos (CONT-02)

Version 1 · 2026-10-24 · Deutsch primär, englische Entsprechungen in Klammern (die Sprachentscheidung
fällt in Validierungswoche 1). Phase-2-Prompts lesen diese Datei unverändert ein.

Positionierung: „Ich bin kein Therapeut – ich lese die Forschung und übersetze sie."
(*"I'm not a therapist — I read the research and translate it."*)
Ton: neurodiversitäts-affirmierend, vorsichtig formuliert (hedged), nie diagnostisch.

## 1. Fixes Template: 60–75 s (fixed template)

Jedes Video folgt denselben Beats. Ein Thema pro Video (*one topic per video*) — keine Listen mit
mehreren Themen, keine „Teil 1 von 5"-Serien innerhalb eines Videos.

| Zeit | Beat | Inhalt |
|---|---|---|
| 0–2 s | **Hook** | Gesprochen = Text auf dem Bildschirm (identisch). Enthält das Such-Keyword (z. B. „ADHS und Zeitgefühl"). Keine Frage, die zur Selbstdiagnose einlädt. |
| 2–10 s | Erleben | Was manche Menschen erleben, vorsichtig formuliert: „Manche Menschen mit ADHS erleben …" |
| 10–45 s | Erklärung | Kurze wissenschaftliche Erklärung mit 1–2 belegten Aussagen. Jede belegte Aussage bekommt eine Quellenkarte (1–2 s). |
| 45–65 s | Was hilft | Umfeld, Strategien, kleine Anpassungen — keine Behandlungsempfehlung. |
| 65–75 s | Abschluss | Stärke mit Einschränkung („kann auch eine Stärke sein – nicht für alle") oder ein Takeaway in einem Satz + „Quellen im angepinnten Kommentar." |

**Wortbudget (word budget):** ca. 140–190 gesprochene Wörter bei ruhigen ~140–150 Wörtern pro Minute.
→ *Kalibrieren an den ersten Aufnahmen (calibrate on first recordings; Annahme A7).*

## 2. Hedging (vorsichtige Formulierung)

Jede Aussage über Menschen ist eine Aussage über *manche* Menschen, nie über „dich".

**Phrasenbank DE:**
- „Manche Menschen mit ADHS …" / „Viele autistische Menschen berichten …"
- „Studien deuten darauf hin, dass …" / „Im Schnitt …"
- „kann", „häufig", „bei einem Teil der Betroffenen"
- „Das heißt nicht, dass es allen so geht."

**Phrase bank EN:**
- "Some people with ADHD …" / "Many autistic people describe …"
- "Research suggests that …" / "On average …"
- "can", "often", "for some people"
- "That doesn't mean it's the same for everyone."

**Verbotene Rahmungen (forbidden frames):**
- „Du hast ADHS, wenn …" (*"You have ADHD if …"*)
- Listen von Anzeichen, Checklisten, Selbsttests (*lists of signs, checklists, self-tests*)
- „Ärzte sagen dir nicht …" / „Was dir keiner sagt" (*"doctors won't tell you …"*)
- Heilungs- oder Behandlungsversprechen, Medikamente, Nahrungsergänzung (*cure claims, medication, supplements*)

## 3. Disclaimer

- Caption/Bio: **„Kein Ersatz für ärztliche oder psychotherapeutische Beratung."**
  (*"Not a substitute for medical or psychotherapeutic advice."*)
- Positionierung (gesprochen, wenn passend): „Ich bin kein Therapeut – ich lese die Forschung und
  übersetze sie."

## 4. Visuelle Regeln (visual rules)

- Ruhige Farbpalette, keine Stroboskop-Effekte (*calm palette, no strobe*).
- **Höchstens 3 Blitze (flashes) in jeder 1-Sekunden-Periode** (WCAG 2.3.1, allgemeine Blitzschwelle).
- Keine Schnellschnitt-Montagen; mindestens ~1,5 s pro Einstellung (*minimum ~1.5 s per shot*).
- Kontrastreiche Untertitel.
- Nichts Textkritisches in den unteren ~20 % des Bildes (Plattform-UI überdeckt diesen Bereich).

## 5. Untertitel (Captions)

- Eingebrannt (*burned in*) und **wörtlich** zum gesprochenen Skript — Genauigkeit vor Styling.
- Maximal 2 Zeilen, ca. 32–42 Zeichen pro Zeile.
- Fachbegriffe exakt wie im Skript schreiben (Whisper-Rechtschreibung gegen das Skript korrigieren).

## 6. Quellen (Sources)

**Quellenkarte im Video (on-screen card, 1–2 s):** „Studie: Autor et al. Jahr, Journal" bzw.
„Leitlinie: AWMF 028-045, Jahr".

**Angepinnter Kommentar (pinned comment):** Quellen im angepinnten Kommentar und/oder in der Caption:
- Studie: Autor et al. (Jahr). Kurztitel. *Journal*. DOI oder PMID.
- Leitlinie: Titel, AWMF-Registernummer, Version/Jahr.
- Die Liste wird in Phase 2 ausschließlich aus der Datenbank gerendert — nie aus dem Gedächtnis eines
  LLM (*rendered from the DB only*).

## 7. Sprache und Begriffe (terminology)

**Jedes Skript muss `ndc check` bestehen** (*every script must pass `ndc check`*):
`ndc check skript.txt --lang de --level script`. Block-Befunde sind nie überschreibbar; Warn-Befunde
nur mit begründetem Override, gebunden an den exakten Text.

- **Identity-first (D-13):** Standard ist „autistische Menschen" (identity-first und geschlechtsneutral).
  „Autist:innen" nur, wenn ein Substantiv unvermeidbar ist. Englisch: "autistic people".
  „Person im Autismus-Spektrum" ist als neutrale Form erlaubt. Nicht: „Menschen mit Autismus",
  „Autisten".
- **Gendern (D-14):** neutrale Konstruktionen, wo möglich — „Menschen mit ADHS", „Eltern",
  „Fachleute", „Lehrkräfte". Keine Genderdoppelpunkte im gesprochenen Text, außer „Autist:innen" (D-13).
- **Nie:** Funktionslabels (hoch-/niedrigfunktional, leichter/schwerer Autismus), ABA-nahe Rahmung
  („Stimming abgewöhnen", „Blickkontakt erzwingen", „Autismus heilen").
- **Vermeiden (Warnung):** „leidet an/unter", „Superkraft", „Asperger" außerhalb von Zitaten,
  Krankheits- und Defizitsprache, „gesunde/normale Menschen" als Vergleichsgruppe, „Behandlung/Therapie"
  außerhalb wörtlicher Leitlinienzitate.

Die vollständige Liste steht in `config/terminology.yaml`, die gesperrten Themen in `config/safety.yaml`.

## 8. Krisenhinweis (crisis line)

Bei Themen rund um Emotionen, Überforderung oder Burnout steht im angepinnten Kommentar ein Hinweis auf
Krisenangebote aus `config/crisis_lines.yaml` (wird in Plan 09 angelegt), z. B. für AT/DE/CH.
Suizid und Selbstverletzung sind selbst kein Videothema (Safety-Filter).
