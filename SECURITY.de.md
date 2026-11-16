# Sicherheitsrichtlinie

🇬🇧 [English](SECURITY.md) · 🇩🇪 Deutsch

Danke, dass Du hilfst, agentic-pm und die Menschen, die es nutzen, sicher zu halten. 💙

## Eine Schwachstelle melden

Bitte **eröffne kein öffentliches Issue** für ein Sicherheitsproblem. Melde es stattdessen vertraulich:

👉 **[Schwachstelle melden](https://github.com/Wieshof/agentic-pm/security/advisories/new)** (vertrauliche Meldung über GitHub)

Hilfreich ist, soweit Du es weißt:

- was ein Angreifer tun könnte und was er dafür braucht (z. B. „kann ein Ticket kommentieren“, „erreicht den MCP-Server“)
- Schritte oder ein kleines Beispiel, um es nachzustellen
- die Version oder der Commit, den Du Dir angesehen hast

Du bekommst innerhalb von **7 Tagen** eine erste Antwort. Wir halten Dich auf dem Laufenden, während wir an einer Lösung arbeiten, stimmen den Veröffentlichungstermin mit Dir ab und nennen Dich gern in der Sicherheitsmeldung.

## Unterstützte Versionen

agentic-pm ist noch früh dran (0.x). Korrekturen landen nur in **`main`**; teste bitte immer mit dem aktuellen `main`.

## Worauf es am meisten ankommt

Der Agent liest nicht vertrauenswürdigen Text (Tickets, E-Mails) und kann in Tracker schreiben. Hier wiegt eine Schwäche am schwersten, deshalb sind Meldungen dazu besonders willkommen:

| Bereich | Was gelten soll |
|---------|-----------------|
| **Freigaben** | Keine Änderung über geringem Risiko wird ohne Bestätigung der zuständigen Person oder einen signierten Freigabe-Link der Teamleitung ausgeführt. Niemand kann freigeben, indem er behauptet, jemand anderes zu sein. |
| **Signierschlüssel** (`AGENT_PM_SIGNING_KEY`) | Freigabe-Tokens und die Audit-Fußzeile lassen sich nicht fälschen, nach Gebrauch nicht erneut verwenden und nicht für eine andere Aufgabe einsetzen. |
| **Webhooks** | Anfragen ohne gültige Signatur werden abgewiesen; der Agent reagiert nie auf seine eigenen Änderungen und lässt sich nicht durch eingefügten Text stummschalten. |
| **Ticket- und E-Mail-Text** | Nicht vertrauenswürdiger Text führt nur zu Vorschlägen oder Kommentaren mit geringem Risiko, nie zu Freigaben, Neuzuweisungen oder verschobenen Terminen. |
| **Personendaten** | Keine Bewertungen oder Verläufe einzelner Personen ([ADR-0004](docs/adr/0004-people-data-boundaries.de.md)). |
| **Geheimnisse** | Tokens und Schlüssel stehen nur in Umgebungsvariablen, nie in `team.yaml` oder in Nachrichten. |

Das Sicherheitsmodell steht unter [Den Agenten betreiben](docs/de/running.md#3-sicherheitsmodell) und in den [Leitplanken](docs/de/guardrails.md).

## Nicht im Umfang

- Schwachstellen in einem Tracker, Mailserver oder einer LLM-Laufzeit selbst (bitte melde sie deren Betreuern)
- Probleme, die einen bereits kompromittierten Rechner oder einen geleakten Signierschlüssel voraussetzen
- Betrieb mit eingeschaltetem Schreiben, aber ohne `AGENT_PM_SIGNING_KEY`, wovon die Doku abrät

Nicht sicher, ob etwas zählt? Melde es trotzdem. Wir hören lieber einmal zu viel davon. 🙂
