# Datenqualität: Was reinkommt, kommt raus

🇬🇧 [English](../data-quality.md) · 🇩🇪 Deutsch

Die Prüfungen des Agenten sind nur so gut wie die Tickets dahinter:
- Eine Aufgabe **ohne Zuständige** taucht in keinem Briefing auf.
- Eine Aufgabe **ohne Termin** fällt aus der Risiko- und Kollisionsprüfung heraus.
- Eine Aufgabe **ohne Schätzung** zählt als ein Tag.

Deshalb prüft der Agent vor jedem Briefing die offenen Aufgaben und **stellt der richtigen Person eine kurze Frage** pro Lücke. Das läuft im Nur-Lese-Modus, braucht kein Modell und ändert nie von sich aus ein Ticket.

## Was geprüft wird

| Lücke | Was das bedeutet | Wer gefragt wird |
|-------|------------------|------------------|
| Niemand zuständig | Die Aufgabe taucht in keinem Briefing auf | Teamleitungen (oder `completeness.triage`) |
| Zuständige Person nicht in der Team-Datei | Sie bekommt nie ein Briefing | Teamleitungen |
| Kein Termin | Fließt nicht in Risiko- oder Kollisionsprüfung ein | Die zuständige Person |
| Termin nur im Text („Deadline 2026-11-25“) | Wird vorgeschlagen, nie automatisch gesetzt | Die zuständige Person |
| Keine Schätzung (standardmäßig aus) | Zählt als ein Tag | Die zuständige Person |
| Blockiert, aber nichts verknüpft und keine Erklärung | Niemand weiß, worauf sie wartet | Die zuständige Person |
| Blockiert, aber der Blocker ist schon erledigt | Vielleicht kann es weitergehen | Die zuständige Person |
| Text sagt „wartet auf #14“, aber nichts ist verknüpft | Die Abhängigkeitsprüfung sieht es nicht | Die zuständige Person |

Im Briefing sieht das so aus:

```
🧩 Hier fehlen noch ein paar Angaben
  • #P-3 Client picks logo ist als blockiert markiert, aber #P-2 ist schon erledigt.
    Kann es weitergehen, oder wartet es noch auf etwas anderes?
```

Teamleitungen sehen zusätzlich eine **Datenqualität** für das Team, und der Wochenrückblick zeigt sie ebenfalls:

```
📊 Datenqualität
  • 75 % von 8 offenen Aufgaben haben alles, was die Prüfungen brauchen
  • es fehlen: 1 blockiert durch bereits Erledigtes, 1 ohne Termin
```

## Vorsicht bei Freitext

- **Tickettext ist nicht vertrauenswürdig.** Formulierungen wie „wartet auf #14“ oder „Deadline 2026-11-25“ werden immer nur zu einer **Frage** an die zuständige Person. Nichts wird automatisch verknüpft oder geändert. Zitiert wird nur die kurze gefundene Formulierung, nie der restliche Text.
- **Nur echte Aufgaben-Referenzen zählen:** `#14`, `#P-7`, `T-08`, `APP-12`, `studio:T-08` oder `github:acme/api#42`. Daten („nach 2026-11-25“) und Wörter („after review“, „blocked by the client“) werden ignoriert.
- **Ein Datum gilt nur dann als Termin,** wenn es nach einem Wort wie *bis, fällig, Termin, Abgabe, spätestens, due, deadline, by, until* oder *target* steht. „Erstellt 2026-01-01“ zählt nicht.
- **Kein Rauschen:** Verweise auf erledigte oder unbekannte Aufgaben werden übersprungen. Werte, die eine Tabelle nicht lesen konnte („TBD“), werden einmal als [Lesbarkeits-Hinweis](spreadsheets.md#er-scheitert-nie-still) gemeldet, nicht noch einmal als Lücke.

## Menschen, keine Bewertungen

Lücken gehen an die Person, die sie beheben kann. Teamleitungen sehen Aufgaben ohne Zuständige und Zahlen auf Teamebene, **nie „Sam hat 7 unvollständige Tickets“**, denn das wäre eine Bewertung einzelner Personen ([ADR-0004](../adr/0004-people-data-boundaries.de.md)).

## Einstellen

```yaml
completeness:
  require_owner: true
  require_due: true
  require_estimate: false       # einschalten, wenn Dein Team schätzt
  require_blocker_reason: true
  detect_hints: true            # Verknüpfungen für „wartet auf #14“ & Co. vorschlagen
  triage: [alex]                # wer Aufgaben ohne Zuständige bekommt (Standard: die Teamleitungen)
  max_per_brief: 5              # höchstens so viele Fragen pro Person und Tag
```

Prüfungen, die ein Tracker nicht unterstützt, werden übersprungen. Bei einem Tracker ohne Termine wird nie nach Terminen gefragt.

`uv run agent-pm deps` zeigt die Datenqualität und jede Lücke an. Später, in Phase 3, gehen dieselben Fragen als einzelne WhatsApp- oder Sprach-Fragen raus, und eine Antwort kann nach Bestätigung das Ticket aktualisieren.
