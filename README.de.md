# agentic-pm

🇬🇧 [English](README.md) · 🇩🇪 Deutsch

**Eine omnichannel-fähige, agentische Projektmanagement-Schicht, die auf den Issue-Trackern aufsetzt, die Du bereits nutzt.**

agentic-pm ersetzt Deinen Issue-Tracker nicht. Es ist eine intelligente Orchestrierungsschicht, die:

- den Live-Zustand aus bestehenden Open-Source- und API-first-Trackern **einliest** (OpenProject, Plane, Taiga, GitHub/GitLab Issues, Jira, Linear),
- über Abhängigkeiten, Widersprüche und implizites Wissen **schlussfolgert** und
- **mit jeder beteiligten Person über ihr bevorzugtes Medium spricht**: Lesen (E-Mail), Schreiben (Chat/WhatsApp), Sprechen (Telefonate) oder Zuhören (gesprochene Briefings), ergänzt um eine schlanke Web-Steuerungsoberfläche.

Der zugrunde liegende Tracker bleibt die einzige, synchronisierte Quelle der Wahrheit. Der Agent speichert selbst **keinen dauerhaften Aufgabenzustand**.

> Status: 🏗️ Phase 0 (Grundlagen) abgeschlossen. Siehe [Roadmap](docs/de/roadmap.md).

---

## Warum

Klassische PM-Werkzeuge zwingen alle Beteiligten in denselben starren Ablauf: Tracker öffnen, Ticket suchen, Felder bearbeiten, Doku schreiben. Die meisten tun das nicht. Tickets veralten, Blocker werden spät erkannt und Wissen bleibt in den Köpfen.

agentic-pm dreht das um. Die Beteiligten bleiben in dem Kanal, den sie ohnehin nutzen, und der Agent erledigt die Ticketarbeit für sie.

### Der Stack wird kleiner statt größer

1. **Weniger Schatten-Tools und Reporting-Dashboards.** Separate BI-Konnektoren, Status-Reporting-Plugins oder eigene Excel-Tracker werden überflüssig. Leser erhalten maßgeschneiderte E-Mail-Briefings, Sprecher gesprochene Briefings, beides direkt aus Live-Ticketdaten.
2. **Weniger PM-Lizenzen.** Stakeholder, Außendienst und Führungskräfte, die nur per Telefon, WhatsApp oder E-Mail kommunizieren, brauchen kein Tracker-Konto. Der Agent handelt über eine einzige Service-Integration stellvertretend für sie.
3. **Keine separaten Wikis für operatives Wissen.** Der Agent hält fest, *wie* Probleme in Sprach- und Chat-Check-ins gelöst wurden, und schreibt das direkt ins Ticket. Teams pflegen keine getrennten Dokumentationstools mehr, die veralten.

---

## Architektur im Überblick

```
            ┌──────────────────────────────────────────────────────────┐
  E-Mail ──►│                                                          │
  WhatsApp ►│   Omnichannel-Schnittstellenschicht (Routing-Gateway,    │
  Sprache ─►│   Kanalpräferenzen pro Person, Transport-Tagging)        │
  Web-UI ──►│                                                          │
            └──────────────────────────┬───────────────────────────────┘
                                       │
            ┌──────────────────────────▼───────────────────────────────┐
            │   Agentische Reasoning-Engine                            │
            │   • Abhängigkeitsgraph-Analyse  • Widerspruchserkennung  │
            │   • Wissensextraktion           • Taktung / Briefings    │
            │   • Berechtigungs- & Audit-Wächter                       │
            └──────────────────────────┬───────────────────────────────┘
                                       │
            ┌──────────────────────────▼───────────────────────────────┐
            │   Repository-Adapterschicht (Open Core)                  │
            │   REST- / GraphQL- / MCP-Konnektoren                     │
            └───┬──────────┬──────────┬──────────┬──────────┬──────────┘
                ▼          ▼          ▼          ▼          ▼
          OpenProject    Plane      Taiga   GitHub/GitLab  Jira/Linear
```

Details: [docs/de/architecture.md](docs/de/architecture.md)

## Zentrale agentische Schleifen

