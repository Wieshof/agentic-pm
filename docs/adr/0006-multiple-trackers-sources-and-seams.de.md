# ADR-0006: Mehrere Tracker: Quellen und Nahtstellen

🇬🇧 [English](0006-multiple-trackers-sources-and-seams.md) · 🇩🇪 Deutsch

- **Status:** angenommen
- **Datum:** 17.11.2026
- **Ersetzt:** den trackerübergreifenden Teil von #59 (Phase 7), der in Schritt 4.0a vorgezogen wird

## Kontext

Bisher heißt eine `team.yaml` ein Tracker und ein Projekt. Ein Verweis auf einen anderen Tracker (`github:acme/api#42`) wird bemerkt, aber nicht geprüft. Zwei häufige Situationen brauchen mehr:

- **Ein Ein-Personen-Unternehmen mit mehreren Kunden.** Jeder Kunde nutzt seinen eigenen Tracker: einer Jira, einer GitHub, einer eine gemeinsame Tabelle. Die Zeit der oder des Selbstständigen ist die gemeinsame Ressource, und kein einzelner Tracker kann zeigen, dass das Review für Kunde A und der Launch für Kunde B beide am Donnerstag dieselbe Person brauchen.
- **Ein Unternehmen, dessen Abteilungen bewusst verschiedene Tracker nutzen.** Die Entwicklung verfolgt Pull Requests und Bugs in GitHub, Betrieb oder Produkt verfolgen Liefergegenstände und Launch-Meilensteine in OpenProject. Sie arbeiten in unterschiedlicher Detailtiefe.

Die übliche Antwort ist, Tickets zwischen solchen Tools zu spiegeln, und das scheitert. Der Betrieb wird mit technischem Rauschen überflutet, die Entwicklung mit geschäftlichen Checklisten, und zwei Kopien laufen auseinander. Worauf es ankommt, ist die **Nahtstelle**: die wenigen Stellen, an denen der Termin der einen Seite von der Arbeit der anderen abhängt.

## Entscheidung

agentic-pm ist **Übersetzer und Abhängigkeitsbrücke an der Nahtstelle**, kein Synchronisierungs-Tool. Niemand wird in ein gemeinsames Board oder Vokabular gezwungen.

### 1. Mehrere Quellen in einer Team-Datei

```yaml
sources:
  eng:  {tracker: github,      project: acme/app,  ticket_language: en}
  ops:  {tracker: openproject, project: launch-q1, base_url: https://op.acme.de,
         ticket_language: de}
people:
  sam:
    logins: {eng: sam-dev, ops: "Sam Meier"}   # eine Person, ein Login pro Tracker
```

- Das heutige `project:` bleibt als Kurzform für eine einzelne Quelle gültig. Bestehende Team-Dateien funktionieren unverändert weiter.
- Jede Quelle hat eigene **Zugangsdaten** (`AGENT_PM_<QUELLE>_TOKEN`, z. B. `AGENT_PM_ENG_TOKEN`), einen eigenen **Webhook-Pfad** (`/webhooks/<quelle>`), eine eigene **Ticket-Sprache**, ein eigenes **Schreibrecht** (`allow_writes`) und eigene **Teamleitungen**.
- Aufgabenverweise tragen die Quelle (`eng#142`, `ops#57`). Abhängigkeitsgraph, Kapazitätsprüfung, Vollständigkeitsprüfung und Briefings arbeiten über alle Quellen zusammen.

### 2. Eine Nahtstelle ist eine Abhängigkeit, dort festgehalten, wo sie gebraucht wird

Die wartende Seite sagt einmal, worauf sie wartet, im eigenen Tracker, im bearbeitbaren Block aus [ADR-0003](0003-pm-records-without-a-database.de.md):

````markdown
```agent-pm
waits_for: eng:milestone/v2.0     # oder eng#142, oder eng:label/launch
```
````

- Die andere Seite kann **eine Gruppe** sein: ein Meilenstein, ein Label oder ein Epic. Der Betrieb hängt an „v2.0“, nicht an 18 Pull Requests.
- Tabellen nutzen ihre bestehende Spalte `Depends On` (`eng:milestone/v2.0`).
- Der Agent **schlägt** eine Nahtstelle **vor**, wenn ein Tickettext die andere Seite erwähnt („wartet auf das Release v2.0“), aber ein Mensch bestätigt sie. Nichts wird automatisch verknüpft.
- **Nie wird ein Eintrag** in einen anderen Tracker kopiert.

