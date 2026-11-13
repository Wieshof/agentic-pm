# Den Agenten betreiben (Phase 2)

🇬🇧 [English](../running.md) · 🇩🇪 Deutsch

Ab Phase 2 kann agentic-pm in Deinen Tracker **schreiben** (hinter den Berechtigungsstufen), **Antworten per E-Mail empfangen**, beim Schließen einer Aufgabe um ein How-to bitten und den **Arbeitstakt** Deines Teams ausführen. Alles läuft in einem Prozess:

```bash
uv run agent-pm run                     # Scheduler + Freigabe-Web + Webhooks + Postfach
uv run agent-pm run --demo --dry-run    # ausprobieren: zeigt Nachrichten an, statt sie zu senden
uv run agent-pm run --once weekly_digest   # einen Job sofort, z. B. per cron
```

## 1. Einrichten

```yaml
project:
  tracker: github
  repo: deine-org/dein-repo
  leads: [alex]
  allow_writes: true                    # Opt-in; ohne liest der Agent nur
  agent_accounts: [agent-pm-bot]        # Login, mit dem er schreibt (Schutz vor Selbstauslösung)
  agent_email: pm@deine-org.de          # Antworten gehen an pm+142@deine-org.de
  control_plane_url: https://pm.deine-org.de   # Freigabe-Links und Webhooks
  ticket_language: en

cadence:
  morning_triage: "08:30"               # werktags; persönliche Briefings (außer brief.when ist gesetzt)
  end_of_day: "17:30"                   # Teamleitungen, nur wenn etwas ansteht
  weekly_digest: "Fri 15:00"            # Teamleitungen
  monthly_health_check: last_friday     # kommt mit #54
```

| Angabe | Bedeutung |
|--------|-----------|
| `"08:30"` | jeden Werktag (keine Briefings am Wochenende) |
| `"daily 08:30"` | jeden Tag |
| `"Fri 15:00"` | wöchentlich |
| `"last_friday 16:00"`, `"first_monday"` | monatlich (Standardzeit 09:00) |

**Geheimnisse** (nur als Umgebungsvariablen): `GITHUB_TOKEN`, `AGENT_PM_SIGNING_KEY` (eine beliebige lange Zufallszeichenkette, für Freigabe-Links), `AGENT_PM_GITHUB_WEBHOOK_SECRET`, `AGENT_PM_SMTP_*` (Versand) und `AGENT_PM_IMAP_*` (Empfang: `HOST`, `PORT`, `USER`, `PASSWORD`, `FOLDER`).

**GitHub-Webhook:** Richte in den Repository-Einstellungen einen Webhook auf `https://pm.deine-org.de/webhooks/github` ein, Content-Type JSON, mit demselben Secret. Abonniere *Issues* und *Issue comments*.

## 2. Was passiert

**How-to-Schleife (#10).** Wenn jemand ein Issue schließt, bekommt die Person eine kurze, freundliche Mail in ihrer Sprache: „Stark, dass #12 erledigt ist! Wie hast Du es gelöst?“ Sie antwortet mit ein, zwei Sätzen, in jeder Sprache. Das lokale Modell macht daraus ein How-to im Ticket, geschrieben in `ticket_language`:

```markdown
### How it was solved
- **Problem:** Auth requests time out under load
- **Root cause:** Redis connection pool exhausted
- **Fix:** Increased the Redis pool size to 50
_Explained by Sam via email (in German), structured by agent-pm._
```

Ob der Agent schon gefragt hat, liest er aus seinem eigenen protokollierten Kommentar im Ticket. Er fragt also nie doppelt.

**Andere Antworten (#9).** Antworten werden über die Adresse `pm+<id>@` oder die `Message-ID` der Aufgabe zugeordnet, und zitierter Verlauf und Signaturen werden entfernt. Dann:

| Die Nachricht ist … | Der Agent … |
|---------------------|-------------|
| eine Lösung | schreibt ein How-to ins Ticket |
| ein Status-Update oder eine Frage | ergänzt sie als Notiz im Ticket |
| neuer Umfang („könntet ihr noch …“) | sagt der Teamleitung Bescheid und legt **keine** Arbeit an (formale Änderungsanträge: #50) |
| ein Dank oder Gruß | tut nichts |
| von jemandem, der nicht in der Team-Datei steht | ignoriert sie |

Jeder Fall bekommt eine kurze Antwort „Danke, ich habe es ergänzt“.

**Freigaben (#11).** Änderungen, die ein OK brauchen, gehen per Mail mit einem Link zur Steuerungsoberfläche an:
- **die verantwortliche Person:** interne Termine oder Status,
- **eine Teamleitung:** Kundentermine, neue Verantwortliche.

Das Öffnen des Links *zeigt* die Änderung nur an, Mail-Scanner können also nichts freigeben. Ein Klick auf ✅ übernimmt sie, aber nur, wenn sich die Aufgabe seit dem Vorschlag nicht geändert hat. Eine kurze Notiz „wartet auf OK“ im Ticket hält alle auf dem Laufenden.

**Arbeitstakt (#45) und Kollisionen (#46).**
- Briefings zeigen jetzt Terminkollisionen, z. B. „#12 und #31 sind bis Dienstag fällig und brauchen etwa 3 Tage, es bleiben aber nur 2 Arbeitstage. Vielleicht #31 verschieben oder übergeben?“
- Teamleitungen bekommen die Abendnotiz (nur wenn nötig) und den Wochenrückblick.

**Onboarding (#47).** `uv run agent-pm onboarding --all --send` schickt allen eine freundliche Vorstellung in ihrer Sprache, die erklärt, was der Agent mit ihren Daten macht ([Details](people-data.md)).

## 3. Sicherheitsmodell

- **Schreiben ist Opt-in** (`allow_writes`) und läuft immer über die Berechtigungsstufen. Jeder Schreibvorgang trägt die Audit-Fußzeile.
- **Freigabe-Links** sind signiert, laufen nach 72 h ab, gelten für genau eine Person und prüfen die Aufgabe live nach. Wer den Link hat, kann entscheiden, also behandle Freigabe-Mails wie andere vertrauliche Mails.
- **E-Mails lassen sich fälschen.** Deshalb führt eine E-Mail immer nur zu Schreibvorgängen mit geringem Risiko (Kommentaren). Sie gibt nie etwas frei, weist nie neu zu und verschiebt nie Termine.
- **Webhooks** brauchen eine gültige Signatur und laufen durch den [Webhook-Filter](data-model.md#webhook-eingang-keine-schleifen-keine-stürme), damit der Agent nie auf seine eigenen Änderungen reagiert.

## 4. Qualität des lokalen Modells

Evaluation `uv run agent-pm eval --suite knowledge --model <Modell>`: 8 Fälle auf Deutsch und Englisch, mit Lösungen, Status-Updates, Fragen, Wünschen nach neuem Umfang und Dank. Eine deutsche Nachricht muss bei `ticket_language: en` ein englisches How-to ergeben.

| Modell | Ergebnis (12.11.2026, `reasoning_effort: none`) |
|--------|------------------------------------------------|
| qwen3.5 | 8/8 |
| gemma4 | 8/8 |

Besteht das Modell die Prüfung nicht (erfundene Ticketnummern, fehlende Lösung, falsche Sprache), wird die Nachricht als normale Notiz ergänzt. Es geht nichts verloren.
