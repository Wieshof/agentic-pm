# Zustandsloses Datenmodell

🇬🇧 [English](../data-model.md) · 🇩🇪 Deutsch

Alle Daten, die der Agent braucht, können in Infrastruktur liegen, die das Unternehmen bereits betreibt. Der Agent selbst hält **keinen dauerhaften Aufgabenzustand**.

## Aufgaben, Termine & Abhängigkeiten → bestehender Tracker

Trifft ein Ereignis ein (ein Git-Webhook, eine E-Mail oder ein Anruf), ruft der Agent den aktuellen Kontext über die API des Trackers ab, wertet ihn aus und schreibt den neuen Status oder Blocker-Tags direkt zurück.

## Präferenzen („Drucker-Profile“) → Repo-Konfiguration oder SSO

Präferenzen wie „morgens E-Mail“ oder „nachmittags Anruf“ stehen in einer einzigen, gut lesbaren Datei im Repository (`.agent-pm/team.yaml`) oder in Verzeichnisattributen (Microsoft Entra ID / Google Workspace). Jede Person kann ihre Präferenz selbst ändern, durch Bearbeiten der Datei oder per Nachricht an den Agenten.

Siehe [`.agent-pm/team.example.yaml`](../../.agent-pm/team.example.yaml).

## How-to-Dokus & Audit-Logs → Ticketkommentare & Markdown

Es gibt keine separate Datenbank und kein Wiki. Der Agent hängt strukturiertes Markdown an das Ticket an oder committet es nach `/docs` im Repository. Audit-Einträge sind Ticketkommentare mit maschinenlesbarer Fußzeile.

## Zuordnung Gespräch → Ticket → Transport-Tagging

Es braucht keine Nachschlagetabelle, um zu wissen, welche Antwort zu welcher Aufgabe gehört.

| Kanal | Mechanismus |
|-------|-------------|
| E-Mail | Dynamische Plus-Adressierung (`pm+repo-task142@yourdomain.com`) oder `Message-ID`- / `In-Reply-To`-Header |
| WhatsApp | Antwortkontext-Metadaten von WhatsApp Business oder ein kurzes Referenz-Tag in der Nachricht |
| Sprache | Das Transkript liegt nur im Arbeitsspeicher der Anrufsitzung, für die 2–3 Minuten des Gesprächs. Strukturierte Updates werden beim Auflegen in den Tracker geschrieben, danach wird das Transkript verworfen. |

## Was der Agent *doch* vorhält (nur flüchtig / betrieblich)

- Kurzlebige Caches mit TTL, ohne Rolle als Quelle der Wahrheit
- Zustell- und Wiederholungswarteschlangen für ausgehende Nachrichten
- Reaktionszähler für die adaptive Taktung. Diese können auch in `team.yaml` oder SSO-Attributen abgelegt werden, wenn vollständige Zustandslosigkeit gefordert ist.

## Webhook-Eingang: keine Schleifen, keine Stürme

Jede Änderung des Agenten (ein Kommentar, ein How-to-Abschnitt) lässt den Tracker sofort einen Webhook zurückschicken. `agentic_pm.ingress.WebhookGate` verwirft, ganz ohne Datenbank:

| Verworfen | So wird es erkannt |
|-----------|--------------------|
| Wiederholungen derselben Zustellung | Zustell-ID (z. B. `X-GitHub-Delivery`), 1 h gemerkt |
| Eigene Änderungen des Agenten | Absender steht in `project.agent_accounts`, oder der Text trägt die Audit-Fußzeile |
| Stürme zu einem Ticket | Gleiches Ticket + gleiche Ereignisart innerhalb von 10 s |

Das Verwerfen ist sicher, weil der Agent bei jedem zugelassenen Ereignis ohnehin das aktuelle Ticket live abruft. Der Speicher liegt nur im Prozess und ist begrenzt; nach einem Neustart beginnt er einfach leer. Bei mehreren Agent-Prozessen leite die Webhooks eines Repositorys an denselben Prozess (oder nimm gelegentlich eine doppelte Nachfrage in Kauf).

## Sprachen: Menschen vs. Tickets

Zwei getrennte Einstellungen in `team.yaml`:

- `people.<handle>.language` ist die Sprache, in der der Agent mit dieser Person **spricht** (Briefings, Chats, Anrufe).
- `project.ticket_language` ist die Sprache, in der der Agent in den Tracker **schreibt**.

So kann eine Entwicklerin ihren Fix per deutscher Sprachnachricht erklären, während der Agent das How-to auf Englisch ins GitHub-Issue schreibt. Jeder ISO-Code funktioniert (`en`, `de`, `pt-BR`). Briefing-Vorlagen gibt es bisher auf Englisch und Deutsch; andere Sprachen bekommen englische Vorlagen mit einer Zusammenfassung in ihrer eigenen Sprache.
