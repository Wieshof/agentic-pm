# Languages

🇬🇧 English · 🇩🇪 [Deutsch](de/languages.md)

agentic-pm talks to every person in their own language, and writes into each tracker in that tracker's language. Adding a language is one file, no code.

| Language | Code | Status |
|----------|------|--------|
| English | `en` | ✅ complete, the reference |
| German | `de` | ✅ complete, informal "Du" |
| *your language* | | [add it](#add-a-language) |

The local model writes the optional brief summary in **any** language already. A language file adds everything else: briefs, questions, approval pages, how-tos, chat replies, and the words the agent understands in replies.

## Settings

```yaml
project:
  ticket_language: en        # what the agent writes into the tracker
  formality: informal        # informal (Du, tu, tú) | formal (Sie, vous, usted)
people:
  ana:
    language: pt-BR          # what the agent uses with Ana
```

- **Fallback, sentence by sentence.** `pt-BR` uses `pt-BR.yaml`, then `pt.yaml`, then English. A language that's only half translated still works.
- **`formality`** is one setting for the whole team. A language can provide formal variants of its texts. Where it doesn't (German today), the fixed texts stay informal and `agent-pm validate` says so. The model summary always follows the setting.
- **Reading uses every language at once.** A German "ja, Freitag" in an English team is understood, and so is a French "oui, vendredi" once French exists.

## What a language file contains

`src/agentic_pm/i18n/locales/<code>.yaml`:

| Section | What it's for |
|---------|---------------|
| `meta` | Name, review status (`native` or `draft`), date pattern (CLDR, e.g. `EEE d MMM y`) |
| `register` | Tone of the model summary for `informal` and `formal`, plus checks (e.g. German: never "Sie", always capitalized "Du") |
| `lexicon` | Words the agent understands: yes/no, "tomorrow", "next", time units, deadline and dependency words, status claims ("done", "stuck"), spreadsheet status names, stopwords for the language check |
| `texts` | Everything the agent says, by area: `messages`, `brief`, `digest`, `gaps`, `coverage`, `web`, `howto`, `channels`, `status` |
| `plurals` | Plural forms per [CLDR category](https://cldr.unicode.org/index/cldr-spec/plural-rules) (`one`, `few`, `many`, `other` …, plus an optional `zero`) |

Some things come from [CLDR](https://cldr.unicode.org/) through Babel for every language automatically: names of days and months (so "vendredi" works as an answer), date formatting, plural rules (Polish has three forms, Arabic six) and language names.

## Add a language

1. Copy `src/agentic_pm/i18n/locales/en.yaml` to `<code>.yaml`, e.g. `fr.yaml` or `pt-BR.yaml`.
2. Set `meta.name`, `meta.date`, and `meta.review: draft`.
3. Translate:
   - **`texts`:** keep every `{placeholder}` exactly as it is.
   - **`register`:** write the tone for the model in your language.
   - **`lexicon`:** the words people really type in a quick reply.

   You can start with a few areas; anything missing falls back to English.
4. For a formal variant, add `key@formal` next to `key`.
5. Run the checks. They verify that keys and placeholders match English and that the patterns compile:

   ```bash
   uv run pytest tests/test_i18n.py
   ```
6. Open a pull request. A native speaker reviews it, and then `review` becomes `native`.

**Tone:** warm, calm, short and never pushy. Read the English and German texts first; they set the voice.

## What stays in English and German

The **documentation** (this site and `docs/`) is written in English and German. The **product** speaks any language that has a file.
