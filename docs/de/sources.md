# Mehrere Tracker: Quellen und Nahtstellen

🇬🇧 [English](../sources.md) · 🇩🇪 Deutsch

Manche Teams leben nicht in einem einzigen Tracker:

- **Selbstständig mit mehreren Kunden.** Ein Kunde nutzt GitHub, ein anderer eine gemeinsame Tabelle, und Deine Zeit ist das, was sie sich teilen.
- **Ein Unternehmen, dessen Abteilungen verschiedene Tools gewählt haben.** Die Entwicklung arbeitet in GitHub, der Betrieb plant den Launch in OpenProject.

agentic-pm kopiert keine Tickets zwischen ihnen. Es liest jeden Tracker, gibt jeder Person ein Briefing über alle hinweg und baut nur dort eine Brücke, wo der Termin der einen Seite an der Arbeit der anderen hängt: an der **Nahtstelle**. Die Entscheidung dahinter steht in [ADR-0006](../adr/0006-multiple-trackers-sources-and-seams.de.md).

## Einrichten

Ersetz `project.tracker` und `project.repo` durch `sources:`. Was für das ganze Team gilt (Teamleitungen, Zeitzone, E-Mail, Anrede), bleibt unter `project:`.

```yaml
project:
  leads: [lea]
  timezone: Europe/Vienna
sources:
  eng:  {tracker: github, project: acme/app, isolation: open, leads: [erik]}
  ops:  {tracker: openproject, project: launch-q1, base_url: "https://op.acme.de",
         ticket_language: de, isolation: open}
  client-a: {tracker: github, project: client-a/site}     # standardmäßig strict
people:
  lea:  {language: de, logins: {ops: "Lea Meier"}}
  erik: {logins: {eng: erik-dev}}
```

Prüf dann, was Du geschrieben hast. `agent-pm validate` zeigt jede Quelle, wer sie leitet und wer sie sehen darf:

```bash
uv run agent-pm validate
```

| Pro Quelle | Einstellung | Standard |
|------------|-------------|----------|
| Tracker und Projekt | `tracker`, `project`, `base_url`, `tracker_options` | Pflicht |
| Sprache, in der der Agent dort schreibt | `ticket_language` | `en` |
| Abschottung | `isolation: strict` oder `open` | **`strict`** |
| Schreiben erlaubt | `allow_writes` | `false` |
| Teamleitungen | `leads` | `project.leads` |
| Zugangsdaten | Umgebungsvariable `AGENT_PM_<QUELLE>_TOKEN`, z. B. `AGENT_PM_CLIENT_A_TOKEN` | der gemeinsame Token |
| Webhook | `https://pm.deine-org.de/webhooks/<quelle>` mit `AGENT_PM_<QUELLE>_WEBHOOK_SECRET` | keiner |

Aufgabenverweise tragen jetzt ihre Quelle: `eng#142`, `ops#57`. So siehst Du sie in Briefings, im Chat (`— eng#142`) und in Antwortadressen (`pm+eng.142@…`). Eine Antwort findet also immer den richtigen Tracker.

## Wer was sieht

- **Eine Person mit `logins:`** gehört genau zu diesen Quellen (und zu denen, die sie leitet).
- **Eine Person ohne `logins:`** gehört zu jeder `open`-Quelle. Eine `strict`-Quelle muss ihre Leute ausdrücklich nennen.
- **Deine eigenen Aufgaben** stehen in Deinem Briefing, aus jeder Quelle, zu der Du gehörst. Dazu gehören auch Kollisionen zwischen ihnen, etwa „acme#14 Review und beta#T-04 Launch sind am selben Tag fällig, Do., 19.11.2026“. Das Briefing nennt Aufgaben und Termine, nie eine Auslastung.
- **Teamleitungen** sehen Team-Themen (Aufgaben ohne Zuständige, Risiken, Datenqualität, Lesbarkeit) nur für die Quellen, die sie leiten. Wer Kunde B leitet, erfährt kein Wort über Kunde A.

