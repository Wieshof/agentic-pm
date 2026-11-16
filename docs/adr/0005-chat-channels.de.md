# ADR-0005: Chat-Kanäle, Antwort-Zuordnung und Nachfassen

🇬🇧 [English](0005-chat-channels.md) · 🇩🇪 Deutsch

- **Status:** angenommen
- **Datum:** 2026-11-16

## Kontext

Phase 3 bringt den Agenten zu Menschen, die den Tracker nicht nutzen. Auf der Roadmap stand zuerst WhatsApp Business. Drei Dinge haben uns noch einmal hinschauen lassen:

- **WhatsApp Business** (Meta Cloud API) leitet Nachrichteninhalte über Meta. Es braucht eine verifizierte Geschäftsnummer, und jede Nachricht, die der Agent außerhalb eines 24-Stunden-Fensters beginnt, braucht eine von Meta vorab genehmigte Vorlage. Das passt nicht zu „lokal zuerst“ ([ADR-0001](0001-tech-stack-and-llm.de.md)) und lässt sich nicht in fünf Minuten ausprobieren.
- Chat hat kein `Reply-To` und keine `Message-ID`, der Agent soll aber zustandslos bleiben ([Datenmodell](../de/data-model.md)).
- Issue #14 wünschte sich „Antwortverhalten pro Person verfolgen“, was [ADR-0004](0004-people-data-boundaries.de.md) ausschließt.

## Entscheidung

1. **Zuerst Matrix und Signal, WhatsApp später.** Beide lassen sich selbst betreiben (ein Matrix-Homeserver, signal-cli), keins braucht ein Geschäftskonto, und Signal ist standardmäßig Ende-zu-Ende-verschlüsselt. Beide stecken hinter einer gemeinsamen `ChatTransport`-Schnittstelle, sodass WhatsApp (und Slack oder Teams) später dazukommen kann, ohne die Zuordnung anzufassen.
2. **Antwort-Zuordnung über ein Tag in der eigenen Nachricht des Agenten.** Jede Chat-Nachricht des Agenten zu einer Aufgabe endet mit einer kurzen Zeile wie `— #12`, `— #12 · due?` oder `— #12 · set status done · 3f9a0c21d4`. Eine Antwort bringt diesen Kontext zurück:
   - **Matrix:** Die zitierte Nachricht wird vom Homeserver geholt und zählt nur, wenn der Agent sie geschickt hat.
   - **Signal:** Der Autor des Zitats muss die Nummer des Agenten sein.

   Vorgeschlagene Änderungen sind mit `AGENT_PM_SIGNING_KEY` **HMAC-signiert**, weil ein Signal-Client ein gefälschtes Zitat schicken könnte. Eine Zuordnungstabelle gibt es nirgends.
3. **Bestätigungen im Chat zählen als Bestätigung der zuständigen Person, E-Mails nicht.** Matrix und Signal authentifizieren den Absender, E-Mails lassen sich fälschen. Ein „ja“ der zuständigen Person im Chat setzt deshalb eine Änderung mit mittlerem Risiko um (Status, interner Termin, Schätzung), über die bestehenden Berechtigungsstufen. Änderungen mit hoher Tragweite brauchen weiterhin den signierten Freigabe-Link einer Teamleitung. Eine Behauptung per E-Mail führt immer nur zu einer normalen Freigabeanfrage.
4. **Spracherkennung läuft lokal** (faster-whisper im Prozess oder ein whisper.cpp-Server). Audio und Transkripte bleiben im Arbeitsspeicher. Die in signal-cli gespeicherte Kopie einer Sprachnachricht wird nach der Bearbeitung gelöscht.
5. **Adaptives Nachfassen (#14) gilt pro Frage, nicht pro Person.** Bevor der Agent noch einmal nachfragt, zählt er die unbeantworteten Erinnerungen zu **einer offenen Frage**, anhand dessen, was im Gespräch und im Ticket sichtbar ist. Nach `escalate_after_ignored` Erinnerungen wechselt er auf den nächsten Kanal aus `prefer` (von der Person selbst festgelegt), und nicht dringende Fragen werden gebündelt. Pro Person wird nichts gespeichert, und einen Wert für „Antwortverhalten“ gibt es nicht. Das einzige Gedächtnis ist eine auditierte „gefragt“-Notiz im Ticket. Dringende Fragen kommen bei jedem Briefing, andere wöchentlich und gebündelt. Ist eine dringende Frage nach doppelt so vielen Erinnerungen noch offen, sieht die Teamleitung die Aufgabe, nicht die Person ([Chat](../de/chat.md#nachfassen-sanft-und-pro-frage)).
6. **Widerspruchs-Triangulation (#15) fragt nach, repariert nie selbst.** Eine Aussage wie „erledigt“, „hänge fest“ oder „angefangen“, die dem Tracker widerspricht, wird zu einer Frage an die Person, die es klären kann. Die Erkennung ist vorsichtig: Verneinungen, Fragen, „fast“ und gemischte Aussagen zählen nicht.

## Konsequenzen

- ✅ Chat funktioniert durchgehend auf Infrastruktur, die das Team selbst betreiben kann, ohne neue Datenbank.
- ✅ Derselbe `Router` bearbeitet E-Mail und Chat: Notizen, How-tos, Umfang, Triangulation.
- ✅ Eine gefälschte E-Mail oder ein gefälschtes Zitat kann kein Ticket ändern.
- ⚠️ Ende-zu-Ende-verschlüsselte Matrix-Räume brauchen Pantalaimon. Ohne nutzt Ihr unverschlüsselte Direktchats.
- ⚠️ Wer in Signal seine Nummer verbirgt, kann nicht `team.yaml` zugeordnet werden.
- ⚠️ Wer WhatsApp nutzt, wartet auf einen späteren Schritt. Die Schnittstelle ist dafür vorbereitet.
