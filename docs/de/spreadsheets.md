# Mit einer Tabelle starten (Selbstständige & kleine Teams)

🇬🇧 [English](../spreadsheets.md) · 🇩🇪 Deutsch

In einer Firma mit ein bis fünf Personen geht es bei agentic-pm nicht ums Koordinieren eines Teams. Es nimmt Dir Dinge aus dem Kopf:

- **Versteckte Ketten.** In einer Tabelle mit 100 Zeilen übersieht man leicht, dass der Kunden-Launch am Freitag an einem Druckproof in Zeile 63 hängt, den noch niemand freigegeben hat. Die Abhängigkeitsanalyse findet diese Kette und schreibt sie in Deine Morgen-Mail.
- **Kein Zellen-Bearbeiten am Handy.** Die Tabelle bleibt Dein Kassenbuch. Später (Phase 3) kannst Du sie per Sprache oder WhatsApp aktualisieren, statt in Excel auf dem Handy herumzuzoomen.
- **Nichts einzurichten.** Eine lokale `.xlsx` oder `.csv` plus ein lokales Modell (Ollama) heißt: keine Cloud-Konten, keine Abos, und Deine Daten bleiben auf Deinem Rechner.

## In zwei Minuten ausprobieren

```bash
uv sync
uv run agent-pm deps  --config examples/solo/team.yaml --date 2026-11-16
uv run agent-pm brief --config examples/solo/team.yaml --person me --date 2026-11-16
```

Die [Beispieltabelle](../../examples/solo/tasks.csv) ist ein kleines Designstudio: Logo, dann Druckdaten, dann der Proof der Druckerei, dann die Flyer, dann der Launch beim Kunden. Sie enthält absichtlich auch ein Datum „TBD“, damit Du siehst, wie Probleme gemeldet werden.

## Deine eigene Tabelle verwenden

```yaml
project:
  tracker: spreadsheet
  repo: studio                       # ein Name für diese Tabelle
  leads: [me]                        # allein: das bist Du
  tracker_options:
    path: data/kundenprojekte.xlsx   # .xlsx oder .csv, relativ zu dem Ort, an dem Du agent-pm startest
    sheet: Aufgaben                  # nur .xlsx (Standard: erstes Blatt)
    header_row: 1                    # steht über der Kopfzeile ein Titel, nimm 2
    columns:                         # Deine Spaltennamen; andere Spalten bleiben unberührt
      id: ID                         # Pflicht, ein stabiler Schlüssel wie T-101
      title: Aufgabe                 # Pflicht
      status: Stand                  # Pflicht
      due: Fällig                    # optional: Datumszelle, 2026-11-20 oder 20.11.2026
      owner: Wer                     # optional: „Sam“ oder „Sam, Kim“
      depends_on: Abhängig von       # optional: „T-12, T-15“ oder „github:acme/api#42“
      estimate: Schätzung            # optional: 4h / 2d / 1w oder eine Zahl
    status_map:                      # zusätzliche Schreibweisen; ergänzen die eingebauten (Deutsch und Englisch)
      blocked: ["wartet auf kunde"]
    estimate_unit: days              # was eine bloße Zahl bei der Schätzung bedeutet (hours oder days)
```

Eingebaute Status sind zum Beispiel *offen / todo*, *in Arbeit / in progress*, *review*, *wartet / blockiert / waiting*, *erledigt / fertig / done* und *abgebrochen / cancelled*.

Um Verantwortliche Personen zuzuordnen, vergleicht der Agent die Zelle „Wer“ mit `tracker_login` (oder dem Handle) in `team.yaml`, ohne auf Groß- und Kleinschreibung zu achten. Steht in Deiner Tabelle „Mia Huber“, setze `tracker_login: Mia Huber`.

## Er scheitert nie still

Tabellen sind lockerer als Issue-Tracker. Deshalb wird jede Zeile, die der Agent nicht verwenden kann, **mit genauer Position gemeldet**, nie stillschweigend weggelassen oder erraten. Dein Briefing sagt es dann, in Deiner Sprache:

```
🧾 Nicht alles lesbar: studio (tasks.csv)
  • tasks.csv:Zeile 11: 'P-10' hat als Fälligkeit 'TBD', das ist kein Datum; ohne Termin geprüft
```

| Situation | Was passiert |
|-----------|--------------|
| Zeile hat Inhalt, aber keine ID, oder verwendet eine ID doppelt | Übersprungen und gemeldet. Zeilennummern werden nie als ID verwendet, weil sie sich beim Sortieren oder Einfügen verschieben. |
| Unbekannter Status (z. B. „vielleicht später“) | Übersprungen und gemeldet. Falsches Raten könnte ein Risiko verstecken oder erfinden; trag das Wort in `status_map` ein. |
| Fälligkeit oder Schätzung nicht lesbar („TBD“) | Aufgabe bleibt, Wert wird gemeldet |
| `Abhängig von` nennt eine fehlende ID | Gemeldet (die Kette ist dort unterbrochen) |
| `Abhängig von` nennt einen anderen Tracker (`github:acme/api#42`) | Als „noch nicht prüfbar“ gemeldet, bis es Abhängigkeiten über Tracker hinweg gibt (#59) |
| Formel ohne berechneten Wert (von einem Skript gespeichert) | Gemeldet; öffne und speichere die Datei in Excel oder LibreOffice |
| Eine eingestellte optionale Spalte fehlt in der Tabelle | Einmal gemeldet; setze sie auf `null`, wenn Du sie nicht führst |
| Leere Zeilen am Ende (auch formatierte) | Werden still ignoriert |
| Datei fehlt, falsches Blatt, Pflichtspalte fehlt | Als Fehler gemeldet; `agent-pm deps` endet mit Code 1 |

Technische Details:
- `.xlsx`-Dateien werden nur lesend geöffnet, mit den gespeicherten Formelergebnissen (`=ARBEITSTAG(…)` funktioniert).
- CSV wird als UTF-8 mit der Byte-Order-Mark gelesen, die Excel einfügt.
- Die Datei wird neu gelesen, sobald sie sich auf der Festplatte ändert.

## Grenzen (vorerst)

- **Nur lesend.** Der Agent schreibt nie in Deine Datei. Das Aktualisieren per Sprache oder WhatsApp gehört zu Phase 3.
- **Keine Änderungsereignisse.** Die Tabelle wird bei jedem Briefing, Wochenrückblick oder `deps`-Lauf gelesen.
- **Eine Tabelle pro Projekt.** Abhängigkeiten zu GitHub- oder OpenProject-Einträgen werden gemeldet, aber noch nicht geprüft (#59).