### 3. Übersetzung an der Nahtstelle

Der Agent berechnet eine **Zusammenfassung** der Gruppe auf der anderen Seite. Sie ist fest berechnet, braucht kein Sprachmodell und ergibt:
- erledigte gegenüber allen Einträgen
- gefährdete Einträge
- einen voraussichtlichen Termin aus Terminen, Schätzungen und Abhängigkeitsgraph

Jede Seite erfährt dann einmal von der anderen, in ihren eigenen Worten:

| Wer | Was sie sieht |
|-----|---------------|
| Wartende Seite (Betrieb) | „Launch-Kampagne: Entwicklung voraussichtlich am 28.11. fertig, im Plan (3 Tage Puffer)“ oder „gefährdet: voraussichtlich 3.12., 2 Tage nach dem Launch“ |
| Liefernde Seite (Entwicklung) | Nur wenn ein Geschäftstermin gefährdet ist: „Die Launch-Kampagne am 1.12. wartet auf v2.0; #31 und #35 entscheiden es“ |

- Status werden über die Statusnamen des jeweiligen Trackers übersetzt. Technische Einträge bleiben auf ihrer Seite; die andere Seite sieht eine Prognose, einen Puffer und einen Grund.
- Triangulation ([ADR-0005](0005-chat-channels.de.md)) und Nachfassen funktionieren über die Nahtstelle genauso: Eine Frage geht an die zuständige Person, auf ihrer Seite, in der Sprache ihres Trackers.

### 4. Abschottung zwischen Quellen

Jede Quelle hat eine Einstellung `isolation`:

| Abschottung | Standard für | Was über die Nahtstelle darf |
|-------------|--------------|------------------------------|
| `strict` | Kunden-Quellen | **In diese Quelle wird nichts über andere Quellen geschrieben**: keine Kommentare, Aufgabentitel, Namen oder Termine. Quellenübergreifendes erscheint nur im privaten Briefing der Personen, die zu beiden gehören. |
| `open` | Interne Abteilungen | Zusammenfassungen an der Nahtstelle und kurze Statuszeilen dürfen mit Audit-Fußzeile als Kommentar am wartenden Eintrag stehen. |

- Drei Kunden einer oder eines Selbstständigen sind drei strikte Quellen: ein Briefing für die Person, und nichts sickert zwischen den Kunden durch.
- Abteilungen eines Unternehmens sind füreinander meist offen.
- `agent-pm validate` weist eine Nahtstelle zurück, für die in eine strikte Quelle geschrieben werden müsste.

### 5. Menschen

- Eine Person kann pro Quelle einen eigenen Login haben (`logins:`).
- Weiterhin keine Historie oder Bewertung einzelner Personen ([ADR-0004](0004-people-data-boundaries.de.md)).
- Kapazitätskollisionen über Quellen hinweg nennen Aufgaben und Termine, nie eine Auslastung.

## Konsequenzen

- ✅ Abteilungen behalten ihre Tools, ihre Detailtiefe und ihr Vokabular. Der Agent baut nur dort eine Brücke, wo der Termin der einen Seite an der Arbeit der anderen hängt.
- ✅ Selbstständige bekommen einen Blick über alle Kunden, einschließlich Kollisionen, die kein einzelner Kunde sehen könnte, ohne dass Daten zwischen Kunden wandern.
- ✅ Keine Kopien, die auseinanderlaufen; jeder Tracker bleibt die Quelle der Wahrheit für seine eigenen Einträge.
- ✅ Der Teil ohne Schreibzugriff (ein Briefing, trackerübergreifende Abhängigkeiten, Kollisionen) funktioniert mit jedem Adapter, den es heute gibt.
- ⚠️ Prognosen sind nur so gut wie die Termine und Schätzungen der liefernden Seite. Die Vollständigkeitsprüfung fragt nach dem, was fehlt.
- ⚠️ Gruppen als Ziel einer Nahtstelle (Meilenstein, Label, Epic) setzen voraus, dass ein Adapter die Einträge einer Gruppe auflisten kann. Wo das nicht geht, gibt es nur Nahtstellen zu einzelnen Einträgen.
- ⚠️ `team.yaml` bekommt eine neue Form. `project:` funktioniert weiter, und `agent-pm validate` erklärt, wie man auf `sources:` umstellt.

## Umsetzungsregeln

Verbindlich für Schritt 4.0a. Sie machen die Entscheidung oben sicher umsetzbar.

