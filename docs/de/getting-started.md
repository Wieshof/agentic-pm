# Erste Schritte (Phase 1: Einblick, nur lesend)

🇬🇧 [English](../getting-started.md) · 🇩🇪 Deutsch

In Phase 1 **liest** agentic-pm Deinen Tracker, findet Abhängigkeitsrisiken und schickt jedem „Leser“ eine freundliche Morgen-Mail. In den Tracker schreibt es nichts.

## 1. Mit Demodaten ausprobieren (ohne Konten)

```bash
uv sync
uv run agent-pm deps  --demo                 # Abhängigkeitsrisiken und Zyklen
uv run agent-pm brief --demo --person alex   # englisches Briefing für eine Teamleitung
uv run agent-pm brief --demo --person sam    # deutsches Briefing („Du“)
```

Die Demodaten liegen relativ zu heute, Du siehst also immer etwas: eine überfällige Aufgabe, eine Verzögerung, die sich durch eine Kette zieht, und eine zirkuläre Abhängigkeit.

## 2. Deinen Tracker verbinden

Kopiere `.agent-pm/team.example.yaml` nach `.agent-pm/team.yaml` und passe sie an. Prüfen kannst Du sie mit `uv run agent-pm validate`. Geheimnisse kommen ausschließlich aus Umgebungsvariablen.

### GitHub Issues

```yaml
project: {tracker: github, repo: deine-org/dein-repo, leads: [alex]}
```

Setze `GITHUB_TOKEN` (oder `AGENT_PM_GITHUB_TOKEN`) auf ein Token, das Issues lesen darf. Weicht der GitHub-Login einer Person von ihrem Handle ab, setze `tracker_login`.

GitHub kennt keine Fälligkeitstermine und Schätzungen, deshalb liest agentic-pm diese Konventionen:

| Was | So schreibst Du es |
|-----|--------------------|
| Fälligkeit | Eine Zeile `Due: 2026-12-01` (oder `Fällig: …`) im Issue-Text, sonst das Fälligkeitsdatum des Meilensteins |
| Schätzung | Eine Zeile `Estimate: 4h` / `2d` / `1w` (oder `Schätzung: …`) bzw. ein Label `estimate:4h` (1d = 8h) |
| Abhängigkeiten | GitHubs native „blocked by / blocking“ und Sub-Issues, oder Zeilen wie `Blocked by #12` / `Abhängig von #12` / `Blocks #15` |
| Status | Geschlossen → erledigt. Offen + Label `status:in-progress`, `status:in-review` oder `status:blocked` |
| Kundentermin | Label `client-facing` (Terminänderungen brauchen später die Freigabe einer Teamleitung) |

### OpenProject

```yaml
project: {tracker: openproject, repo: mein-projekt, base_url: https://op.example.com, leads: [alex]}
```

Setze `OPENPROJECT_API_KEY`. Fälligkeit, Schätzung, Status, Zuständige (Anzeigename) und Beziehungen (blockiert / Vorgänger / Nachfolger / verwandt, über- und untergeordnet) werden direkt gelesen. Verwende den Anzeigenamen als `tracker_login`.

> Der OpenProject-Adapter ist mit aufgezeichneten API-Antworten getestet, aber noch nicht mit einer echten Instanz. Melde Dich gern, wenn Dir etwas komisch vorkommt.

## 3. So funktioniert die Risikoprüfung

Die Analyse ist einfacher, nachvollziehbarer Code und kein Raten durch ein Modell:

- Eine Aufgabe braucht `Schätzung ÷ 8h` Tage (mindestens 1). Ohne Schätzung zählt sie als 1 Tag.
- Eine Aufgabe kann am Tag nach dem Ende all ihrer offenen Blocker starten. Ein überfälliger Blocker wird frühestens heute fertig.
- Rutscht das Ende dadurch über die Fälligkeit, ist die Aufgabe **gefährdet**. Die Analyse nennt den Grund (Blocker überfällig / Blocker zu spät fällig / Verzögerung weiter oben in der Kette) und schlägt ein neues Datum vor.
- Vorerst zählen nur Kalendertage. Wochenenden und Feiertage werden noch nicht berücksichtigt.

## 4. Morgen-Briefings

```bash
uv run agent-pm brief --person alex                    # im Terminal anzeigen
uv run agent-pm brief --all --format eml --out briefs/ # eine .eml pro Leser
uv run agent-pm brief --all --send                     # per SMTP verschicken
```

Jede Aufgabe erscheint genau einmal, in ihrem wichtigsten Abschnitt: überfällig, andere warten auf Dich, gefährdet, bald fällig, wartet auf etwas. Teamleitungen sehen zusätzlich Team-Risiken und zirkuläre Abhängigkeiten. Mit `language: de` kommt das Briefing auf Deutsch, mit „Du“.

**Versand** nutzt `AGENT_PM_SMTP_HOST`, `AGENT_PM_SMTP_PORT` (587), `AGENT_PM_SMTP_USER`, `AGENT_PM_SMTP_PASSWORD` und `AGENT_PM_SMTP_FROM`.

**Zeitplan:** Solange der Agent noch keinen eigenen Scheduler hat, nimm cron, zum Beispiel werktags um 07:30:

```cron
30 7 * * 1-5  cd /srv/agentic-pm && uv run agent-pm brief --all --send --llm
```

## 5. Optional: eine kurze Zusammenfassung von Deinem lokalen Modell

Mit `--llm` ergänzt ein lokales Modell (siehe `llm:` in `team.yaml`) 1–3 freundliche Einleitungssätze. Sicherheitsnetze:

- Das Modell sieht nur die berechneten Fakten.
- Deutsches „du/dich/dein“ wird automatisch großgeschrieben. Ein förmliches „Sie“ wird abgelehnt.
- Zusammenfassungen, die unbekannte Aufgabennummern nennen, verirrte `#`-Tags enthalten oder zu lang sind, werden **verworfen**, und das Briefing geht ohne sie raus.
- An ruhigen Tagen wird das Modell gar nicht gefragt (Modelle erfinden sonst gern Aufgaben).

Für Denk-Modelle wie qwen3.x setze `reasoning_effort: none`.

### Modelle vergleichen: die Evaluation

```bash
uv run agent-pm eval --model qwen3.5
uv run agent-pm eval --model gemma4
```

Es gibt 8 Fälle (Deutsch und Englisch, volle und ruhige Tage), alle mit deterministischen Prüfungen und ohne LLM als Richter. Ergebnisse vom 12.11.2026 (je zwei Läufe, `reasoning_effort: none`):

| Modell | Lauf 1 | Lauf 2 | Typischer Fehler (vom Guard abgefangen) |
|--------|--------|--------|-----------------------------------------|
| qwen3.5 | 8/8 | 6/8 | Lässt eine wichtige Aufgabe weg oder schreibt `#{15}` |
| gemma4 | 7/8 | 8/8 | Lässt eine wichtige Aufgabe weg |

Ergänze eigene Fälle in `src/agentic_pm/evals/brief_summary_cases.yaml`, bevor Du das Modell wechselst.
