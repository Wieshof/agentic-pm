# Zentrale agentische Abläufe

🇬🇧 [English](../workflows.md) · 🇩🇪 Deutsch

Um wie ein menschlicher Projektmanager zu arbeiten, führt der Agent fünf Abläufe aus. Diese Seite beschreibt jeden davon und sagt ehrlich, wie viel heute schon gebaut ist.

✅ gebaut und getestet · 🗓️ geplant (siehe [Roadmap](roadmap.md)) · 🚫 bewusst nicht

## 1. Proaktive Abhängigkeitsauflösung

**Auslöser:** Eine Schätzung ändert sich, ein Termin verschiebt sich oder eine neue Teilanforderung kommt hinzu.

Der Agent durchläuft den Abhängigkeitsgraphen. Hängt Aufgabe B von Aufgabe A ab und verzögert sich A um zwei Tage, erfährt die zuständige Person für B davon und bekommt **einen Terminvorschlag, bevor Leerlauf entsteht**.

| | Was | |
|-|-----|-|
| ✅ | Risiken über die ganze Kette (A → B → C), mit Terminvorschlag, im Morgen-Briefing und in der Tagesabschluss-Notiz für Teamleitungen | [Datenqualität](data-quality.md) |
| ✅ | Abhängigkeiten über Tracker hinweg, zwischen Abteilungen oder Kunden | [mehrere Tracker](sources.md) |
| 🗓️ | Eine sofortige Nachricht, sobald sich ein Termin verschiebt (heute: mit dem nächsten Briefing) | noch nicht eingeplant |
| 🗓️ | Kalender der Zuständigen als Eingabe | zurückgestellt |

- Ergebnis: eine Benachrichtigung und ein Terminvorschlag. Den Termin selbst zu ändern braucht eine Freigabe (bei kundenrelevanten Terminen die einer Teamleitung).
- KPI-Ziel (in einem Pilotbetrieb noch nicht gemessen): Ein Blocker ist innerhalb von 2 Stunden sichtbar.

## 2. Widerspruchs-Triangulation

**Auslöser:** Zwei Quellen widersprechen sich, z. B. „erledigt“ in einer Chat-Antwort, während das Ticket noch offen ist.

Der Agent benennt die genaue Lücke, ermittelt, **wer den fehlenden Kontext hat**, und stellt dieser Person **eine kurze Frage**, um den Stand zu klären.

