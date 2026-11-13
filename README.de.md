# agentic-pm

🇬🇧 [English](README.md) · 🇩🇪 Deutsch

**Eine omnichannel-fähige, agentische Projektmanagement-Schicht, die auf den Issue-Trackern aufsetzt, die Du bereits nutzt.**

agentic-pm ersetzt Deinen Issue-Tracker nicht. Es ist eine intelligente Orchestrierungsschicht, die:

- den Live-Zustand aus bestehenden Open-Source- und API-first-Trackern **einliest** (OpenProject, Plane, Taiga, GitHub/GitLab Issues, Jira, Linear),
- über Abhängigkeiten, Widersprüche und implizites Wissen **schlussfolgert** und
- **mit jeder beteiligten Person über ihr bevorzugtes Medium spricht**: Lesen (E-Mail), Schreiben (Chat/WhatsApp), Sprechen (Telefonate) oder Zuhören (gesprochene Briefings), ergänzt um eine schlanke Web-Steuerungsoberfläche.

Der zugrunde liegende Tracker bleibt die einzige, synchronisierte Quelle der Wahrheit. Der Agent speichert selbst **keinen dauerhaften Aufgabenzustand**.

> Status: ✍️ Phase 2 (Zurückschreiben, How-tos, Freigaben, Takt) gebaut, bereit für ein Pilotteam. Hier geht's los: [Erste Schritte](docs/de/getting-started.md) · [Den Agenten betreiben](docs/de/running.md). Siehe [Roadmap](docs/de/roadmap.md).

---

## Warum

Klassische PM-Werkzeuge zwingen alle Beteiligten in denselben starren Ablauf: Tracker öffnen, Ticket suchen, Felder bearbeiten, Doku schreiben. Die meisten tun das nicht. Tickets veralten, Blocker werden spät erkannt und Wissen bleibt in den Köpfen.

agentic-pm dreht das um. Die Beteiligten bleiben in dem Kanal, den sie ohnehin nutzen, und der Agent erledigt die Ticketarbeit für sie.

### Der Stack wird kleiner statt größer

1. **Weniger Schatten-Tools und Reporting-Dashboards.** Separate BI-Konnektoren, Status-Reporting-Plugins oder eigene Excel-Tracker werden überflüssig. Leser erhalten maßgeschneiderte E-Mail-Briefings, Sprecher gesprochene Briefings, beides direkt aus Live-Ticketdaten.
2. **Weniger PM-Lizenzen.** Stakeholder, Außendienst und Führungskräfte, die nur per Telefon, WhatsApp oder E-Mail kommunizieren, brauchen kein Tracker-Konto. Der Agent handelt über eine einzige Service-Integration stellvertretend für sie.
3. **Keine separaten Wikis für operatives Wissen.** Der Agent hält fest, *wie* Probleme in Sprach- und Chat-Check-ins gelöst wurden, und schreibt das direkt ins Ticket. Teams pflegen keine getrennten Dokumentationstools mehr, die veralten.

---

## Schnellstart

**1. Beschreibe Dein Team** in `.agent-pm/team.yaml`. Die Datei wird in Dein Repository eingecheckt und enthält deshalb nie Geheimnisse:

```yaml
project:
  tracker: github                # oder jira, asana, notion, ... siehe docs/de/trackers.md
  repo: deine-org/dein-repo
  leads: [alex]
  ticket_language: en            # der Agent schreibt Tickets auf Englisch ...
  agent_accounts: [agent-pm-bot] # ... mit diesem Login (seine eigenen Webhooks werden ignoriert)
people:
  alex:
    role: team-lead
    archetype: reader            # reader | writer | talker | listener
    language: de                 # ... während Alex mit dem Agenten Deutsch spricht
    channels: {email: alex@example.com}
    brief: {when: "08:00", format: email}
```

**2. Starte es:**

```bash
uv sync
uv run agent-pm validate                   # prüft team.yaml, auch auf eingefügte Geheimnisse
uv run agent-pm brief --person alex        # braucht GITHUB_TOKEN; probier zuerst --demo
```

