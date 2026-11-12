# ADR-0004: Grenzen für Daten über Menschen

🇬🇧 [English](0004-people-data-boundaries.md) · 🇩🇪 Deutsch

- **Status:** angenommen
- **Datum:** 2026-11-12

## Kontext

Zur Arbeit einer Projektleitung gehören auch Personenthemen: Auslastung, Kapazitätskonflikte, Stimmung, Coaching, Leistung. Ein Agent, der jedes Ticket und jede Nachricht liest, könnte leicht zu einem Überwachungswerkzeug werden. Das würde das Vertrauen zerstören, auf das er angewiesen ist, und es würde rechtliche Probleme verursachen:
- DSGVO: Zweckbindung, Transparenz und meist eine Datenschutz-Folgenabschätzung.
- In Deutschland und Österreich: Mitbestimmung des Betriebsrats bei technischen Systemen, die Verhalten oder Leistung überwachen können (§ 87 Abs. 1 Nr. 6 BetrVG; §§ 96, 96a ArbVG).

## Entscheidung

1. **Zweck: das Projekt liefern, nie Menschen bewerten.** Der Agent bewertet, reiht oder benotet keine Einzelpersonen.
2. **Aufgabenbezogen statt personenbezogen.** Kapazitätsprüfungen schauen auf die **aktuell** offene Arbeit und sagen, was kollidiert, z. B. „#12 und #31 sind beide Freitag fällig und beide auf dem kritischen Pfad“. Sie schlagen eine Lösung vor (verschieben, aufteilen, übergeben). Es gibt keine Auslastungsprozente und keine Werte pro Person.
3. **Keine Personenhistorie.** Keine gespeicherten Profile, Verläufe oder Ranglisten pro Person. Signale pro Person, die der Agent zum Arbeiten braucht, etwa auf welchem Kanal jemand antwortet, bleiben nur kurz im Arbeitsspeicher. Die betroffene Person kann sie einsehen und abschalten.
4. **Nur Team-Werte** für Team-Kennzahlen (Engagement, Kurzumfragen), und erst ab einer Gruppengröße von 5 wird etwas angezeigt.
5. **Keine abgeleiteten Zustände.** Keine Erkennung von Stimmung, Stress, Moral oder Burnout aus Nachrichten oder Aktivität.
6. **Themen nur zur Unterstützung.** Leistungsbeurteilung, Coaching, Konfliktlösung, Personalauswahl und die Freigabe von Rechnungen oder Bestellungen bleiben beim Menschen. Der Agent darf neutrales Material vorbereiten, z. B. die offenen Punkte für die Agenda eines 1:1, aber er urteilt und entscheidet nicht.
7. **Transparenz.** Doku und Onboarding-Nachrichten nennen, was der Agent verarbeitet, wozu und wie lange. Jede Person kann die Daten einsehen, die sie betreffen.

Bezieh vor einem Rollout Deine Datenschutzbeauftragte bzw. Deinen Datenschutzbeauftragten ein und, wo es einen gibt, den Betriebsrat. Dieses ADR ist ein Gestaltungsprinzip, keine Rechtsberatung.

## Konsequenzen

- ✅ Auslastungsprobleme werden trotzdem früh erkannt, als Planungsprobleme mit konkreter Lösung statt als Urteile über Menschen.
- ✅ Leichtere Abstimmung mit Datenschutz und Betriebsrat.
- ⚠️ Manche Zahlen „klassischer“ PM-Dashboards (Auslastung oder Produktivität einzelner Personen) gibt es bewusst nicht.
- ⚠️ Die adaptive Nachfass-Taktung (Phase 3) muss mit kurzlebigen Signalen pro Person auskommen, die man abschalten kann.
