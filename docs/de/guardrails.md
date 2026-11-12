# Betriebliche Leitplanken & Erfolgskennzahlen

🇬🇧 [English](../guardrails.md) · 🇩🇪 Deutsch

Wer einer KI Schreibzugriff auf Projekt-Repositorys und direkte Kommunikationskanäle gibt, braucht klare Grenzen, damit das Team ihr vertrauen kann.

## Gestufte Schreibrechte

| Stufe | Beispiele | Verhalten |
|-------|-----------|-----------|
| **Geringes Risiko** | Kommentare protokollieren, nachträgliche Doku anhängen, Blocker markieren, Labels setzen | Läuft automatisch, mit Audit-Trail |
| **Mittleres Risiko** | Interne Termine ändern, Status im Namen der zuständigen Person aktualisieren | Läuft automatisch, wenn die Person im Kanal bestätigt hat; sonst wird sie gefragt |
| **Hohe Tragweite** | Aufgaben löschen, Zuständige neu zuweisen, externe Kundentermine verschieben | **Bestätigungsanfrage an die zuständige Teamleitung**, bevor etwas ausgeführt wird |

Die Stufen sollen pro Projekt in `.agent-pm/policy.yaml` konfigurierbar sein (geplant).

## Einwilligung & Datenschutz

- Ein- und ausgehende Anrufe enthalten einen **automatischen Hinweis**, wenn transkribiert wird.
- Alle Gesprächsprotokolle sind **strikt auf den Projekt-Workspace beschränkt**.
- **Kein Training** externer Foundation-Modelle mit Projektdaten.
- Sprachtranskripte liegen nur für die Dauer des Anrufs im Arbeitsspeicher (siehe [Datenmodell](data-model.md)).
- Persönliche Präferenzen bleiben unter der Kontrolle der jeweiligen Person (`team.yaml` / SSO).

## Ziel-KPIs

| KPI | Ziel |
|-----|------|
| Reduktion der manuellen Ticketbearbeitungszeit | > 70 % |
| Mittlere Zeit bis zur Sichtbarkeit eines Abhängigkeits-Blockers | < 2 h nach Statusänderung |
| Kanalübergreifende Beteiligungsquote | Anteil der Teammitglieder, die Tickets aktiv über ihren gewählten Kanal aktualisieren |

### Sekundäre Indikatoren (Infrastrukturabbau)

- Anzahl abgeschalteter Schatten-Tracker / Reporting-Plugins
- Durch Stellvertreter-Interaktion eingesparte Tracker-Lizenzen
- Anteil geschlossener Tickets mit angehängtem How-to-Abschnitt