> 🔐 **Geheimnisse nur in Umgebungsvariablen.** Tracker-Tokens, SMTP-/WhatsApp-Schlüssel und SIP-Zugangsdaten gehören nie in `team.yaml`. `agent-pm validate` lehnt Werte ab, die wie Zugangsdaten aussehen. Siehe [Geheimnisse](#geheimnisse).

Ausführliche Anleitung: [Erste Schritte](docs/de/getting-started.md) · vollständiges Beispiel: [.agent-pm/team.example.yaml](.agent-pm/team.example.yaml)

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

Details: [docs/de/workflows.md](docs/de/workflows.md) · **So deckt sich das mit der kompletten PM-Rolle** (Aufgaben, täglicher/wöchentlicher/monatlicher Takt, Kennzahlen, was beim Menschen bleibt): [PM-Abdeckung](docs/de/pm-coverage.md)

## Zustandslos by Design

| Daten | Wo sie liegen |
|-------|---------------|
| Aufgaben, Termine, Abhängigkeiten | Im bestehenden Tracker, bei jedem Ereignis live abgerufen |
| Präferenzen („Drucker-Profile“) | `.agent-pm/team.yaml` im Repository oder SSO-Verzeichnisattribute (Entra ID / Google Workspace) |
| How-to-Dokus & Audit-Logs | Ticketkommentare oder Markdown in `/docs` |
| Zuordnung Gespräch → Ticket | Transport-Tags: E-Mail-Plus-Adressierung / `Message-ID`, WhatsApp-Antwortkontext, Arbeitsspeicher der Anrufsitzung |

Details: [docs/de/data-model.md](docs/de/data-model.md) · Beispielkonfiguration: [.agent-pm/team.example.yaml](.agent-pm/team.example.yaml)

## Entwicklung

Voraussetzungen: Python ≥ 3.12 und [uv](https://docs.astral.sh/uv/). Entscheidungen: [ADR-0001](docs/adr/0001-tech-stack-and-llm.de.md).

```bash
uv sync                                           # installieren
uv run pytest                                     # Tests
uv run agent-pm validate .agent-pm/team.yaml      # Team-Datei prüfen
uv run agent-pm schema > schemas/team.schema.json # JSON-Schema exportieren
uv run agent-pm mcp                               # MCP-Tracker-Server (stdio, Demodaten)
uv run agent-pm deps  --demo                      # Abhängigkeitsrisiken & Zyklen
uv run agent-pm brief --demo --person sam         # freundliches Morgen-Briefing
uv run agent-pm eval  --model qwen3.5             # lokale Modelle vergleichen (--suite knowledge)
uv run agent-pm run   --demo --dry-run            # der ganze Agent, zeigt an statt zu senden
uv run agent-pm onboarding --demo --person sam    # freundliche Vorstellung: was der Agent mit Daten macht
```

**Lokales LLM (Standard):** Betreibe einen beliebigen OpenAI-kompatiblen Server, z. B. [Ollama](https://ollama.com), und setze `llm.model` / `llm.base_url` in `team.yaml`. Live-Test: `AGENT_PM_LIVE_LLM=<Modell> uv run pytest tests/test_llm.py`.

### Geheimnisse

`team.yaml` und die `llm:`-Einstellungen darin werden versioniert und wie Code reviewt. Alles Geheime kommt aus der Umgebung (oder aus Deinem Secret-Manager, als Umgebungsvariablen eingespielt):

| Variable | Wofür |
|----------|-------|
| `GITHUB_TOKEN` / `AGENT_PM_GITHUB_TOKEN` | GitHub-Adapter |
| `OPENPROJECT_API_KEY` | OpenProject-Adapter |
| `AGENT_PM_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FROM` | Versand der E-Mail-Briefings |
| `AGENT_PM_LLM_API_KEY` | Nur wenn Dein Modellserver einen Schlüssel verlangt |
| `AGENT_PM_SIGNING_KEY` | Signieren von Freigabe-Links |
| `AGENT_PM_GITHUB_WEBHOOK_SECRET` | Prüfung von GitHub-Webhooks |
| `AGENT_PM_IMAP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FOLDER` | Lesen von Antworten im Postfach des Agenten |
| `AGENT_PM_WHATSAPP_*`, `AGENT_PM_SIP_*` | WhatsApp und Sprache (Phase 3, geplant) |

### Module

| Modul | Zweck |
|-------|-------|
| `agentic_pm.config` | Schema & Validierung für `team.yaml` |
| `agentic_pm.adapters` | `TrackerAdapter`-Protokoll, GitHub & OpenProject (nur lesend), In-Memory-Tracker |
| `agentic_pm.engine` | Abhängigkeitsgraph-Analyse: Risiken, Was-wäre-wenn, Zyklen |
| `agentic_pm.briefs` | Morgen-Briefings (DE/EN), abgesicherte LLM-Zusammenfassung, SMTP |
| `agentic_pm.evals` | Evaluationsfälle & Runner für lokale Modelle |
| `agentic_pm.audit` | Berechtigungsstufen & Audit-Fußzeile |
| `agentic_pm.ingress` | Webhook-Filter: ignoriert eigene Änderungen des Agenten, entfernt doppelte Zustellungen und Event-Stürme |
| `agentic_pm.actions` · `approvals` · `web` | Berechtigungs- & Audit-Wächter, signierte Freigabe-Tokens, Steuerungsoberfläche |
| `agentic_pm.email_routing` · `inbox` · `inbound` | Ticket-Zuordnung für E-Mail, IMAP-Postfach, Antwortverarbeitung, How-to-Schleife |
| `agentic_pm.knowledge` | Wissensextraktion: Antworten → How-tos in der Ticketsprache |
| `agentic_pm.cadence` · `runtime` | Arbeitstakt, Scheduler, `agent-pm run` |
| `agentic_pm.engine.capacity` | Terminkollisionen (aufgabenbezogen) |
| `agentic_pm.mcp_server` | MCP-Werkzeuge über jedem Adapter, mit Stufenprüfung |
| `agentic_pm.llm` | Anbieterunabhängige LLM-Schnittstelle, lokaler OpenAI-kompatibler Anbieter |

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
  getting-started.md  Tracker verbinden, Briefings, lokales Modell
  trackers.md         Übersicht über 25 Tracker (generiert)
  pm-coverage.md      die komplette PM-Rolle vs. was der Agent tut
  running.md          den Agenten betreiben: Schreiben, Freigaben, E-Mail, Takt
  people-data.md      was der Agent mit Daten über Menschen macht
  adr/                Architekturentscheidungen (ADRs)
  de/                 deutsche Fassungen aller Dokumente
```

## Mitwirken

Siehe [CONTRIBUTING.de.md](CONTRIBUTING.de.md). Designdiskussionen finden in GitHub Issues statt. Jede Roadmap-Phase hat einen Meilenstein.

**Welche Tracker?** Die [Übersicht](docs/de/trackers.md) zeigt Jira, Azure DevOps, Asana, monday.com, Smartsheet, Notion, Trello, Planner, Linear, GitLab, Redmine und mehr, dazu das [Adapter-Epic #18](https://github.com/Wieshof/agentic-pm/issues/18).

**Referenz-Adapter: GitHub Issues** ([`adapters/github.py`](src/agentic_pm/adapters/github.py)), in Phase 1 zusammen mit OpenProject gebaut. Neue Tracker-Adapter (Plane, Taiga, GitLab, Jira, Linear, siehe #18) implementieren dasselbe `TrackerAdapter`-Protokoll und bestehen die gemeinsame Vertrags-Testsuite (`agentic_pm.testing`). Kopiere am besten den GitHub-Adapter samt Tests. Die Tests nutzen aufgezeichnete API-Antworten, Du brauchst also kein Konto.

## Lizenz

[Apache License 2.0](LICENSE)
