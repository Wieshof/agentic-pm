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
