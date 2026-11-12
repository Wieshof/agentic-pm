# PM-Abdeckung

🇬🇧 [English](../pm-coverage.md) · 🇩🇪 Deutsch

Wie agentic-pm die komplette Rolle einer Projektleitung abdeckt: Aufgaben, täglicher/wöchentlicher/monatlicher Takt und Erfolgskennzahlen. Du siehst, was gebaut ist, was geplant ist (mit Issue), was beim Menschen bleibt und was wir bewusst nicht tun.

✅ gebaut · 🗓️ geplant · 🤝 nur Unterstützung (der Agent bereitet vor, ein Mensch entscheidet) · 🚫 bewusst nicht (siehe [ADR-0004](../adr/0004-people-data-boundaries.de.md))

## Aufgaben

### Projektplanung & -start

| Aufgabe | | Wo |
|---|:-:|---|
| Umfang, Ziele, Ergebnisse, Erfolgskriterien aus einem Sponsor-Briefing | 🗓️ | [#48](https://github.com/Wieshof/agentic-pm/issues/48) |
| PSP, Meilensteine, Abnahmekriterien, erste Abhängigkeiten | 🗓️ | [#48](https://github.com/Wieshof/agentic-pm/issues/48) |
| Zeitplan, kritischer Pfad, Basispläne | 🗓️ | Verzugserkennung ✅; [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Risikoregister, Kommunikations- & Qualitätsplan | 🗓️ | [#49](https://github.com/Wieshof/agentic-pm/issues/49), [#61](https://github.com/Wieshof/agentic-pm/issues/61), [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Budgetschätzung, Ressourcenplan | 🗓️ | [#58](https://github.com/Wieshof/agentic-pm/issues/58), [#46](https://github.com/Wieshof/agentic-pm/issues/46) |
| Machbarkeitsstudie, Business Case | 🤝 | nur Entwürfe |
| Governance, Entscheidungsrahmen, Eskalationswege | 🗓️ | Berechtigungsstufen ✅; [#11](https://github.com/Wieshof/agentic-pm/issues/11), [#51](https://github.com/Wieshof/agentic-pm/issues/51) |

### Umsetzung & Führung

| Aufgabe | | Wo |
|---|:-:|---|
| Fortschritt verfolgen, nachfassen, Blocker lösen | ✅ | Briefings, Abhängigkeitsanalyse; [#14](https://github.com/Wieshof/agentic-pm/issues/14), [#15](https://github.com/Wieshof/agentic-pm/issues/15) |
| Abhängigkeiten über Arbeitsstränge koordinieren | ✅ | ein Projekt; projektübergreifend [#59](https://github.com/Wieshof/agentic-pm/issues/59) |
| Aufgaben zuweisen, Erwartungen klären | 🗓️ | nur Vorschläge, Teamleitung gibt frei [#11](https://github.com/Wieshof/agentic-pm/issues/11) |
| Auslastung & Kapazitätskonflikte | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46) (aufgabenbezogen) |
| Coaching, Feedback, Leistungsbeurteilung | 🤝 | höchstens neutrales 1:1-Material, siehe ADR-0004 |
| Konfliktlösung, Motivation | 🤝 | Mensch |

### Stakeholder & Kommunikation

| Aufgabe | | Wo |
|---|:-:|---|
| Angepasste Updates pro Person und Kanal | ✅ | E-Mail-Briefings (DE/EN); [#12](https://github.com/Wieshof/agentic-pm/issues/12), [#13](https://github.com/Wieshof/agentic-pm/issues/13), [#16](https://github.com/Wieshof/agentic-pm/issues/16) |
| Statusberichte, Management-Briefings, Prognosen | 🗓️ | [#45](https://github.com/Wieshof/agentic-pm/issues/45), [#54](https://github.com/Wieshof/agentic-pm/issues/54) |
| Stakeholder-Landkarte & Beteiligungsplan | 🗓️ | [#61](https://github.com/Wieshof/agentic-pm/issues/61) |
| Workshops, Steuerkreise: Agenda, Protokoll, Entscheidungen | 🗓️ | [#51](https://github.com/Wieshof/agentic-pm/issues/51) |
| Erste Anlaufstelle für Fragen | 🗓️ | [#9](https://github.com/Wieshof/agentic-pm/issues/9), [#12](https://github.com/Wieshof/agentic-pm/issues/12), [#13](https://github.com/Wieshof/agentic-pm/issues/13) |

### Risiko-, Problem- & Änderungsmanagement

| Aufgabe | | Wo |
|---|:-:|---|
| Abhängigkeitsrisiken und Verzug | ✅ | Abhängigkeitsanalyse |
| Widersprüchliche Statusangaben | 🗓️ | [#15](https://github.com/Wieshof/agentic-pm/issues/15) |
| RAID-Register mit Wahrscheinlichkeit × Auswirkung, Verantwortlichen, Gegenmaßnahmen | 🗓️ | [#49](https://github.com/Wieshof/agentic-pm/issues/49) |
| Formale Änderungssteuerung inkl. Scope Creep aus Chats | 🗓️ | [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Eskalation von Problemen | 🗓️ | [#11](https://github.com/Wieshof/agentic-pm/issues/11), [#49](https://github.com/Wieshof/agentic-pm/issues/49) |

### Budget, Zeitplan & Ressourcen

| Aufgabe | | Wo |
|---|:-:|---|
| Zeitplan überwachen, Verzug aufholen | ✅ | Risiken + Terminvorschläge; [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Kapazitätsplanung, Ressourcenkonflikte | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46), [#53](https://github.com/Wieshof/agentic-pm/issues/53) |
| Budget vs. Ist, Burn Rate, Prognosen | 🗓️ | [#57](https://github.com/Wieshof/agentic-pm/issues/57), [#58](https://github.com/Wieshof/agentic-pm/issues/58) |
| Beschaffung, Lieferantenverträge, Rechnungen | 🤝 | Erinnerungen und Zusammenfassungen; Freigaben bleiben beim Menschen |

### Qualität & Lieferung

| Aufgabe | | Wo |
|---|:-:|---|
| Abnahmekriterien, Test- und UAT-Status | 🗓️ | [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Definition-of-Done-Prüfungen | 🗓️ | [#17](https://github.com/Wieshof/agentic-pm/issues/17) |
| Abschluss, Review nach Einführung, Lessons Learned | 🗓️ | [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Wissen während des Projekts sichern | 🗓️ | [#10](https://github.com/Wieshof/agentic-pm/issues/10) |

### Prozessverbesserung & Compliance

| Aufgabe | | Wo |
|---|:-:|---|
| Methoden: Scrum, Kanban, PRINCE2, hybrid | 🗓️ | [#17](https://github.com/Wieshof/agentic-pm/issues/17), [#60](https://github.com/Wieshof/agentic-pm/issues/60) |
| Audit-Trail, Berechtigungsstufen, Einwilligung | ✅ | Audit-Fußzeile, Webhook-Filter; [#8](https://github.com/Wieshof/agentic-pm/issues/8), [#11](https://github.com/Wieshof/agentic-pm/issues/11) |
| Portfolio-Reporting und Priorisierung | 🗓️ | [#59](https://github.com/Wieshof/agentic-pm/issues/59) |
| PMO-Vorlagen und Prozessverbesserung | 🗓️ | [#56](https://github.com/Wieshof/agentic-pm/issues/56) |

## Arbeitstakt

Die Rituale einer Projektleitung werden zu **geplanten Auslösern** in `team.yaml` ([#45](https://github.com/Wieshof/agentic-pm/issues/45)). Der Agent prüft seinen eigenen Takt monatlich und schlägt Änderungen als Pull Request vor ([#56](https://github.com/Wieshof/agentic-pm/issues/56)). So ist der Arbeitstakt ein lebendes Dokument.

### Täglich

| Aufgabe | | Wo |
|---|:-:|---|
| Morgen-Triage: Warnsignale, Überfälliges, Blocker | ✅ | Morgen-Briefing; Auslöser [#45](https://github.com/Wieshof/agentic-pm/issues/45) |
| RAID-Log auf neue oder eskalierende Punkte prüfen | 🗓️ | [#49](https://github.com/Wieshof/agentic-pm/issues/49), [#45](https://github.com/Wieshof/agentic-pm/issues/45) |
| Bei Aufgaben auf dem kritischen Pfad nachfassen | 🗓️ | [#14](https://github.com/Wieshof/agentic-pm/issues/14), [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Entscheidungen und Aufgaben sofort dokumentieren | 🗓️ | [#51](https://github.com/Wieshof/agentic-pm/issues/51), [#10](https://github.com/Wieshof/agentic-pm/issues/10) |
| Tagesende: RAID aktualisieren, neue Risiken und Änderungen erfassen | 🗓️ | [#45](https://github.com/Wieshof/agentic-pm/issues/45), [#49](https://github.com/Wieshof/agentic-pm/issues/49), [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Nachrichten der Nacht sichten, Posteingang leeren | 🤝 | Routinefragen beantwortet der Agent selbst [#9](https://github.com/Wieshof/agentic-pm/issues/9) |

### Wöchentlich

| Aufgabe | | Wo |
|---|:-:|---|
| Zeitplan-Review, kritischer Pfad, Verzug | 🗓️ | [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Wöchentlicher Statusbericht / Steuerkreis-Zusammenfassung | 🗓️ | [#45](https://github.com/Wieshof/agentic-pm/issues/45) |
| Änderungsanträge bearbeiten | 🗓️ | [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Ressourcenplanung für die nächsten 1–2 Wochen | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46), [#53](https://github.com/Wieshof/agentic-pm/issues/53) |
| 1:1s, Stimmung, Anerkennung | 🤝 | Mensch; keine abgeleitete Stimmung (ADR-0004) |

### Monatlich

| Aufgabe | | Wo |
|---|:-:|---|
| Gesundheitscheck gegen Basisplan und Erfolgskriterien | 🗓️ | [#54](https://github.com/Wieshof/agentic-pm/issues/54) |
| Finanz-Review und Prognose | 🗓️ | [#58](https://github.com/Wieshof/agentic-pm/issues/58) |
| Kapazitätsplanung für 1–3 Monate | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46), [#59](https://github.com/Wieshof/agentic-pm/issues/59) |
| Retrospektive / Lessons Learned | 🗓️ | [#17](https://github.com/Wieshof/agentic-pm/issues/17), [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Den eigenen Arbeitstakt prüfen und anpassen | 🗓️ | [#56](https://github.com/Wieshof/agentic-pm/issues/56) |
| Leistungs- und Entwicklungsgespräche | 🚫 | nie automatisiert (ADR-0004) |

## Erfolgskennzahlen

Unsere bisherigen KPIs messen das Werkzeug (weniger Ticketpflege, schnellere Blocker-Erkennung). Diese messen das Projekt:

| Kennzahl | Quelle | Issue |
|---|---|---|
| Termintreue | Tracker + Basisplan | [#54](https://github.com/Wieshof/agentic-pm/issues/54), [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Budgetabweichung | Zeiterfassung / Finanzen | [#58](https://github.com/Wieshof/agentic-pm/issues/58) |
| Umfangstreue, Anzahl und Wirkung von Änderungen | Änderungsanträge | [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Stakeholder-Zufriedenheit | Kurzumfragen (Teamebene) | [#61](https://github.com/Wieshof/agentic-pm/issues/61) |
| Team-Engagement | Kurzumfragen, Gruppe ab 5 | [#61](https://github.com/Wieshof/agentic-pm/issues/61), [#47](https://github.com/Wieshof/agentic-pm/issues/47) |
| Lösung von Risiken und Problemen | RAID-Register | [#49](https://github.com/Wieshof/agentic-pm/issues/49) |
| Qualität der Ergebnisse | Fehler, Abnahme | [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Prozessverbesserung & Wissensaustausch | How-tos, Lessons Learned | [#10](https://github.com/Wieshof/agentic-pm/issues/10), [#55](https://github.com/Wieshof/agentic-pm/issues/55) |

## Wo PM-Einträge liegen

RAID-Einträge, Änderungsanträge, Entscheidungen und Basispläne liegen im Tracker (Typen oder Labels) oder als versionierte Dateien unter `.agent-pm/`, nie in einer Datenbank des Agenten. Siehe [ADR-0003](../adr/0003-pm-records-without-a-database.de.md).

## Datenquellen über Tracker hinaus

Kalender ([#53](https://github.com/Wieshof/agentic-pm/issues/53)), Zeiterfassung und Finanzen ([#57](https://github.com/Wieshof/agentic-pm/issues/57)) sowie alle Tracker in der [Übersicht](trackers.md), jetzt auch Azure DevOps, Smartsheet und MS Project.

## Grenzen

Der Agent unterstützt bei Personenthemen, aber er überwacht und beurteilt keine Menschen. Kapazitätsprüfungen sind aufgabenbezogen, es gibt keine Personenhistorie und keine Werte pro Person, Team-Kennzahlen gibt es nur auf Teamebene, und es wird nichts über Stimmung abgeleitet. Details und rechtlicher Hintergrund: [ADR-0004](../adr/0004-people-data-boundaries.de.md).

Phasen: [Roadmap](roadmap.md).