1. **Zwei Sprachen, keine Übersetzung durch ein Modell.**
   - Zusammenfassungen an der Nahtstelle sind Zahlen und Termine (erledigt/gesamt, Prognose, Puffer), es muss also nie ein Tickettitel übersetzt werden.
   - Zeilen im **Briefing einer Person** stehen in ihrer `language` aus `team.yaml`: „Engineering-Prognose 28. Nov., 3 Tage Puffer“ / „engineering forecast 28 Nov, 3 days buffer“. Ein zweites Feld `brief_language`, das dem widersprechen könnte, gibt es bewusst nicht.
   - Statuszeilen, die **in ein Ticket geschrieben** werden, stehen in der `ticket_language` der Zielquelle. Ein OpenProject-Board mit `ticket_language: de` bekommt deutsche Zeilen, auch wenn es auf ein englisches GitHub-Repo wartet.
2. **`strict` ist der Standard und wird doppelt durchgesetzt.**
   - `isolation` steht in der Quellen-Konfiguration standardmäßig auf `strict`, eine vergessene Einstellung kann also nichts durchsickern lassen.
   - **Lesen:** Eine `waits_for`-Nahtstelle, die eine `strict`-Quelle berührt (an einem der beiden Enden), wird nicht aufgelöst, sondern endet mit dem Hinweis `ISOLATION_BOUNDARY_BLOCKED`, den Teamleitungen wie jeden anderen Lesbarkeits-Hinweis sehen. *Kollisionen* über Quellen hinweg bleiben sichtbar, aber nur im privaten Briefing einer Person, die zu beiden Quellen gehört.
   - **Schreiben:** Jeder Schreibvorgang trägt die Quelle, für die er handelt (`AuditMeta.source`), und jeder Aufgabenverweis seine Quelle (`TaskRef.source`, weil zwei Kunden beide auf GitHub sein können). Die Prüfung weist einen Schreibvorgang zurück, dessen Zielquelle nicht die Quelle der Aktion ist. Sie weist auch einen zurück, dessen Text auf eine andere `strict`-Quelle verweist oder einen Aufgabentitel daraus enthält.
3. **Statuszeilen bei `open` enthalten nur Zahlen und Termine.** Zum Beispiel `eng:milestone/v2.0 · 14/18 erledigt · Prognose 2026-11-28 · 3 Tage Puffer`, dazu die signierte Audit-Fußzeile.
   - Keine Issue-Titel der anderen Seite und keine Namen von Zuständigen: Technische Details bleiben auf ihrer Seite.
   - Über die Fußzeile ignoriert der Webhook-Filter die eigenen Änderungen des Agenten.
   - Die Zeile wird im ADR-0003-Block an Ort und Stelle aktualisiert, nicht jedes Mal als neuer Kommentar angehängt.
4. **Kollisionen nennen Aufgaben und Termine, nie eine Auslastung.** Zum Beispiel: „Kunde A #14 und Kunde B T-04 sind beide am Do., 19.11.2026 fällig.“
   - Schätzungen fehlen oft oder sind grob, während zwei Liefergegenstände am selben Tag eine objektive Tatsache sind, mit der man sofort etwas anfangen kann.
   - So bleibt es auch bei [ADR-0004](0004-people-data-boundaries.de.md).

## Umsetzung

> **Stand (20.11.2026):** Punkte 1–5 sind gebaut ([Anleitung](../de/sources.md)). Statuszeilen in `open`-Tickets (Regel 3) folgen mit dem agent-pm-Block in Schritt 4.0; die Schreibprüfung, durch die sie gehen, ist fertig.

Schritt **4.0a** im [Plan für Phase 4](../de/plan-phase-4.md), vor der Grundlage 4.0:

1. Konfiguration `sources:`, Zugangsdaten, Webhooks und Ticket-Sprache pro Quelle; `project:` bleibt als Kurzform.
2. Abhängigkeitsgraph, Briefings, Kapazität und Vollständigkeit über mehrere Quellen, alles nur lesend.
3. Nahtstellen: `waits_for:` im agent-pm-Block und in Tabellenzellen, Zusammenfassungen von Gruppen (Meilenstein, Label), Prognose und Puffer, dazu Nahtstellen-Zeilen in den Briefings beider Seiten.
4. Abschottung: `strict` / `open`, durchgesetzt in jedem Schreibweg und in den Prüfungen, mit Tests, die versuchen, Daten durchsickern zu lassen.
5. Vorschläge für Nahtstellen aus Tickettexten (von einem Menschen bestätigt).
