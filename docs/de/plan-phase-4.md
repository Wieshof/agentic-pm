# Plan für Phase 4: Planung & Steuerung

🇬🇧 [English](../plan-phase-4.md) · 🇩🇪 Deutsch

- **Status:** abgestimmt, noch nicht begonnen
- **Datum:** 17.11.2026
- **Issues:** #48 #49 #50 #51 #52 #54 #55 (#53 zurückgestellt)

Mit den Phasen 1–3 kann der Agent lesen, warnen, nachfragen und aktualisieren. In Phase 4 **führt er die Unterlagen des Projekts**: einen aus einem Ziel entworfenen Plan, Risiken, Änderungsanträge, Entscheidungen, Basispläne und einen monatlichen Gesundheitscheck. Das alles sind Einträge, die das Team auch ohne den Agenten sehen und bearbeiten kann ([ADR-0003](../adr/0003-pm-records-without-a-database.de.md)).

## Entscheidungen

| Frage | Entscheidung |
|-------|--------------|
| Wo liegen die Einträge? | **Im Tracker**, der einzigen Quelle der Wahrheit. Die Schnittstelle wird für jeden Tracker vorgesehen; gebaut wird sie dort, wo sie gebraucht wird (jetzt: GitHub). |
| Und bei Tabellen? | **Zusätzliche Blätter** in derselben Arbeitsmappe (`Planentwurf`, `RAID`, `Änderungen`, `Entscheidungen`), die dem Agenten gehören. An das Aufgabenblatt selbst wird nur angehängt, und nur nach einer Freigabe. |
| Dateien im Repository (Basispläne, Entscheidungen, Besprechungsnotizen)? | **Pull Request**, damit ein Mensch prüft und zusammenführt. |
| Erstes Feature nach der Grundlage? | **PSP-Generator (#48)**: Aus einem Ziel wird ein Planentwurf zur Freigabe. |
| Kalender (#53)? | **Zurückgestellt.** Kommt eventuell am Ende von Phase 4 oder in Phase 6. |
| Asana? | Passt gut (eigene Meilensteine, Freigabe-Aufgaben und benutzerdefinierte Felder; #30). Die Grundlage ist so entworfen, dass Asana der nächste Tracker mit Schreibzugriff sein kann. |

## Schritte

### 4.0 Grundlage: Einträge anlegen

In Phase 4 legt fast alles etwas an. Heute kann der Agent nur bestehende Aufgaben kommentieren und ändern, und das nur bei GitHub.

- **Protokoll:** `create_task(project, NewTask, meta)` und `add_dependency(a, b, meta)`, beide optional und über Fähigkeiten abgesichert.
  - `NewTask` enthält Titel, Beschreibung, Art, Labels, Zuständige, Termin, Schätzung, übergeordnetes Element oder Meilenstein und Abhängigkeiten.
  - Adapter, die nichts anlegen können, melden das freundlich als nur lesbar.
- **Fähigkeiten** (Katalog): `creates` und `records`, wobei `records` eins hiervon ist:
  - `native`: Jira, Azure DevOps, Arbeitspaket-Typen in OpenProject
  - `custom_field`: Asana
  - `label`: GitHub, GitLab, Gitea
  - `sheet`: Tabelle
  - `none`

  Die Übersicht in der Doku zeigt sie an.
- **Eintrags-Schicht** (`agentic_pm.records`): Die Arten sind Meilenstein, Risiko, Annahme, Problem, Abhängigkeit, Änderungsantrag, Entscheidung und Planentwurf.
  - Sie liest und schreibt den kleinen bearbeitbaren Datenblock aus ADR-0003.
  - Sie listet Einträge einer Art auf.
  - `agent-pm validate` prüft die Label-Konvention.
- **Freigaben für „anlegen“:** Heute trägt eine signierte Freigabe eine Feldänderung. Ein Plan kann 30 Punkte haben, zu viel für einen Link. Deshalb liegt der Entwurf **als ein Eintrag im Tracker** (`type:plan-draft`, lesbarer Plan plus YAML-Block), und das Freigabe-Token trägt nur diesen Eintrag und einen Hash seines Inhalts.
  - Man kann den Entwurf vor der Freigabe bearbeiten. Ein geänderter Entwurf bekommt eine neue Freigabeanfrage, statt veralteten Inhalt umzusetzen.
- **GitHub:** Issues, Labels, Meilensteine und Abhängigkeiten anlegen.
- **Tabelle:** Geschrieben wird nur in Blätter, die dem Agenten gehören.
  - Vor dem ersten Schreiben legt der Agent eine Sicherungskopie an.
  - Enthält die Arbeitsmappe etwas, das `openpyxl` nicht erhalten kann (Diagramme, Pivot-Tabellen, Bilder), schreibt er stattdessen in eine Begleitdatei `<Name>.agent-pm.xlsx` und sagt das dazu.
  - Wer mit CSV arbeitet, bekommt Dateien daneben (`raid.csv`, …).
- **Repo-Schreiber:** Branch plus Commit plus Pull Request über die GitHub-API, genutzt ab 4.3. Gitea folgt später.
- **Fertig, wenn:** die Vertragstests das Anlegen abdecken, GitHub und Tabellen in Tests Einträge anlegen und die anderen Adapter klar sagen, dass sie es noch nicht können.

### 4.1 PSP-Generator (#48)

Eine Auftraggeberin oder ein Auftraggeber beschreibt ein Ziel per E-Mail, Chat oder Sprachnachricht oder mit `agent-pm plan --from ziel.md`. Der Agent entwirft einen Plan:

1. **Modell-Schritt** (lokales LLM, JSON-Schema): Meilensteine, Arbeitspakete mit Abnahmekriterien, grobe Schätzungen, Abhängigkeiten zwischen ihnen und **offene Fragen**, die er beantwortet braucht (Umfang, Rahmenbedingungen, Erfolgskriterien).
2. **Prüfung**, wie bei der Briefing-Zusammenfassung und den How-tos:
   - Größen in Grenzen, jedes Paket in einem Meilenstein, keine erfundenen Nummern
   - Abhängigkeiten ohne Zyklus, plausible Schätzungen
   - in der Ticket-Sprache geschrieben, keine erfundenen Personen
3. **Feste Terminplanung:** Ein Vorwärtsdurchlauf über Abhängigkeiten und Schätzungen ergibt Terminvorschläge und den kritischen Pfad. Die heutige Kapazitätsprüfung markiert Kollisionen mit bestehender Arbeit.
4. **Entwurf:** ein Eintrag `type:plan-draft` (bei Tabellen: das Blatt `Planentwurf`). Die Teamleitungen bekommen eine Freigabeanfrage (hohe Tragweite), die Auftraggeberin oder der Auftraggeber die offenen Fragen im eigenen Kanal.
5. **Nach der Freigabe:** Meilensteine, Pakete und Abhängigkeiten werden angelegt. Der Entwurf wird mit Links auf alles Angelegte geschlossen. Die Zuständigen werden einmal gebeten, ihre Pakete und Termine zu bestätigen.

- **Modellqualität:** eine neue Testreihe `agent-pm eval --suite wbs` (Ziele auf Deutsch und Englisch, klein bis mittel), mit qwen3.5 und gemma4. Lehnt die Prüfung zu oft ab, gibt es statt eines schwachen Plans ein Gerüst (nur Meilensteine) plus offene Fragen.
- **Fertig, wenn:** ein auf Deutsch geschriebenes Ziel für ein englischsprachiges Projekt einen prüfbaren englischen Plan ergibt. Freigeben legt ihn an; wird der Entwurf vorher bearbeitet, entsteht die bearbeitete Fassung; Ablehnen hinterlässt nichts.

### 4.2 RAID-Register (#49)

- Risiken, Annahmen, Probleme und Abhängigkeiten als Einträge, mit Wahrscheinlichkeit × Auswirkung, Zuständigen, Gegenmaßnahme und Prüftermin.
- **Der Agent schlägt Risiken vor** aus dem, was er ohnehin sieht: Verzögerungen, Widersprüche, blockierte Arbeit und Lieferantentermine. Er legt sie als auditierte Einträge mit geringem Risiko an, die man schließen kann, wenn man anderer Meinung ist.
- Briefings und die Feierabend-Notiz zeigen neue, sich verschärfende, herrenlose oder überfällige Einträge. Der Wochenrückblick zeigt die Entwicklung der Bewertungen.

### 4.3 Änderungssteuerung (#50)

- Heute informiert eine `scope_change`-Nachricht nur die Teamleitung. Künftig wird daraus ein Eintrag `type:change-request` in den Worten der anfragenden Person, mit:
  - **Auswirkung auf den Zeitplan** (Was-wäre-wenn über die Abhängigkeiten)
  - Aufwand und Risiken
- Die Teamleitung gibt frei oder lehnt ab. **Vor der Freigabe entsteht keine Arbeit.** Nach der Freigabe wird die Arbeit über die Mechanik aus 4.1 angelegt.
- Die Zahl der Änderungen wird zur Projektkennzahl.

### 4.4 Basispläne & kritischer Pfad (#52)

- Ein Basisplan-Schnappschuss `.agent-pm/baselines/JJJJ-MM-TT.json` entsteht, wenn ein Plan freigegeben wird, per Pull Request. Ein neuer Basisplan braucht die Freigabe der Teamleitung.
- Die Abhängigkeitsanalyse bekommt kritischen Pfad und Puffer dazu.
- Der Wochenrückblick zeigt die Abweichung vom Basisplan pro Meilenstein.

### 4.5 Monatlicher Gesundheitscheck (#54)

- Füllt den heutigen Platzhalter `monthly_health_check` mit:
  - Termintreue und Abweichung vom Basisplan
  - Zahl und Wirkung der Änderungen
  - Alter der Risiken und überfällige Prüfungen
  - geschriebene How-tos
  - einem Ampelstatus pro Bereich mit Begründung und den nötigen Entscheidungen
- **Nur auf Team- und Projektebene** ([ADR-0004](../adr/0004-people-data-boundaries.de.md)).

### 4.6 Entscheidungen & Besprechungen (#51)

- Entscheidungen werden aus Threads und Antworten als Einträge `type:decision` oder als Dateien in `.agent-pm/decisions/` (per Pull Request) festgehalten.
- Agenda-Entwürfe entstehen aus offenen RAID-Einträgen, Änderungsanträgen und anstehenden Entscheidungen.
- Aufgaben aus Besprechungen werden zu Tickets, sobald die zuständige Person sie bestätigt.

### 4.7 Qualität & Abschluss (#55)

- Abnahmekriterien und UAT-Stand pro Meilenstein, dazu der Fehlertrend.
- Ein Abschlussbericht: geliefert gegenüber geplant, und übergebene offene Punkte.
- Lessons learned, mit einer kurzen Frage an jede Person gesammelt und als Markdown per Pull Request abgelegt.

### Zurückgestellt: Kalender (#53)

Abwesenheiten in der Kapazitätsprüfung und Besprechungsvorbereitung. ICS/CalDAV käme zuerst.

## Risiken

- **Noch kein Pilot.** Die Phasen 2 und 3 liefen noch nicht mit einem echten Team, und Phase 4 schreibt viel. Ein Live-Test des Bestehenden (Schreiben bei GitHub, E-Mail, Matrix/Signal) sollte vor oder parallel zu 4.0 stattfinden.
- **PSP-Qualität mit einem lokalen Modell.** Abgefangen durch die Prüfung, die Testreihe, das Gerüst als Rückfalllösung und die Freigabe, bevor irgendetwas angelegt wird.
- **In Tabellen zu schreiben ist heikel.** Abgefangen durch Blätter, die dem Agenten gehören, die Sicherungskopie, die Begleitdatei als Ausweichlösung und reines Anhängen ans Aufgabenblatt.
- **Vorerst legt nur GitHub Einträge an.** Wer OpenProject, Gitea oder Asana nutzt, bekommt ein klares „noch nicht“, bis der jeweilige Adapter `create_task` kann.

## Abschluss

Ein Pilotprojekt läuft einen Monat lang mit einem aus einem Ziel erstellten Plan, dazu RAID-Register, Änderungssteuerung und Gesundheitscheck, die der Agent führt.
