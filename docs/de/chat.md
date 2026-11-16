# Chat: Matrix und Signal (Phase 3)

🇬🇧 [English](../chat.md) · 🇩🇪 Deutsch

Wer nicht im Tracker lebt, arbeitet mit dem Agenten in einer Chat-App, die er schon nutzt. Dort gibt es ein kurzes Briefing, Fragen kommen einzeln, Sprachnachrichten gehen auch, und eine Änderung bestätigst Du einfach mit „ja“. Ein Tracker-Konto braucht es dafür nicht.

Warum zuerst Matrix und Signal und nicht WhatsApp, steht in [ADR-0005](../adr/0005-chat-channels.de.md).

## Was Du schicken kannst

| Du schickst | Was passiert |
|-------------|--------------|
| Eine Antwort auf eine Nachricht des Agenten | Landet bei genau dieser Aufgabe, ohne Nummer |
| Freitext mit einer Aufgabennummer, „#12 Review läuft“ | Wird als Notiz an #12 gehängt, wie eine Antwort per E-Mail |
| Eine Sprachnachricht | Wird lokal transkribiert und dann wie Text behandelt. Die Notiz im Ticket ist mit „(Sprachnachricht)“ markiert. |
| „Freitag“ auf „Bis wann soll es fertig sein?“ | Der Agent fragt zurück: „Soll ich den Termin von #12 auf Fr., 20.11.2026 setzen?“ |
| „ja“ auf diese Frage | Die Änderung wird gemacht, wenn die Aufgabe Dir gehört. Sonst bekommt die zuständige Person eine normale Freigabeanfrage. |
| „#12 ist erledigt“, während #12 noch offen ist | Siehe [Triangulation](#triangulation-wenn-es-nicht-zusammenpasst) unten |

Nachrichten von Personen, die nicht in `team.yaml` stehen, werden ignoriert. Eine Matrix-Einladung von Unbekannten nimmt der Agent nie an.

## Briefings im Chat

Mit `brief.format: chat` schickt der Agent zur Briefing-Zeit ein kurzes Briefing in Deinen Chat. Danach kommt **jede fehlende Angabe als eigene Frage** (höchstens `completeness.max_per_brief`), damit Du jede mit einer einzigen Antwort erledigen kannst:

```
#12 Fix auth timeout hat keinen Termin, deshalb kann ich nicht sagen, ob es eng wird.
Bis wann soll es fertig sein?

— #12 · due?
```

