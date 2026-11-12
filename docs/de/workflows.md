# Zentrale agentische Abläufe

🇬🇧 [English](../workflows.md) · 🇩🇪 Deutsch

Um wie ein menschlicher Projektmanager zu arbeiten, führt das System im Hintergrund fünf autonome Schleifen aus.

## 1. Proaktive Abhängigkeitsauflösung

**Auslöser:** Eine Schätzung ändert sich, ein Termin verschiebt sich oder eine neue Teilanforderung kommt hinzu.

Der Agent durchläuft den Abhängigkeitsgraphen. Hängt Aufgabe B von Aufgabe A ab und verzögert sich A um zwei Tage, benachrichtigt er die verantwortliche Person für B sofort über ihren bevorzugten Kanal und **schlägt angepasste Termine vor, bevor Leerlauf entsteht**.

- Eingaben: Tracker-Beziehungen, Schätzungen, Kalender der Zuständigen (optional)
- Ergebnis: Benachrichtigung + Terminvorschlag (Freigabe nötig, wenn kundenrelevant)
- KPI: mittlere Zeit bis zur Sichtbarkeit eines Blockers < 2 h

## 2. Widerspruchs-Triangulation

**Auslöser:** Zwei Quellen widersprechen sich, z. B. „Feature fertig“ in WhatsApp, während der verknüpfte PR noch nicht reviewt ist.

Der Agent benennt die genaue Lücke, ermittelt, **wer den fehlenden Kontext hat**, und startet ein gezieltes **Mikro-Interview** (E-Mail, Chat oder 60-Sekunden-Anruf), um den Stand zu klären.

- Quellen: Chat-Aussagen, Tracker-Status, Review- & CI-Status von PR/MR, Commits
- Ergebnis: bereinigter Status + Audit-Kommentar mit Begründung

## 3. Mühelose „How-to“-Dokumentation

**Auslöser:** Jemand erklärt eine Lösung in einem Anruf, einer Sprachnachricht oder im Chat. Zum Beispiel: *„Ich habe das Auth-Timeout behoben, indem ich die Redis-Poolgröße erhöht und den Retry-Header angepasst habe.“*

Der Agent macht daraus sauberes Markdown und hängt es an das Ticket an. Die Erklärung darf in jeder Sprache kommen; das How-to wird in `project.ticket_language` geschrieben (aus einer deutschen Sprachnachricht wird z. B. ein englisches How-to):

```markdown
### Wie es gelöst wurde
- **Problem:** Auth-Anfragen laufen unter Last in ein Timeout
- **Ursache:** Redis-Verbindungspool ausgeschöpft
- **Lösung:** Redis-Poolgröße erhöht; Retry-Header angepasst
- **Verifiziert von:** <Person>, <Datum>
- **Quelle:** Sprachnachricht (transkribiert)
```

## 4. Adaptive Nachfass-Taktung

Statt allen dieselben generischen Erinnerungen zu schicken, verfolgt der Agent pro Person und Kanal, wie schnell reagiert wird.

- Ein **Sprecher**, der drei E-Mails ignoriert, bekommt stattdessen einen kurzen ausgehenden Sprach-Check-in.
- Ein **Leser**, der keine Unterbrechungen möchte, bekommt nicht dringende Fragen gebündelt im morgendlichen E-Mail-Briefing.
- Dringlichkeit, Ruhezeiten und Kanalpräferenzen kommen aus `team.yaml`.

## 5. Statusberichte & Scrum-Artefakte

Regelmäßige Statusberichte werden **per E-Mail oder als gesprochenes Briefing** verschickt. Zuhörer können während des Briefings **Rückfragen stellen und Klärungen erbitten**.

Der Agent kann außerdem Scrum-Artefakte aus Live-Trackerdaten aktuell halten:

| Artefakt | Wie der Agent unterstützt |
|----------|---------------------------|
| Product Backlog | Markiert veraltete / ungeschätzte Einträge, schlägt Refinement-Fragen vor |
| Sprint Backlog | Verfolgt Zusage vs. Fortschritt, zeigt gefährdete Einträge |
| Inkrement / Definition of Done | Prüft DoD-Signale (PR gemergt, Tests grün, Doku angehängt) |
| Daily Scrum | Asynchrones Stand-up über den Kanal jeder Person, Zusammenfassung ans Team |
| Sprint Review / Retro | Vorentwürfe für Review-Notizen und Retro-Impulse aus Sprintdaten |
| Burndown | Wird in Briefings erzeugt statt in einem eigenen Dashboard |

> Offene Frage: Soll der Agent Artefakte *umgestalten* (z. B. Stories neu schneiden) oder nur darüber berichten? Wird in der Roadmap als Punkt in Phase 5 geführt.