| # | Schleife | Was sie tut |
|---|----------|-------------|
| 1 | **Proaktive Abhängigkeitsauflösung** | Verschiebt sich eine Schätzung, durchläuft sie den Abhängigkeitsgraphen, warnt nachgelagerte Verantwortliche über ihren bevorzugten Kanal und schlägt neue Termine vor, bevor Leerlauf entsteht. |
| 2 | **Widerspruchs-Triangulation** | Erkennt widersprüchliche Aussagen, z. B. „fertig“ in WhatsApp, während der PR noch nicht reviewt ist. Sie ermittelt, wer den fehlenden Kontext hat, und führt ein kurzes Mikro-Interview. |
| 3 | **Mühelose How-to-Dokumentation** | Macht aus Sprachnachrichten und Anrufen („Auth-Timeout behoben, indem ich den Redis-Pool vergrößert habe …“) strukturiertes Markdown im Ticket. |
| 4 | **Adaptive Nachfass-Taktung** | Verfolgt, wie schnell jede Person reagiert, und wechselt den Kanal, wenn einer nicht funktioniert. Nicht dringende Fragen werden gebündelt. |
| 5 | **Statusberichte & Scrum-Artefakte** | Versendet Statusberichte per E-Mail oder als gesprochenes Briefing mit Rückfragemöglichkeit. Hält Scrum-Artefakte (Backlog, Sprint, Burndown, Review-Notizen) aktuell. |

Details: [docs/de/workflows.md](docs/de/workflows.md)

## Zustandslos by Design

| Daten | Wo sie liegen |
|-------|---------------|
| Aufgaben, Termine, Abhängigkeiten | Im bestehenden Tracker, bei jedem Ereignis live abgerufen |
| Präferenzen („Drucker-Profile“) | `.agent-pm/team.yaml` im Repository oder SSO-Verzeichnisattribute (Entra ID / Google Workspace) |
| How-to-Dokus & Audit-Logs | Ticketkommentare oder Markdown in `/docs` |
| Zuordnung Gespräch → Ticket | Transport-Tags: E-Mail-Plus-Adressierung / `Message-ID`, WhatsApp-Antwortkontext, Arbeitsspeicher der Anrufsitzung |

Details: [docs/de/data-model.md](docs/de/data-model.md) · Beispielkonfiguration: [.agent-pm/team.example.yaml](.agent-pm/team.example.yaml)

## Leitplanken & KPIs

- **Gestufte Schreibrechte:** Aktionen mit geringem Risiko laufen automatisch mit Audit-Trail. Folgenreiche Änderungen muss eine Teamleitung bestätigen.
- **Einwilligung & Datenschutz:** Anrufe kündigen an, wenn transkribiert wird. Logs sind auf den Projekt-Workspace beschränkt und werden nie zum Training externer Modelle verwendet.
- **KPIs:** mindestens 70 % weniger manuelle Ticketbearbeitung, unter 2 h bis ein Abhängigkeits-Blocker sichtbar wird, und die kanalübergreifende Beteiligungsquote.

Details: [docs/de/guardrails.md](docs/de/guardrails.md)

## Aufbau des Repositorys

```
.agent-pm/            Beispielkonfiguration für Team / Präferenzen
docs/
  architecture.md     Drei-Schichten-Architektur & Kanalzuordnung
  workflows.md        die fünf autonomen Schleifen
  data-model.md       zustandslose Datenhaltung & Routing
  guardrails.md       Berechtigungen, Datenschutz, KPIs
  roadmap.md          phasenweiser Lieferplan
  adr/                Architekturentscheidungen (ADRs)
  de/                 deutsche Fassungen aller Dokumente
```

## Entwicklung

Voraussetzungen: Python ≥ 3.12 und [uv](https://docs.astral.sh/uv/). Entscheidungen: [ADR-0001](docs/adr/0001-tech-stack-and-llm.de.md).

```bash
uv sync                                           # installieren
uv run pytest                                     # Tests
uv run agent-pm validate .agent-pm/team.yaml      # Team-Datei prüfen
uv run agent-pm schema > schemas/team.schema.json # JSON-Schema exportieren
uv run agent-pm mcp                               # MCP-Tracker-Server (stdio, Demodaten)
```

**Lokales LLM (Standard):** Betreibe einen beliebigen OpenAI-kompatiblen Server, z. B. [Ollama](https://ollama.com), und setze `llm.model` / `llm.base_url` in `team.yaml`. Live-Test: `AGENT_PM_LIVE_LLM=<Modell> uv run pytest tests/test_llm.py`.

| Modul | Zweck |
|-------|-------|
| `agentic_pm.config` | Schema & Validierung für `team.yaml` |
| `agentic_pm.adapters` | `TrackerAdapter`-Protokoll, Datenmodell, In-Memory-Referenztracker |
| `agentic_pm.audit` | Berechtigungsstufen & Audit-Fußzeile |
| `agentic_pm.mcp_server` | MCP-Werkzeuge über jedem Adapter, mit Stufenprüfung |
| `agentic_pm.llm` | Anbieterunabhängige LLM-Schnittstelle, lokaler OpenAI-kompatibler Anbieter |

## Mitwirken

Siehe [CONTRIBUTING.de.md](CONTRIBUTING.de.md). Designdiskussionen finden in GitHub Issues statt. Jede Roadmap-Phase hat einen Meilenstein.

## Lizenz

[Apache License 2.0](LICENSE)