Die letzte Zeile ist das **Tag**. Wenn Du antwortest, erkennt der Agent daran, um welche Aufgabe es geht und welche Art Antwort er erwartet. Dafür muss nichts gespeichert werden ([Datenmodell](data-model.md#zuordnung-gespräch--ticket--transport-tagging)). An einem ruhigen Tag kommt gar nichts.

## Triangulation: wenn es nicht zusammenpasst

Wenn eine Nachricht oder ein frischer Ticket-Kommentar etwas anderes sagt als der Tracker, fragt der Agent **einmal** nach. Beispiele: „erledigt“, obwohl die Aufgabe offen ist; „ich hänge fest“, obwohl sie in Arbeit ist; „angefangen“, obwohl sie noch offen ist.

| Wer es sagt | Wo | Was der Agent macht |
|-------------|----|---------------------|
| Die zuständige Person | Matrix / Signal | „Du hast „… erledigt“ geschrieben, aber #12 steht noch auf in Arbeit. Soll ich es auf erledigt setzen?“ Antwort: ja oder nein. |
| Jemand anderes | Chat | Fragt die zuständige Person über den normalen Freigabe-Weg und sagt dem Absender, dass gefragt wurde |
| Egal wer | E-Mail | Wie „jemand anderes“: E-Mails lassen sich fälschen, deshalb zählen sie nie als Bestätigung der zuständigen Person |
| Ein Ticket-Kommentar (letzte 24 h) | Tracker | Steht im Briefing der zuständigen Person, im Chat zusätzlich als einzelne Ja/Nein-Frage |

Die Regeln sind absichtlich vorsichtig. „Noch nicht fertig“, „fast fertig“, „ist es erledigt?“ und „API fertig, aber bei der UI hänge ich fest“ zählen nicht. Ohne ein „ja“ oder eine Freigabe ändert der Agent nie einen Status.

## Matrix einrichten

1. Leg auf Deinem Homeserver ein Konto für den Agenten an, z. B. `@agent-pm:example.org`, und hol Dir dafür ein Access-Token.
2. Trag die Matrix-ID jeder Person in `team.yaml` ein: `channels: { matrix: "@sam:example.org" }`.
3. Setz die Umgebungsvariablen:

   | Variable | Beispiel |
   |----------|----------|
   | `AGENT_PM_MATRIX_HOMESERVER` | `https://matrix.example.org` |
   | `AGENT_PM_MATRIX_USER` | `@agent-pm:example.org` |
   | `AGENT_PM_MATRIX_TOKEN` | das Access-Token des Agenten-Kontos |

4. Jede Person startet einen Direktchat mit dem Agenten, oder der Agent öffnet einen, wenn er zum ersten Mal schreibt.

**Verschlüsselung.** Der Agent spricht einfaches HTTP mit dem Homeserver und kann Ende-zu-Ende-verschlüsselte Räume nicht entschlüsseln. Nutz einen **unverschlüsselten Direktchat** mit dem Agenten auf einem Homeserver, dem Du vertraust, oder betreib den Agenten hinter [Pantalaimon](https://github.com/matrix-org/pantalaimon), das E2EE für ihn übernimmt. In einem verschlüsselten Raum antwortet der Agent, dass er die Nachricht nicht lesen kann, statt still zu bleiben.

**Nichts zu merken.** Was der Agent schon bearbeitet hat, ist seine eigene Lesemarke auf dem Homeserver, dieselbe Idee wie „gelesen“ im IMAP-Postfach. Beim allerersten Start markiert er alles als gelesen, statt auf alte Nachrichten zu antworten.

## Signal einrichten

1. Betreib [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) im Modus `normal` oder `native` (nicht `json-rpc`) und registrier oder verknüpf eine Nummer für den Agenten.
2. Trag die Nummer jeder Person in `team.yaml` ein: `channels: { signal: "+43 660 1234567" }`.
3. Setz `AGENT_PM_SIGNAL_API_URL` (z. B. `http://localhost:8080`) und `AGENT_PM_SIGNAL_NUMBER`.

Signal ist Ende-zu-Ende-verschlüsselt, und signal-cli hält die Schlüssel auf Deinem Rechner. Beim Lesen wird eine Nachricht aus der Signal-Warteschlange genommen, der Agent speichert also nichts. Sprachnachrichten werden in den Arbeitsspeicher geladen, und die Kopie in signal-cli wird gelöscht, sobald die Nachricht bearbeitet ist. Gruppenchats werden ignoriert, es zählen nur Direktchats.

Wer in den Signal-Einstellungen seine Nummer verbirgt, kann vom Agenten nicht `team.yaml` zugeordnet werden. Dann muss die Nummer für Kontakte sichtbar sein.

## Sprachnachrichten

Die Transkription läuft **lokal**. Sie ist aus, bis Du eine Engine wählst:

```yaml
speech:
  engine: faster-whisper   # uv sync --extra voice
  model: small             # tiny | base | small | medium | large-v3
# oder
speech:
  engine: whisper-cpp
  url: http://localhost:8080/inference   # Dein whisper.cpp-Server
```

Audio und Transkript bleiben im Arbeitsspeicher und werden vom Agenten nie auf die Festplatte geschrieben. Gespeichert wird nur die fertige Notiz, als Kommentar im Ticket. Ohne Engine bittet der Agent freundlich darum, es kurz zu schreiben.

## Welchen Kanal der Agent nutzt

Jede Person kann eine Reihenfolge festlegen: `prefer: [signal, email]`. Ohne Angabe bekommen Leser zuerst E-Mail, alle anderen zuerst den Chat. Antworten gehen immer über den Kanal zurück, aus dem die Nachricht kam. Freigabe-Links gehen genauso raus, behandle sie also wie jede andere private Nachricht.

## Betrieb

`uv run agent-pm run` fragt jeden eingerichteten Chat alle `cadence.chat_poll_seconds` ab (Standard 15). Für eine einzelne Runde von Hand: `uv run agent-pm run --once chat`.

Für Bestätigungen im Chat braucht der Agent `AGENT_PM_SIGNING_KEY` und `project.allow_writes: true`. Ohne beides legt er weiterhin Notizen an, schlägt aber nie eine Änderung vor.
