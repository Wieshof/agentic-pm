# ADR-0002: Strategie für Tracker-Adapter

🇬🇧 [English](0002-tracker-adapter-strategy.md) · 🇩🇪 Deutsch

- **Status:** angenommen
- **Datum:** 2026-11-12
- **Issue:** #18

## Kontext

Teams nutzen sehr unterschiedliche Tracker: Jira, Asana, monday.com, Notion, Trello, Planner, Redmine, Bugzilla, Linear, GitLab und mehr. Sie unterscheiden sich darin, was sie liefern können (native Abhängigkeiten, Schätzungen, Webhooks), und darin, wie Daten aufgebaut sind (feste Felder vs. selbst definierte Spalten und Eigenschaften). Wir können nicht alle Adapter auf einmal bauen, dürfen uns aber auch nicht verbauen, und Nutzer müssen klar sehen, was mit ihrem Tracker funktioniert.

## Entscheidung

1. **Ein Katalog als einzige Quelle der Wahrheit.** `src/agentic_pm/adapters/catalog.yaml` listet jeden bekannten Tracker mit Fähigkeiten, Status (verfügbar / geplant / Kandidat), Stufe und Issue. Die Übersicht in der Doku (DE/EN), `agent-pm trackers` und die Prüfung von `team.yaml` werden daraus erzeugt. CI schlägt fehl, wenn die Doku abweicht.
2. **Angegebene Fähigkeiten, sanftes Zurückfallen.** Jeder Adapter stellt `capabilities` bereit (Abhängigkeiten, Schätzungen, Fälligkeiten, mehrere Zuständige, Hierarchie, Ereignisse, Schreiben). Die Engine richtet sich danach und meldet Einschränkungen an Teamleitungen, statt zu schweigen.
3. **Ein Protokoll, eine Vertrags-Testsuite.** Alle Adapter implementieren `TrackerAdapter` und bestehen `agentic_pm.testing.AdapterContract`, mit aufgezeichneten API-Antworten, damit CI keine Konten braucht.
4. **Plugins über Entry Points** (`agentic_pm.adapters`), damit Adapter auch außerhalb dieses Repositorys leben können.
5. **Zuordnungen in der Konfiguration, nicht im Code.** Tracker mit selbst definierten Feldern werden über `project.tracker_options` eingerichtet (nie Geheimnisse).
6. **Zuerst nur lesend.** Jeder Adapter startet nur lesend. Schreiben folgt pro Tracker in Phase 2, hinter den Berechtigungsstufen.
7. **Stufen bestimmen die Reihenfolge.** Stufe 1: Jira, Azure DevOps, GitLab, Linear, Plane, GitHub Projects, Asana. Stufe 2: ClickUp, monday.com, Wrike, Shortcut, Smartsheet, MS Project, Redmine, Gitea/Forgejo, Taiga, Notion. Stufe 3: Bugzilla, Trello, MantisBT, Microsoft Planner, Todoist, Taskade.

Noch offen, jeweils als Issue erfasst: eine Polling-Ereignisquelle (#22), ein geprüftes Zuordnungsschema (#23) und eine MCP-Brücke für seltene Tracker (#24).

## Konsequenzen

- ✅ Nutzer sehen Unterstützung und Einschränkungen, bevor sie etwas verbinden.
- ✅ Neue Adapter sind größtenteils Fleißarbeit: Protokoll umsetzen, Antworten aufzeichnen, Vertrags-Testsuite bestehen.
- ⚠️ Katalogzeilen für noch nicht gebaute Tracker stammen aus Dokumentation und können falsch sein. Sie sind als „noch nicht live geprüft“ markiert, bis es einen Adapter gibt.
- ⚠️ Tracker mit frei gestaltbaren Daten (Notion, monday.com, Trello) brauchen pro Team einen Zuordnungsschritt. Das ist mehr Einrichtung als bei Trackern mit festem Schema.
