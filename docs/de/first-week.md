# Deine erste Woche mit agentic-pm

🇬🇧 [English](../first-week.md) · 🇩🇪 Deutsch

Meist haben drei Menschen mit agentic-pm zu tun, deshalb hat diese Anleitung drei Wege. Lies Deinen, die anderen kannst Du überspringen.

| Du bist… | Dein Weg | Zeit |
|----------|----------|------|
| Inhaberin, Inhaber oder Projektleitung und willst es einsetzen | [1. Entscheiden](#1-für-die-leitung-entscheiden) | etwa 15 Minuten, nichts Technisches |
| Die Person, die sich um Eure IT kümmert | [2. Einrichten](#2-für-die-it-einrichten) | etwa eine Stunde (geschätzt: gemessen hat es noch niemand) |
| Jemand im Team, der Briefings bekommen wird | [3. Nutzen](#3-für-das-team-nutzen) | 5 Minuten Lesen |

Wo es steht: Alles hier ist gebaut und getestet, aber im echten Betrieb hat es noch kein Pilotteam eingesetzt. In der ersten Woche liest es nur, Ausprobieren ist also sicher.

## 1. Für die Leitung: entscheiden

1. **Wähl ein Projekt für den Anfang.** Eines, nicht alle. Aus einem kleinen Start lernst Du am meisten.
2. **Sag, wo seine Aufgaben liegen.** In einer Tabelle (Excel oder CSV) oder in einem Tracker: GitHub, OpenProject oder Gitea / Forgejo. Alle funktionieren heute. Auch mehrere gleichzeitig, z. B. einer pro Kunde ([mehrere Tracker](sources.md)).
3. **Leg fest, wer ein Morgen-Briefing bekommt, und wann.** Fang mit Dir selbst an, um 8:00, in Deiner Sprache. Andere kommen später dazu, jede Person mit eigener Zeit und Sprache.
4. **Leg fest, wo es läuft.** Auf jedem Rechner, der zur Briefing-Zeit eingeschaltet ist. Zum Ausprobieren reicht Dein Laptop; für den Alltag ein kleiner Rechner, der an bleibt, mit mindestens 16 GB Arbeitsspeicher, wenn darauf das Sprachmodell läuft.
5. **Gib es an Deine IT weiter.** Schick ihr diese Seite und diese vier Antworten:
   - welche Tabelle oder welcher Tracker (und welches Projekt darin)
   - ein E-Mail-Konto, von dem der Assistent schreiben darf, z. B. `pm@deine-firma.de`
   - Deine Personenliste: Name, E-Mail, Sprache, Briefing-Zeit
   - den Rechner, auf dem es läuft
6. **In der ersten Woche liest es nur.** Der Assistent schreibt nichts in Deine Projekte: keine Kommentare, keine Status- oder Terminänderungen. Die Briefings schickt er trotzdem, das ist seine Aufgabe. Prüf jeden Morgen, ob sie stimmen.
7. **Nach einer stimmigen Woche entscheidest Du übers Schreiben.** Zuerst Kommentare und How-tos, dann Termin- und Statusänderungen, die immer ein „ja“ der zuständigen Person brauchen (bei Kundenterminen das einer Teamleitung). Siehe [was er ändern darf](guardrails.md).

**Sag Deinem Team Bescheid, bevor das erste Briefing kommt.** Teil [was der Agent mit Daten über Dich macht](people-data.md). Wo es Datenschutzbeauftragte oder einen Betriebsrat gibt, bezieh sie vorher ein.

## 2. Für die IT: einrichten

Du brauchst ein Terminal, Python 3.12 oder neuer und [uv](https://docs.astral.sh/uv/).

**Schritt 1: installieren und die Demo ausprobieren** (ohne Konten):

```bash
git clone https://github.com/Wieshof/agentic-pm.git
cd agentic-pm
uv sync
uv run agent-pm brief --demo --person sam
uv run agent-pm run --demo --dry-run --once briefs
```

**Schritt 2: ein Nur-Lese-Token für den Tracker.**

| Tracker | Was Du anlegst | Umgebungsvariable |
|---------|----------------|-------------------|
| GitHub | einen Fine-grained Token mit *Issues: read* für das eine Repository | `GITHUB_TOKEN` |
| OpenProject | einen API-Schlüssel einer Person, die das Projekt sehen kann | `OPENPROJECT_API_KEY` |
| Gitea / Forgejo | einen Token mit Lesezugriff auf Issues | `AGENT_PM_GITEA_TOKEN` |
| Tabelle | nichts; die Datei muss auf diesem Rechner nur lesbar sein | keine |

Tokens gehören nur in Umgebungsvariablen, nie in eine Datei im Repository.

**Schritt 3: das Team beschreiben.** Kopier `.agent-pm/team.example.yaml` nach `.agent-pm/team.yaml`, trag den Tracker und die Personen aus der Liste der Leitung ein und prüf es:

```bash
uv run agent-pm validate
uv run agent-pm brief --person <handle>
```

Für eine Tabelle folg stattdessen dem [Tabellen-Modus](spreadsheets.md); das [Solo-Beispiel](../../examples/solo/) kannst Du direkt kopieren.

**Schritt 4 (optional): das lokale Sprachmodell.** Es schreibt eine Zusammenfassung in zwei Sätzen über jedes Briefing. Ohne Modell funktioniert das Briefing genauso, nur ohne diese Zusammenfassung.

```bash
ollama pull gemma4
uv run agent-pm eval --model gemma4
uv run agent-pm brief --person <handle> --llm
```

**Schritt 5: E-Mail.** Setz `AGENT_PM_SMTP_HOST`, `AGENT_PM_SMTP_PORT`, `AGENT_PM_SMTP_USER`, `AGENT_PM_SMTP_PASSWORD` und `AGENT_PM_SMTP_FROM`. Für die erste Woche reicht der Versand.

Antworten kommen später dazu, und sie brauchen ein Postfach mit Plus-Adressen (`pm+142@deine-firma.de` muss bei `pm@deine-firma.de` ankommen). Nicht jeder Mail-Anbieter kann das, prüf es also, bevor Du dem Team Antworten versprichst.

**Schritt 6: dauerhaft laufen lassen.** `uv run agent-pm run` verschickt jedes Briefing zu der Zeit, die die Person gewählt hat. Lass es als Dienst laufen, der mit dem Rechner startet, oder plan nur die Briefings mit cron ein ([Erste Schritte](getting-started.md#4-morgen-briefings)).

**Schritt 7 (ab Woche zwei): Schreiben und Antworten.** Erst, wenn die Leitung zugestimmt hat:

- `allow_writes: true`
- `project.agent_accounts`
- ein zufälliger `AGENT_PM_SIGNING_KEY` mit mindestens 32 Zeichen
- `AGENT_PM_IMAP_*` für Antworten
- optional Webhooks und die Freigabeseiten

Alles steht in [Den Agenten betreiben](running.md).

### Wenn etwas nicht klappt

| Was Du siehst | Bedeutet meistens |
|---------------|-------------------|
| `401` oder `404` von GitHub | Der Token sieht das Repository nicht, oder ihm fehlt *Issues: read*. |
| „model not found“ | Erst `ollama pull <Modell>`; die Meldung zeigt, welche Modelle installiert sind. |
| Das Modell ist sehr langsam oder der Rechner hängt | Das Modell ist zu groß für den Arbeitsspeicher; nimm ein kleineres und lass die Evaluation noch einmal laufen. |
| Kein Briefing angekommen | Der Rechner hat zur Briefing-Zeit geschlafen, oder `agent-pm run` lief nicht. |
| Antworten werden ignoriert | Das Postfach kann keine Plus-Adressen, oder `AGENT_PM_IMAP_*` ist nicht gesetzt. |
| `validate` beschwert sich | Es nennt die genaue Zeile. Uhrzeiten brauchen in YAML Anführungszeichen: `"08:00"`. |

## 3. Für das Team: nutzen

- **Was Du bekommst:** eine kurze Nachricht am Tag, zu der Zeit, die Du gewählt hast. Darin stehen Deine eigenen Aufgaben: was überfällig ist, worauf andere warten, was bald fällig ist. Fehlen Angaben, kommt eine Frage. Hier ist [ein echtes Beispiel](../../README.de.md#was-er-für-dich-tut).
- **Wie Du antwortest:** Ändere die Aufgabe wie gewohnt im Tracker. Hat Dein Team Antworten eingeschaltet, kannst Du auch einfach auf die Mail antworten, in Deiner eigenen Sprache; Deine Antwort landet als Notiz an der Aufgabe. In Matrix oder Signal reicht ein kurzes „Freitag“ oder „2 Tage“, und der Agent fragt Dich, ob er es so eintragen soll.
- **Was er mit Daten über Dich macht:** [eine Seite in einfacher Sprache](people-data.md). Kurz gesagt: keine Bewertungen, keine Messung von Antwortzeiten, und das Sprachmodell läuft auf dem eigenen Rechner Eurer Firma.
- **Du willst kein Briefing, oder eine andere Zeit oder Sprache?** Bitte Deine Teamleitung, Deinen Eintrag in der Team-Datei zu ändern. Mit „stopp“ zu antworten, schaltet es noch nicht ab.
