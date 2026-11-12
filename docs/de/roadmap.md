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

## Phase 2 — Zurückschreiben & Dokumentation
- Schreibstufe „geringes Risiko“ mit Audit-Trail (Kommentare, Labels, Blocker-Tags)
- E-Mail-Routing per Plus-Adressierung (`pm+repo-task142@…`)
- Wissensextraktion: E-Mail/Chat → How-to-Markdown im Ticket
- Berechtigungs- & Audit-Wächter + Bestätigungsablauf für Teamleitungen (Web-Steuerungsoberfläche v0)
- **Abschluss:** ≥ 50 % der geschlossenen Pilot-Tickets enthalten ein vom Agenten verfasstes How-to

## Phase 3 — Omnichannel (Chat & Sprache)
- WhatsApp-Business-Integration (Routing über Antwortkontext, Sprachnachrichten)
- Sprachagent: eingehende Anrufe, ausgehende 60-Sekunden-Check-ins, Transkriptionshinweis, Transkripte nur im Arbeitsspeicher
- Adaptive Nachfass-Taktung
- Widerspruchs-Triangulation + Mikro-Interviews
- **Abschluss:** Blocker werden in < 2 h sichtbar; mindestens eine Person ohne Tracker-Konto ist pro Pilotteam aktiv

## Phase 4 — Scrum-Artefakte & gesprochene Briefings
- Interaktive gesprochene Statusbriefings mit Fragen und Antworten
- Asynchrones Daily Scrum, Entwürfe für Sprint Review/Retro, DoD-Prüfungen
- Entscheiden, ob der Agent Artefakte umgestaltet oder nur darüber berichtet
- **Abschluss:** Ein Sprint läuft vollständig ohne separates Reporting-Dashboard

## Phase 5 — Skalierung & Ökosystem
- Weitere Adapter: Taiga, GitLab, Jira, Linear
- Synchronisierung der Präferenzen über SSO (Entra ID / Google Workspace)
- Multiprojekt- / Portfolio-Ansichten, Policy-as-Code
- KPI-Messung & Bericht zum Infrastrukturabbau
