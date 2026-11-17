# agentic-pm

🇬🇧 [English](README.md) · 🇩🇪 Deutsch

**Ein ruhiger Projekt-Assistent, der auf Deinen bestehenden Tools aufsetzt und seine KI auf Deiner eigenen Hardware laufen lässt.**

agentic-pm liest Deine Aufgabenliste oder Deinen Tracker, bemerkt, was ins Rutschen kommt, und spricht mit jeder Person so, wie sie es mag: eine kurze Mail am Morgen, eine Chat-Nachricht, ein schnelles „ja“, um eine Änderung zu bestätigen. Eine eigene Datenbank hat er nicht. Deine Tabelle oder Dein Tracker bleibt der eine Ort, an dem die Wahrheit steht.

🌐 [Website](https://wieshof.github.io/agentic-pm/) · 🚀 [Erste Schritte](docs/de/getting-started.md) · 📊 [Mit einer Tabelle starten](docs/de/spreadsheets.md) · 🗺️ [Roadmap](docs/de/roadmap.md)

---

## Warum es das gibt

Projekte scheitern selten an fehlenden Tools. Sie kommen ins Rutschen, weil niemand Zeit hat, Tickets aktuell zu halten, Statusmeldungen per Mail hinterherzulaufen oder zu bemerken, dass der Launch am Freitag still und leise an etwas hängt, an dem gerade niemand arbeitet. Gleichzeitig wollen viele Teams und Selbstständige ihre internen Pläne nicht an eine Cloud-KI schicken.

agentic-pm nimmt Dir diesen Kleinkram ab, und sein Sprachmodell läuft auf Deinem Rechner (mit [Ollama](https://ollama.com) oder jedem OpenAI-kompatiblen Server).

## Was er für Dich tut

- **Warnt Dich, bevor ein Termin platzt.** Er folgt den Abhängigkeiten zwischen Aufgaben und sagt der richtigen Person früh Bescheid: *„#14 Release notes könnte sich um 1 Tag verschieben, weil #13 Login UI weiter oben in der Kette hängt.“*
- **Holt alle dort ab, wo sie sind.** Ein Morgen-Briefing per Mail oder ein kurzes Briefing in Matrix oder Signal. Antworten gehen in der eigenen Sprache, die Tickets bleiben in der Sprache des Teams.
- **Stellt eine freundliche Frage pro fehlender Angabe.** „#16 hat keinen Termin. Bis wann soll es fertig sein?“ Du antwortest „Freitag“, bestätigst mit „ja“, und das Ticket ist aktualisiert.
- **Macht aus „so habe ich es gelöst“ ein How-to** im Ticket, aus einer Mail-Antwort oder einer Sprachnachricht (lokal transkribiert).
- **Merkt, wenn etwas nicht zusammenpasst.** Jemand schreibt „#12 ist erledigt“, aber #12 ist noch offen. Dann fragt er einmal nach, statt zu raten.
- **Fasst sanft nach.** Dringendes kommt täglich, alles andere wöchentlich und gebündelt. Klappt ein Kanal nicht, versucht er den nächsten, und er führt nie Buch über Menschen.

Ein echtes Morgen-Briefing (aus der eingebauten Demo):

```
Guten Morgen, Sam!

⏰ Überfällig
  • #11 Redis pool sizing (2 Tage überfällig)

🤝 Andere warten auf Dich
  • Kim braucht #12 Fix auth timeout, um mit #13 Login UI zu starten

📅 In den nächsten Tagen fällig
  • #12 Fix auth timeout (fällig 2026-11-18)

Du hast 3 offene Aufgaben. Antworte einfach auf diese Mail, wenn etwas nicht stimmt. 💬
```

## Für wen

| Du bist… | Fang hier an |
|----------|--------------|
| Selbstständig oder ein kleines Studio und planst in Excel oder einer CSV | [Tabellen-Modus](docs/de/spreadsheets.md): keine Konten, kein Server nötig |
| Ein Team auf GitHub, OpenProject oder Gitea / Forgejo | [Erste Schritte](docs/de/getting-started.md) |
| Jemand, der lieber gar keinen Tracker öffnet | Lass Dich vom Team mit E-Mail, Matrix oder Signal eintragen ([Chat](docs/de/chat.md)) |

Nicht so technisch? Schick die [Erste-Schritte-Anleitung](docs/de/getting-started.md) an die Person, die sich bei Euch um die IT kümmert. Eingerichtet wird das mit einer kleinen Konfigurationsdatei.

## Datenschutz und Sorgfalt eingebaut

- **Die KI läuft lokal.** Nachrichten und Aufgabentexte gehen an ein Modell auf Deiner eigenen Hardware, nie an eine Cloud-KI, und sie werden nie zum Training verwendet.
- **Keine zweite Datenbank.** Aufgaben, Termine und Abhängigkeiten werden live aus Deinem Tool gelesen. Notizen und How-tos landen dort, wo alle sie sehen.
- **Du behältst die Kontrolle.** Der Agent liest nur, bis Du das Schreiben einschaltest. Kommentare und Labels laufen automatisch. Termin oder Status Deiner eigenen Aufgabe ändert er nur mit Deinem „ja“, Kundentermine oder neue Zuständige nur mit der signierten Freigabe einer Teamleitung.
- **Keine Überwachung.** Keine Bewertungen, Ranglisten oder Messung von Antwortzeiten über Menschen, kein Erraten von Stimmungen ([ADR-0004](docs/adr/0004-people-data-boundaries.de.md), [was er mit Personendaten macht](docs/de/people-data.md)).
- **Geheimnisse bleiben aus dem Repo.** Tokens und Passwörter stehen nur in Umgebungsvariablen, und `agent-pm validate` weist alles zurück, was danach aussieht.

## Stand

| | Was | |
|-|-----|-|
| ✅ | **Nur-Lese-Einblick:** Abhängigkeitsrisiken, Terminkollisionen, Fragen zur Datenqualität, Morgen-Briefings | Phase 1 |
| ✅ | **Zurückschreiben:** Kommentare, How-tos, signierte Freigaben, Mail-Antworten, täglicher und wöchentlicher Takt | Phase 2 |
| ✅ | **Chat über Matrix und Signal:** Sprachnachrichten, Triangulation, adaptives Nachfassen | Phase 3 |
| ⏳ | WhatsApp, telefonische Check-ins und gesprochene Briefings | Phase 3 |
| 🗓️ | Planung und Steuerung, Scrum-Artefakte, Portfolio und Finanzen | Phasen 4–7 |

Alles mit ✅ ist gebaut und getestet (mehr als 300 automatische Tests). Im echten Betrieb hat es noch kein Pilotteam eingesetzt. Wenn Du das erste sein möchtest, [eröffne gern ein Issue](https://github.com/Wieshof/agentic-pm/issues). Der ganze Plan: [Roadmap](docs/de/roadmap.md).

**Tracker:** Excel/CSV, GitHub Issues, OpenProject und Gitea / Forgejo funktionieren heute. Jira, GitLab, Linear, Plane, Asana, Azure DevOps und 15 weitere sind erfasst und geplant ([Übersicht](docs/de/trackers.md)).

## In zwei Minuten ausprobieren

Du brauchst Python 3.12+ und [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Wieshof/agentic-pm && cd agentic-pm
uv sync
uv run agent-pm brief --demo --person sam        # das Briefing oben, aus Demo-Daten
uv run agent-pm run --demo --dry-run --once briefs   # der ganze Agent, druckt statt zu senden
```

Dann beschreib Dein eigenes Team in `.agent-pm/team.yaml`. Die Datei liegt in Deinem Repository, deshalb stehen darin nie Geheimnisse:

```yaml
project:
  tracker: github                # spreadsheet | github | openproject | gitea
  repo: deine-org/dein-repo
  leads: [alex]
  ticket_language: en            # Tickets bleiben auf Englisch ...
people:
  alex:
    role: team-lead
    archetype: reader            # reader | writer | talker | listener
    language: de                 # ... während Alex mit dem Agenten Deutsch spricht
    channels: {email: alex@example.com}
    brief: {when: "08:00", format: email}
```

```bash
uv run agent-pm validate                  # prüft die Datei, auch auf versehentlich eingefügte Geheimnisse
uv run agent-pm brief --person alex       # Dein echtes Briefing (braucht GITHUB_TOKEN)
```

Weiter geht's: [Erste Schritte](docs/de/getting-started.md) · [Den Agenten betreiben](docs/de/running.md) · [vollständige Beispiel-Konfiguration](.agent-pm/team.example.yaml)

---

## So funktioniert es

```
   E-Mail ─┐                                            ┌─ Excel / CSV
   Matrix ─┤   ┌───────────────┐   ┌────────────────┐   ├─ GitHub Issues
   Signal ─┼──►│ Kanäle        │──►│ Auswertung     │──►├─ OpenProject
      Web ─┤   │ (wer, wo,     │   │ (Abhängig-     │   ├─ Gitea / Forgejo
    (MCP) ─┘   │  welche Aufg.)│   │ keiten, Lücken)│   └─ 21 weitere geplant
               └───────────────┘   └────────────────┘
                      ▲                     │
                      └── lokales Modell ───┘
```

| Schleife | Was sie tut |
|----------|-------------|
| **Abhängigkeitsrisiken** | Verschiebt sich eine Aufgabe, folgt er dem Abhängigkeitsgraphen, warnt die Betroffenen weiter hinten und schlägt neue Termine vor, bevor jemand umsonst wartet. |
| **Triangulation** | Eine Status-Aussage („erledigt“, „hänge fest“), die dem Tracker widerspricht, wird zu einer Frage an die Person, die es klären kann. |
| **How-to-Doku** | Antworten und Sprachnachrichten zu einer Lösung werden zu einem strukturierten How-to im Ticket, in der Sprache des Tickets. |
| **Adaptives Nachfassen** | Zählt unbeantwortete Erinnerungen pro Frage, nie pro Person. Dringendes kommt täglich, der Rest wöchentlich und gebündelt, und klappt ein Kanal nicht, versucht er den nächsten. |
| **Briefings & Takt** | Morgen-Briefings, eine Notiz zum Feierabend für Teamleitungen und ein Wochenrückblick, jeweils zur Zeit, die sich die Person ausgesucht hat. |

**Keine Datenbank.** Aufgaben liegen im Tracker, Team-Einstellungen in `.agent-pm/team.yaml`. Welche Antwort zu welcher Aufgabe gehört, reist mit der Nachricht selbst: als Plus-Adresse in der Mail (`pm+142@…`) oder als kurzes signiertes Tag im Chat. Details: [Architektur](docs/de/architecture.md) · [Datenmodell](docs/de/data-model.md) · [Abläufe](docs/de/workflows.md) · [wie das zur ganzen PM-Rolle passt](docs/de/pm-coverage.md)

---

## Für Entwicklerinnen und Entwickler

```bash
uv sync                                           # installieren
uv run pytest                                     # Tests
uv run agent-pm validate .agent-pm/team.yaml      # eine Team-Datei prüfen
uv run agent-pm deps  --demo                      # Abhängigkeitsrisiken, Lücken und Zyklen
uv run agent-pm brief --demo --person sam         # Morgen-Briefing
uv run agent-pm run   --demo --dry-run            # der ganze Agent, druckt statt zu senden
uv run agent-pm eval  --model qwen3.5             # lokale Modelle vergleichen (--suite knowledge)
uv run agent-pm mcp                               # MCP-Tracker-Server (stdio, Demo-Daten)
uv run agent-pm trackers                          # welche Tracker gebaut / geplant sind
```

**Lokales Modell:** Betreib einen beliebigen OpenAI-kompatiblen Server, z. B. [Ollama](https://ollama.com), und setz `llm.model` / `llm.base_url` in `team.yaml` ([ADR-0001](docs/adr/0001-tech-stack-and-llm.de.md)). Live-Test: `AGENT_PM_LIVE_LLM=<Modell> uv run pytest tests/test_llm.py`.

### Geheimnisse

Alles Geheime kommt aus Umgebungsvariablen (oder Deinem Secret-Manager), nie aus `team.yaml`:

| Variable | Wofür |
|----------|-------|
| `GITHUB_TOKEN` / `AGENT_PM_GITHUB_TOKEN` | GitHub |
| `OPENPROJECT_API_KEY` | OpenProject |
| `AGENT_PM_GITEA_TOKEN` | Gitea / Forgejo |
| `AGENT_PM_SIGNING_KEY` | Freigabe-Links, Bestätigungen im Chat und die Audit-Fußzeile (mindestens 32 zufällige Zeichen) |
| `AGENT_PM_GITHUB_WEBHOOK_SECRET` · `AGENT_PM_GITEA_WEBHOOK_SECRET` | Webhooks prüfen |
| `AGENT_PM_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FROM` | Mails senden |
| `AGENT_PM_IMAP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FOLDER` | Antworten im Postfach des Agenten lesen |
| `AGENT_PM_MATRIX_HOMESERVER`, `_USER`, `_TOKEN` | Chat über Matrix |
| `AGENT_PM_SIGNAL_API_URL`, `_NUMBER` | Chat über Signal (signal-cli-rest-api) |
| `AGENT_PM_LLM_API_KEY` | Nur, wenn Dein Modell-Server einen Schlüssel verlangt |

### Code-Übersicht

| Modul | Zweck |
|-------|-------|
| `agentic_pm.config` | Schema und Prüfung von `team.yaml` |
| `agentic_pm.adapters` | `TrackerAdapter`-Protokoll; Tabelle, GitHub, OpenProject, Gitea; Tracker-Katalog; Vertragstests |
| `agentic_pm.engine` | Abhängigkeiten, Kapazität, Vollständigkeit, Nachfassen, Triangulation |
| `agentic_pm.briefs` | Morgen-Briefing, Feierabend-Notiz, Wochenrückblick, abgesicherte LLM-Zusammenfassung |
| `agentic_pm.actions` · `approvals` · `audit` | Berechtigungsstufen, signierte Freigaben, Audit-Fußzeile |
| `agentic_pm.email_routing` · `inbox` · `inbound` | Mail-Zuordnung, IMAP-Postfach, Antwortverarbeitung, How-to-Schleife |
| `agentic_pm.chat` · `speech` | Matrix und Signal, Antwort-Tags, lokale Spracherkennung |
| `agentic_pm.web` · `ingress` | Freigabeseiten, Webhooks, Entdoppelung |
| `agentic_pm.knowledge` · `llm` · `evals` | How-to-Extraktion, Modell-Schnittstelle, Modell-Evaluierung |
| `agentic_pm.cadence` · `runtime` · `cli` | Zeitplan, `agent-pm run`, Kommandozeile |
| `agentic_pm.mcp_server` | MCP-Werkzeuge für jeden Adapter, mit denselben Berechtigungsstufen |

### Aufbau des Repositorys

```
.agent-pm/        Beispiel-Konfiguration für ein Team
docs/             Anleitungen (deutsche Fassungen in docs/de/), Website (index.html)
  adr/            Architekturentscheidungen
examples/solo/    ein Ein-Personen-Studio, das in einer CSV plant
schemas/          JSON-Schema für team.yaml
src/agentic_pm/   der Agent
tests/            automatische Tests
```

---

## Mitmachen

Ideen, Fragen und Pull Requests sind willkommen. Siehe [CONTRIBUTING.de.md](CONTRIBUTING.de.md). Designfragen besprechen wir in [GitHub Issues](https://github.com/Wieshof/agentic-pm/issues), und jede Roadmap-Phase hat einen Meilenstein.

**Neue Tracker-Adapter** setzen das `TrackerAdapter`-Protokoll um und bestehen die gemeinsamen Vertragstests (`agentic_pm.testing`). Am einfachsten kopierst Du den GitHub-Adapter samt Tests. Die Tests nutzen aufgezeichnete API-Antworten, Du brauchst also kein Konto ([Adapter-Epic #18](https://github.com/Wieshof/agentic-pm/issues/18)).

**Ein Sicherheitsproblem gefunden?** Melde es bitte vertraulich, siehe [SECURITY.de.md](SECURITY.de.md).

## Lizenz

[Apache License 2.0](LICENSE)