| | Was | |
|-|-----|-|
| ✅ | Status-Aussagen in E-Mail und Chat („erledigt“, „hänge fest“) werden mit dem Tracker verglichen; die zuständige Person bestätigt mit „ja“, alle anderen gehen über eine Freigabe | [Chat](chat.md) |
| ✅ | Ein letzter Ticket-Kommentar, der einen anderen Status behauptet, erscheint im Briefing der zuständigen Person | |
| 🗓️ | Review- und CI-Status von Pull Requests als Quellen | noch nicht eingeplant |
| 🗓️ | Ein 60-Sekunden-Anruf als Weg zu fragen | Phase 3, [#13](https://github.com/Wieshof/agentic-pm/issues/13) |

- Ergebnis: der bereinigte Status, mit einem Audit-Kommentar, wer ihn bestätigt hat.

## 3. Mühelose „How-to“-Dokumentation

**Auslöser:** Jemand erklärt eine Lösung per E-Mail, im Chat oder in einer Sprachnachricht. Zum Beispiel: *„Ich habe das Auth-Timeout behoben, indem ich die Redis-Poolgröße erhöht und den Retry-Header angepasst habe.“*

Der Agent macht daraus sauberes Markdown und hängt es an das Ticket an. Die Erklärung darf in jeder Sprache kommen; das How-to wird in der `ticket_language` des Trackers geschrieben (aus einer deutschen Sprachnachricht wird z. B. ein englisches How-to):

```markdown
### Wie es gelöst wurde
- **Problem:** Auth-Anfragen laufen unter Last in ein Timeout
- **Ursache:** Redis-Verbindungspool ausgeschöpft
- **Lösung:** Redis-Poolgröße erhöht; Retry-Header angepasst
- **Verifiziert von:** <Person>, <Datum>
- **Quelle:** Sprachnachricht (transkribiert)
```

| | Was |
|-|-----|
| ✅ | Aus E-Mail-Antworten und aus Matrix- oder Signal-Nachrichten, auch aus Sprachnachrichten (lokal transkribiert) |
| ✅ | Wird eine Aufgabe geschlossen, wird die zuständige Person einmal um ein kurzes How-to gebeten |
| 🗓️ | Aus Telefonaten ([#13](https://github.com/Wieshof/agentic-pm/issues/13)) |

## 4. Adaptive Nachfass-Taktung

Der Agent passt sich **pro offener Frage an, nie pro Person** ([ADR-0005](../adr/0005-chat-channels.de.md)). Er führt keine Historie über irgendwen und berechnet keinen Wert dafür, wie schnell jemand reagiert ([ADR-0004](../adr/0004-people-data-boundaries.de.md)).

| | Was |
|-|-----|
| ✅ | **Das einzige Gedächtnis ist das Ticket.** Fragt der Agent zum ersten Mal (z. B. nach einem Termin), hinterlässt er eine kurze Notiz am Ticket. Eine Antwort oder irgendein Kommentar der gefragten Personen zählt als Antwort. |
| ✅ | **Dringende Fragen** (niemand zuständig, ein Blocker, andere Arbeit wartet) kommen in jedem Briefing. Alles andere wird gebündelt und einmal pro Woche gefragt. |
| ✅ | **Ein anderer Kanal:** Nach ein paar unbeantworteten Erinnerungen *zu dieser Frage* (`escalate_after_ignored`, Standard 3) versucht der Agent zusätzlich den nächsten Kanal, den die Person unter `prefer` angegeben hat. |
| ✅ | **Teamleitungen sehen die Aufgabe, nicht die Person:** „#12 hat immer noch keinen Termin“, nie „Sam hat nicht geantwortet“. |
| ✅ | Ruhezeiten, Unterbrechungswünsche und Kanäle kommen aus dem eigenen Eintrag jeder Person in `team.yaml`. |
| 🗓️ | Ein Anruf als einer dieser Kanäle ([#13](https://github.com/Wieshof/agentic-pm/issues/13)) |
| 🚫 | Messen, wie schnell jemand antwortet, oder Menschen vergleichen |

## 5. Statusberichte & Scrum-Artefakte

Regelmäßige Statusberichte gehen **per E-Mail oder im Chat** raus, zu der Zeit, die jede Person gewählt hat: ein Morgen-Briefing für alle, eine Tagesabschluss-Notiz und ein Wochenrückblick für Teamleitungen.

| | Was |
|-|-----|
| ✅ | Morgen-Briefing (E-Mail oder Chat), Tagesabschluss-Notiz, Wochenrückblick |
| 🗓️ | Gesprochene Briefings, bei denen Zuhörer Rückfragen stellen können ([#13](https://github.com/Wieshof/agentic-pm/issues/13)) |
| 🗓️ | Scrum-Artefakte, siehe unten (Phase 5) |

Geplant für Phase 5: Scrum-Artefakte aus Live-Trackerdaten aktuell halten.

| Artefakt | Wie der Agent unterstützen wird |
|----------|---------------------------------|
| Product Backlog | Markiert veraltete / ungeschätzte Einträge, schlägt Refinement-Fragen vor |
| Sprint Backlog | Verfolgt Zusage vs. Fortschritt, zeigt gefährdete Einträge |
| Inkrement / Definition of Done | Prüft DoD-Signale (PR gemergt, Tests grün, Doku angehängt) |
| Daily Scrum | Asynchrones Stand-up über den Kanal jeder Person, Zusammenfassung ans Team |
| Sprint Review / Retro | Vorentwürfe für Review-Notizen und Retro-Impulse aus Sprintdaten |
| Burndown | Wird in Briefings erzeugt statt in einem eigenen Dashboard |

> Offene Frage: Soll der Agent Artefakte *umgestalten* (z. B. Stories neu schneiden) oder nur darüber berichten? Wird in der Roadmap als Punkt in Phase 5 geführt.
