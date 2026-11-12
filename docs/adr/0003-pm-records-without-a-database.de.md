# ADR-0003: PM-Einträge ohne Datenbank

🇬🇧 [English](0003-pm-records-without-a-database.md) · 🇩🇪 Deutsch

- **Status:** angenommen
- **Datum:** 2026-11-12

## Kontext

Eine Projektleitung führt mehr als Aufgaben: ein RAID-Register (Risiken, Annahmen, Probleme, Abhängigkeiten), Änderungsanträge, Entscheidungen, Basispläne, Besprechungsnotizen und einen Arbeitstakt. Der Agent ist bewusst zustandslos ([Datenmodell](../de/data-model.md)). Diese Einträge brauchen also ein Zuhause in Infrastruktur, die das Team schon betreibt, wo Menschen sie auch ohne den Agenten sehen und bearbeiten können.

## Entscheidung

| Eintrag | Primärer Ort | Ausweichort |
|---------|--------------|-------------|
| Risiko, Annahme, Problem, externe Abhängigkeit | Tracker-Eintrag mit nativem Typ, wenn der Tracker einen hat (Jira, Azure DevOps), sonst Label `type:risk` / `type:assumption` / `type:issue` / `type:dependency` | — |
| Änderungsantrag | Tracker-Eintrag `type:change-request`, der die Arbeit verlinkt, die er auslösen würde | — |
| Entscheidung | Tracker-Eintrag `type:decision` oder Markdown in `.agent-pm/decisions/NNNN-titel.md` | Datei im Repo |
| Meilenstein | Meilenstein oder Epic des Trackers | Eintrag `type:milestone` |
| Basisplan | Schnappschuss `.agent-pm/baselines/JJJJ-MM-TT.json` (Fälligkeiten und Schätzungen je Aufgabe), per Pull Request eingecheckt | — |
| Besprechungsnotizen | Kommentar am zugehörigen Eintrag oder `.agent-pm/meetings/JJJJ-MM-TT-thema.md` | Datei im Repo |
| Arbeitstakt | Abschnitt `cadence:` in `team.yaml` | — |

**Strukturierte Felder** (Wahrscheinlichkeit, Auswirkung, Gegenmaßnahme, Prüftermin) nutzen die eigenen Felder des Trackers, wo es sie gibt. Sonst stehen sie in einem kleinen Block in der Beschreibung, den auch Menschen bearbeiten können:

````markdown
```agent-pm
probability: 3   # 1-5
impact: 4        # 1-5
mitigation: Angebot eines zweiten Lieferanten bis 2026-12-01
review: 2026-11-20
```
````

**Schreiben folgt den Berechtigungsstufen.**
- Ein Risiko oder eine Entscheidung vorzuschlagen ist geringes Risiko und wird protokolliert.
- Ein neuer Basisplan und PSP-Entwürfe haben hohe Tragweite, deshalb bleiben sie Entwürfe, bis eine Teamleitung sie freigibt.
- Neuer Umfang wird nie ohne freigegebenen Änderungsantrag zu Arbeitspaketen.

## Konsequenzen

- ✅ Alles bleibt in den Werkzeugen sichtbar und bearbeitbar, die das Team schon nutzt. Es überlebt auch ohne den Agenten.
- ✅ Basispläne und Entscheidungen bekommen über Git eine Versionsgeschichte und ein Review.
- ⚠️ Eine Label-Konvention ist schwächer als native Typen. Gemischte Teams müssen sich einmal auf die Labels einigen (`agent-pm validate` prüft sie später).
- ⚠️ Das Register zu lesen heißt, bei jedem Lauf die Einträge mit diesen Labels aufzulisten. Für ein Projekt ist das kein Problem, für große Portfolios aber aufwendiger.
