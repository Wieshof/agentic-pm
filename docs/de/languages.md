# Sprachen

🇬🇧 [English](../languages.md) · 🇩🇪 Deutsch

agentic-pm spricht mit jeder Person in ihrer eigenen Sprache und schreibt in jeden Tracker in dessen Sprache. Eine Sprache hinzuzufügen ist eine Datei, kein Code.

| Sprache | Code | Stand |
|---------|------|-------|
| Englisch | `en` | ✅ vollständig, die Referenz |
| Deutsch | `de` | ✅ vollständig, informelles „Du“ |
| *Deine Sprache* | | [ergänzen](#eine-sprache-ergänzen) |

Die optionale Zusammenfassung im Briefing schreibt das lokale Modell schon heute in **jeder** Sprache. Eine Sprachdatei ergänzt alles andere: Briefings, Fragen, Freigabeseiten, How-tos, Chat-Antworten und die Wörter, die der Agent in Antworten versteht.

## Einstellungen

```yaml
project:
  ticket_language: en        # was der Agent in den Tracker schreibt
  formality: informal        # informal (Du, tu, tú) | formal (Sie, vous, usted)
people:
  ana:
    language: pt-BR          # was der Agent mit Ana spricht
```

- **Rückfall Satz für Satz.** `pt-BR` nutzt `pt-BR.yaml`, dann `pt.yaml`, dann Englisch. Auch eine nur halb übersetzte Sprache funktioniert.
- **`formality`** ist eine Einstellung für das ganze Team. Eine Sprache kann formelle Varianten ihrer Texte mitbringen. Wo das fehlt (heute bei Deutsch), bleiben die festen Texte informell, und `agent-pm validate` sagt das. Die Zusammenfassung des Modells folgt immer der Einstellung.
- **Beim Lesen gelten alle Sprachen gleichzeitig.** Ein deutsches „ja, Freitag“ wird auch in einem englischen Team verstanden, und ein französisches „oui, vendredi“, sobald es Französisch gibt.

## Was in einer Sprachdatei steht

`src/agentic_pm/i18n/locales/<code>.yaml`:

| Abschnitt | Wofür |
|-----------|-------|
| `meta` | Name, Prüfstand (`native` oder `draft`), Datumsmuster (CLDR, z. B. `EEE, dd.MM.y`) |
| `register` | Ton der Zusammenfassung für `informal` und `formal`, plus Prüfungen (z. B. Deutsch: nie „Sie“, „Du“ immer groß) |
| `lexicon` | Wörter, die der Agent versteht: ja/nein, „morgen“, „nächste“, Zeiteinheiten, Wörter für Termine und Abhängigkeiten, Status-Aussagen („erledigt“, „hänge fest“), Statusnamen in Tabellen, Füllwörter für die Sprachprüfung |
| `texts` | Alles, was der Agent sagt, nach Bereichen: `messages`, `brief`, `digest`, `gaps`, `coverage`, `web`, `howto`, `channels`, `status` |
| `plurals` | Pluralformen nach [CLDR-Kategorie](https://cldr.unicode.org/index/cldr-spec/plural-rules) (`one`, `few`, `many`, `other` …, dazu optional `zero`) |

Manches liefert [CLDR](https://cldr.unicode.org/) über Babel für jede Sprache automatisch: Namen von Wochentagen und Monaten (damit „vendredi“ als Antwort funktioniert), Datumsformate, Pluralregeln (Polnisch hat drei Formen, Arabisch sechs) und Sprachnamen.

## Eine Sprache ergänzen

1. Kopier `src/agentic_pm/i18n/locales/en.yaml` nach `<code>.yaml`, z. B. `fr.yaml` oder `pt-BR.yaml`.
2. Setz `meta.name`, `meta.date` und `meta.review: draft`.
3. Übersetze:
   - **`texts`:** Lass jeden `{Platzhalter}` genau so, wie er ist.
   - **`register`:** Schreib den Ton für das Modell in Deiner Sprache.
   - **`lexicon`:** die Wörter, die Menschen in einer schnellen Antwort wirklich tippen.

   Du kannst mit ein paar Bereichen anfangen; was fehlt, kommt auf Englisch.
4. Für eine formelle Variante ergänzt Du `key@formal` neben `key`.
5. Führ die Prüfungen aus. Sie prüfen, dass Schlüssel und Platzhalter zum Englischen passen und dass die Muster gültig sind:

   ```bash
   uv run pytest tests/test_i18n.py
   ```
6. Öffne einen Pull Request. Eine Muttersprachlerin oder ein Muttersprachler prüft ihn, dann wird `review` zu `native`.

**Ton:** herzlich, ruhig, kurz und nie drängend. Lies zuerst die englischen und deutschen Texte, sie geben die Stimme vor.

## Was Englisch und Deutsch bleibt

Die **Dokumentation** (diese Seiten und `docs/`) gibt es auf Englisch und Deutsch. Das **Produkt** spricht jede Sprache, für die es eine Datei gibt.