## Abschottung: strict und open

| | `strict` (Kunden) | `open` (Abteilungen) |
|-|-------------------|----------------------|
| Nahtstellen zu anderen Quellen | nicht verfolgt; Teamleitungen bekommen `ISOLATION_BOUNDARY_BLOCKED` | zusammengefasst und angezeigt |
| Direkte Verknüpfung zu einer anderen Quelle | nicht verfolgt, gleicher Hinweis | verfolgt wie jede Abhängigkeit |
| Was in diesen Tracker geschrieben wird | nichts über irgendeine andere Quelle | nichts über eine `strict`-Quelle |

Jeder Schreibvorgang wird doppelt geprüft. Er muss für die eigene Quelle seines Ziels handeln. Sein Text darf keine andere Quelle nennen, von der das Ziel nichts wissen darf (`client-a#3`), und keinen Aufgabentitel aus ihr zitieren. Sonst wird er abgelehnt. Tests probieren genau diese Lecks aus.

## Nahtstellen

Die wartende Seite sagt einmal, worauf sie wartet, im eigenen Tracker. Schreib es in den Aufgabentext:

````markdown
```agent-pm
waits_for: eng:milestone/v2.0
```
````

Oder trag es in der Tabelle in die Spalte `Depends On` ein: `eng:milestone/v2.0`.

| Ziel | Bedeutet |
|------|----------|
| `eng#142` | ein einzelner Eintrag |
| `eng:milestone/v2.0` | alle Einträge dieses Meilensteins (OpenProject: Version) |
| `eng:label/launch` | alle Einträge mit diesem Label |

Der Agent berechnet dann die andere Seite, ohne Sprachmodell und ohne etwas zu kopieren:

- erledigte gegenüber allen Einträgen
- eine Prognose aus Terminen, Schätzungen und dem Abhängigkeitsgraphen
- den Puffer bis zum Termin der wartenden Aufgabe

Jede Seite erfährt es in ihrer eigenen Sprache:

- **Wartende Seite** (Zuständige und Teamleitungen): „ops#57 Launch campaign wartet auf eng:milestone/v2.0: 14/18 erledigt, Prognose Sa., 28.11.2026, im Plan (3 Tage Puffer)“ oder „… 2 Tage nach seinem Termin. Gefährdet.“
- **Liefernde Seite:** nur wenn ein Geschäftstermin gefährdet ist, und nur die Zuständigen der Einträge, die es entscheiden, dazu die Teamleitungen: „ops#57 Launch campaign am Di., 01.12.2026 wartet auf eng:milestone/v2.0; eng#31 und eng#35 entscheiden es.“

Haben Einträge auf der anderen Seite keinen Termin, gibt es keine ehrliche Prognose. Die wartende Seite liest dann „noch keine Prognose, weil 2 offene Einträge dort keinen Termin haben“. Diese Einträge verschwinden nie im Backlog: Ihre Zuständigen (oder die Teamleitungen dieser Quelle) bekommen die übliche Frage nach dem fehlenden Termin, als dringend markiert.

**Vorschläge:** Erwähnt ein Ticket `eng#142` oder `eng:milestone/v2.0`, ohne es einzutragen, bekommt die zuständige Person eine Frage: „Wartet es darauf? Dann ergänz `waits_for: …`“. Nichts wird automatisch verknüpft.

## Was später kommt

- **Statuszeilen im wartenden Ticket** (nur bei `open`-Quellen), z. B. `eng:milestone/v2.0 · 14/18 erledigt · Prognose 2026-11-28 · 3 Tage Puffer`. Sie kommen mit dem bearbeitbaren agent-pm-Block in Schritt 4.0, damit die Zeile an Ort und Stelle aktualisiert wird, statt dass sich Kommentare stapeln. Die Schreibprüfung, durch die sie gehen werden, ist schon fertig.
- **Epics als Ziel einer Nahtstelle**, sobald Adapter die Einträge eines Epics auflisten können.
