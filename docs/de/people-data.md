# Was der Agent mit Daten über Dich macht

🇬🇧 [English](../people-data.md) · 🇩🇪 Deutsch

Eine verständliche Zusammenfassung für alle in einem Team, das agentic-pm nutzt. Die Gestaltungsregeln dahinter stehen in [ADR-0004](../adr/0004-people-data-boundaries.de.md).

## Was er verwendet

| Daten | Woher sie kommen | Wofür |
|-------|------------------|-------|
| Dein Name, Kanäle (E-Mail, Telefon, …), Sprache, Briefing-Zeit | Die Team-Datei `.agent-pm/team.yaml`, die Dein Team pflegt | Um Dich so zu erreichen, wie Du es möchtest |
| Dir zugewiesene Aufgaben mit Terminen, Schätzungen, Abhängigkeiten | Dein Tracker (z. B. GitHub), live gelesen | Briefings, Risikowarnungen, Terminkollisionen |
| Nachrichten, die Du dem Agenten schickst | Das Postfach des Agenten oder Dein Chat mit ihm (Matrix, Signal) | Um sie der richtigen Aufgabe zuzuordnen (How-to, Notiz) |
| Sprachnachrichten, die Du im Chat schickst | Dein Chat, in den Arbeitsspeicher geladen | Lokal in Text umgewandelt, danach wird das Audio verworfen |

## Was er nicht tut

- **Keine Bewertung von Menschen.** Keine Ranglisten, Auslastungs- oder Produktivitätszahlen.
- **Keine Historie über Dich.** Jede Prüfung schaut auf die Aufgaben, wie sie gerade sind. Terminkollisionen nennen Aufgaben („#12 und #31 sind beide Freitag fällig“), nicht die Leistung von Menschen.
- **Kein Erraten von Stimmungen.** Nachrichten werden nicht auf Stress, Stimmung oder Burnout untersucht.
- **Kein Training außerhalb.** Nachrichten verarbeitet standardmäßig ein Modell auf den eigenen Servern Deiner Organisation, und sie werden nie zum Training von Modellen verwendet.
- **Keine Reaktion auf Fremde.** E-Mails oder Chats von Absendern, die nicht in der Team-Datei stehen, werden ignoriert.
- **Keine Messung Deiner Antwortzeiten.** Bleibt eine Frage offen, zählt der Agent die Erinnerungen zu genau dieser Frage, nie, wie schnell *Du* normalerweise antwortest.

## Wie lange etwas aufbewahrt wird

- Der Agent selbst speichert **nichts dauerhaft**. Was er schreibt (How-tos, Notizen, Audit-Einträge), liegt in Deinem Tracker, wo Dein Team es sehen und bearbeiten kann.
- Kurzlebige Arbeitsdaten (z. B. um denselben Webhook nicht doppelt zu verarbeiten) liegen nur im Arbeitsspeicher und verschwinden beim Neustart.
- E-Mails bleiben im Postfach des Agenten, mit der üblichen Aufbewahrungsdauer Deiner Organisation.
- Chat: Signal-Nachrichten verlassen die Signal-Warteschlange, sobald der Agent sie gelesen hat, und Matrix-Nachrichten bleiben in Deinem Chat auf Deinem Homeserver. **Sprachnachrichten und ihre Transkripte speichert der Agent nie.** Übrig bleibt nur die fertige Notiz im Ticket.

## Was er schreibt und wann er vorher fragt

- **Automatisch, mit Audit-Vermerk:** Kommentare, How-tos und Labels, dazu eine kurze Notiz, wenn er zum ersten Mal nach einer fehlenden Angabe fragt („🙋 Sam nach einer fehlenden Angabe gefragt: kein Termin“). Daran erkennt er, wann er nachfassen soll. Woanders wird nichts über Dich gespeichert.
- **Erst mit Deinem OK:** Änderungen an Terminen oder Status Deiner Aufgabe. Du bekommst eine freundliche Mail mit Link oder im Chat eine Frage, die Du mit „ja“ oder „nein“ beantwortest. Nichts ändert sich, bevor Du entschieden hast.
- **Erst mit dem OK einer Teamleitung:** Kundentermine, neue Verantwortliche, Löschen.

## Deine Wahl

- Ändere Kanal, Sprache oder Briefing-Zeit in der Team-Datei, oder frag einfach Deine Teamleitung.
- Schalte Briefings oder Erinnerungen ab, indem Du auf irgendeine Mail des Agenten antwortest.
- Frag Deine Teamleitung, was in der Team-Datei über Dich steht.

Vor dem Rollout sollte Dein Team die Datenschutzbeauftragte bzw. den Datenschutzbeauftragten und, wo es einen gibt, den Betriebsrat einbeziehen.
