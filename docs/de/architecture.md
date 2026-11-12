# Architektur & Kanalzuordnung

🇬🇧 [English](../architecture.md) · 🇩🇪 Deutsch

agentic-pm ist eine **dreischichtige Middleware**. Sie liest den Zustand aus den zugrunde liegenden Werkzeugen ein, analysiert Abhängigkeiten und Widersprüche und überträgt Änderungen über die Kommunikationskanäle.

## 1. Repository-Adapterschicht (Open Core)

Bidirektionale Konnektoren, die **Aufgaben, Zuständige, Termine, Abhängigkeiten und Kommentare** synchronisieren.

| Ziel | Transport | Hinweise |
|------|-----------|----------|
| OpenProject | REST API v3 (HAL+JSON), Webhooks | Native Arbeitspaket-Beziehungen für Abhängigkeiten |
| Plane | REST API, Webhooks | Selbst hostbar |
| Taiga | REST API, Webhooks | |
| GitHub Issues / Projects | GraphQL + REST, Webhooks, MCP | PR-Review-Status speist die Widerspruchserkennung |
| GitLab Issues | REST/GraphQL, Webhooks | |
| Jira | REST, Webhooks | Issue-Links → Abhängigkeitskanten |
| Linear | GraphQL, Webhooks | |

Jeder Adapter implementiert eine gemeinsame Schnittstelle (Skizze):

```ts
interface TrackerAdapter {
  getTask(ref: TaskRef): Promise<Task>;
  listDependencies(ref: TaskRef): Promise<Edge[]>;
  addComment(ref: TaskRef, markdown: string, meta: AuditMeta): Promise<void>;
  updateFields(ref: TaskRef, patch: TaskPatch, meta: AuditMeta): Promise<void>;
  subscribe(handler: (evt: TrackerEvent) => void): Unsubscribe;
}
```

Jeder Adapter wird zusätzlich als **MCP-Server** bereitgestellt, sodass die Reasoning-Engine und externe Agenten dieselben Werkzeuge nutzen.

## 2. Agentische Reasoning-Engine

Ein Orchestrierungskern, der pro Ereignis Zustand hält, aber nichts dauerhaft speichert:

- **Abhängigkeitsgraph-Analyse:** baut den Graphen bei Bedarf aus Live-Trackerdaten auf. Sie findet vor- und nachgelagerte Blocker, Änderungen am kritischen Pfad und Leerlaufrisiken.
- **Widerspruchserkennung:** vergleicht Statusaussagen aus verschiedenen Quellen (Chat-Aussagen, Tracker-Status, PR-/CI-Status, Kalender) und benennt die genaue Lücke.
- **Wissensextraktion:** macht aus Erklärungen in Gesprächen strukturiertes Markdown (Problem → Ursache → Lösung → Verifikation) und schreibt es ins Ticket zurück.
- **Taktungs- & Briefing-Planer:** entscheidet, *wer* *was* *wann* und *über welchen Kanal* erfährt.
- **Berechtigungs- & Audit-Wächter:** ordnet jeden Schreibvorgang einer Risikostufe zu und leitet folgenreiche Änderungen zur Bestätigung weiter (siehe [Leitplanken](guardrails.md)).

## 3. Omnichannel-Schnittstellenschicht

Ein einheitliches Routing-Gateway, das ausgehende Briefings und eingehende Updates an die konfigurierte Präferenz jeder Person anpasst.

| Kanal | Nutzertyp | Eingehend | Ausgehend |
|-------|-----------|-----------|-----------|
| Lesen | „Leser“ | E-Mail-Antworten | Morgendliches E-Mail-Briefing, Sammelberichte |
| Schreiben | „Schreiber“ | WhatsApp / Slack / Teams (Text) | Kurze Chat-Erinnerungen |
| Sprechen | „Sprecher“ | Anrufe, Sprachnachrichten | Ausgehende 60-Sekunden-Check-in-Anrufe |
| Zuhören | „Zuhörer“ | Gesprochene Fragen während des Briefings | Gesprochenes Status-Briefing (Anruf oder Audio) |
| Web-Steuerungsoberfläche | Leitungen / Admins | Freigaben, Konfiguration, Audit-Prüfung | Dashboards (optional) |

## Ereignisablauf (Beispiel: Aufgabe A verzögert sich)

1. Der Tracker-Webhook für das geänderte Fälligkeitsdatum von Aufgabe A erreicht den Adapter.
2. Die Engine ruft A und deren Abhängigkeitsumfeld live ab.
3. Die Abhängigkeitsanalyse stellt fest: B hängt von A ab, der Start von B ist jetzt gefährdet.
4. Der Taktungsplaner liest in `team.yaml` nach: Die verantwortliche Person für B ist ein „Sprecher“, bevorzugt nachmittags.
5. Die Schnittstellenschicht plant einen Sprach-Check-in und schlägt ein neues Datum vor.
6. Die Person stimmt mündlich zu. Der Wächter stuft die Terminänderung ein: intern bedeutet automatisch, kundenrelevant bedeutet Bestätigung durch die Teamleitung.
7. Der Adapter schreibt die Änderung und einen Audit-Kommentar in den Tracker zurück.
