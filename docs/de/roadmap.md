# Phasenweise Roadmap

🇬🇧 [English](../roadmap.md) · 🇩🇪 Deutsch

Jede Phase ist ein GitHub-Meilenstein. Die Phasen bauen aufeinander auf. Jede Phase endet mit etwas, das ein Pilotteam tatsächlich nutzen kann.

## Phase 0 — Grundlagen ✅
- Repository, Dokumentation, ADR-Prozess, Beitragsrichtlinien
- Tech-Stack und LLM-Anbieter auswählen (ADR)
- Schema + Validator für `team.yaml`
- Gemeinsame `TrackerAdapter`-Schnittstelle + MCP-Werkzeugumfang

## Phase 1 — Einblick nur lesend (ein Tracker, E-Mail) ✅ gebaut · Pilot steht aus
- GitHub-Issues-Adapter (lesend), danach OpenProject oder Plane
- Abhängigkeitsgraph-Analyse (nur lesend)
- Morgendliches E-Mail-Briefing für „Leser“
- **Abschluss:** Ein Pilotteam erhält korrekte tägliche Briefings, ohne dass der Agent etwas schreibt

## Phase 2 — Zurückschreiben, Dokumentation & Takt ✅ gebaut · Pilot steht aus

Siehe [Den Agenten betreiben](running.md).

- Schreibstufe „geringes Risiko“ mit Audit-Trail (Kommentare, Labels, Blocker-Tags)
- E-Mail-Routing per Plus-Adressierung (`pm+repo-task142@…`)
- Wissensextraktion: E-Mail/Chat → How-to-Markdown im Ticket
- Berechtigungs- & Audit-Wächter + Bestätigungsablauf für Teamleitungen (Web-Steuerungsoberfläche v0)
- **Arbeitstakt:** geplante Auslöser in `team.yaml` (Morgen-Triage, RAID-Check am Tagesende, Wochen-Digest, monatlicher Gesundheitscheck)
- **Kapazität & Terminkollisionen** über alle verbundenen Projekte (nur lesend, aufgabenbezogen)
- **Grenzen für Personendaten** festgeschrieben und umgesetzt ([ADR-0004](../adr/0004-people-data-boundaries.de.md))
- **Abschluss:** ≥ 50 % der geschlossenen Pilot-Tickets enthalten ein vom Agenten verfasstes How-to; der Wochen-Digest ersetzt die manuelle Status-Mail

## Phase 3 — Omnichannel (Chat & Sprache)
- WhatsApp-Business-Integration (Routing über Antwortkontext, Sprachnachrichten)
- Sprachagent: eingehende Anrufe, ausgehende 60-Sekunden-Check-ins, Transkriptionshinweis, Transkripte nur im Arbeitsspeicher
- Adaptive Nachfass-Taktung
- Widerspruchs-Triangulation + Mikro-Interviews
- **Abschluss:** Blocker werden in < 2 h sichtbar; mindestens eine Person ohne Tracker-Konto ist pro Pilotteam aktiv

## Phase 4 — Planung & Steuerung (neu)
Die Einträge liegen im Tracker oder im Repository, nie in einer Datenbank des Agenten ([ADR-0003](../adr/0003-pm-records-without-a-database.de.md)).
- **Projektstart / PSP-Generator:** Ein Sponsor beschreibt ein Ziel per Sprache, E-Mail oder Chat; der Agent entwirft Meilensteine, Arbeitspakete, Abnahmekriterien und erste Abhängigkeiten im Tracker, **als Entwurf zur Freigabe**
- **RAID-Register:** Risiken, Annahmen, Probleme und Abhängigkeiten als Tracker-Einträge (`type:risk` …) mit Wahrscheinlichkeit × Auswirkung, Verantwortlichen und Gegenmaßnahme
- **Änderungssteuerung:** Neuer Umfang, der über irgendeinen Kanal kommt („könntet ihr noch … einbauen“), wird mit seiner Auswirkung auf den Zeitplan markiert und **vor** dem Anlegen von Arbeitspaketen der Teamleitung zur Freigabe vorgelegt
- **Entscheidungslog & Besprechungsnotizen:** Tagesordnungen aus offenen Punkten, Entscheidungen und Aufgaben zurück in den Tracker
- **Basispläne & kritischer Pfad:** Basisplan-Schnappschüsse, Puffer, Verzug gegenüber dem Basisplan; Kalender als Quelle für Verfügbarkeit
- **Monatlicher Gesundheitscheck** gegen Basisplan und Erfolgskriterien; Projekt-KPIs (Termintreue, Änderungsvolumen, Risikolösung, Fehlertrend)
- **Qualität & Abschluss:** Abnahmekriterien und UAT-Status, Fehlertrends, Abschlussbericht und Lessons Learned
- **Abschluss:** Ein Pilotprojekt läuft einen Monat lang mit RAID, Änderungssteuerung und Gesundheitscheck, gepflegt vom Agenten

## Phase 5 — Scrum-Artefakte & gesprochene Briefings
- Interaktive gesprochene Statusbriefings mit Fragen und Antworten
- Asynchrones Daily Scrum, Entwürfe für Sprint Review/Retro, DoD-Prüfungen
- Entscheiden, ob der Agent Artefakte umgestaltet oder nur darüber berichtet
- **Selbstlernender Takt:** monatliche Retrospektive des eigenen Arbeitstakts, als Pull Request für `team.yaml` vorgeschlagen
- **Abschluss:** Ein Sprint läuft vollständig ohne separates Reporting-Dashboard

## Phase 6 — Skalierung & Ökosystem
Adapter-Arbeit kann parallel zu anderen Phasen laufen.
- Weitere Adapter nach Stufen, siehe [Tracker](trackers.md) und Epic #18 (inkl. Azure DevOps, Smartsheet, MS Project)
- Synchronisierung der Präferenzen über SSO (Entra ID / Google Workspace)
- Policy-as-Code
- KPI-Messung & Bericht zum Infrastrukturabbau

## Phase 7 — Geld & Portfolio (neu)
- Zeiterfassung und Finanzdaten als Quellen (z. B. Tempo, Harvest, Clockify, Tabellen)
- Budget vs. Ist, Burn Rate, Abweichungserklärungen und Prognosen
- Portfolio-Sicht: projektübergreifende Abhängigkeiten, Kapazität und Priorisierung
- Methodik-Profile: Scrum, Kanban, PRINCE2-Phasenfreigaben, hybrid
- Stakeholder-Landkarte und Ein-Fragen-Umfragen über den Kanal jeder Person

So deckt sich das mit der kompletten PM-Rolle: [PM-Abdeckung](pm-coverage.md).
