# Start with a spreadsheet (solo & small teams)

🇬🇧 English · 🇩🇪 [Deutsch](de/spreadsheets.md)

In a one- to five-person company, agentic-pm isn't about coordinating a team. It takes things off your mind:

- **Hidden chains.** In a 100-row sheet it's easy to miss that Friday's client launch depends on a printer proof in row 63 that nobody has signed off. The dependency engine finds that chain and puts it in your morning email.
- **No cell-editing on a phone.** You keep the spreadsheet as your ledger. Later (Phase 3) you can update it by voice or WhatsApp instead of zooming into Excel on a phone.
- **Nothing to set up.** A local `.xlsx` or `.csv` plus a local model (Ollama) means no cloud accounts, no subscriptions, and your data stays on your machine.

## Try it in two minutes

```bash
uv sync
uv run agent-pm deps  --config examples/solo/team.yaml --date 2026-11-16
uv run agent-pm brief --config examples/solo/team.yaml --person me --date 2026-11-16
```

The [example sheet](../examples/solo/tasks.csv) is a small design studio: logo, then print files, then the printer's proof, then the flyers, then the client launch. It also has one "TBD" date on purpose, so you can see how problems are reported.

## Use your own sheet

```yaml
project:
  tracker: spreadsheet
  repo: studio                       # a name for this sheet
  leads: [me]                        # solo: that's you
  tracker_options:
    path: data/client-projects.xlsx  # .xlsx or .csv, relative to where you run agent-pm
    sheet: Tasks                     # .xlsx only (default: first sheet)
    header_row: 1                    # if there's a title above the header, use 2
    columns:                         # your column names; other columns stay untouched
      id: ID                         # required, a stable key such as T-101
      title: Task                    # required
      status: Status                 # required
      due: Due                       # optional: date cell, 2026-11-20 or 20.11.2026
      owner: Owner                   # optional: "Sam" or "Sam, Kim"
      depends_on: Depends On         # optional: "T-12, T-15" or "github:acme/api#42"
      estimate: Estimate             # optional: 4h / 2d / 1w, or a number
    status_map:                      # extra spellings; extend the built-in English and German ones
      blocked: ["waiting for client"]
    estimate_unit: hours             # what a plain number in Estimate means (hours or days)
```

Built-in statuses include, for example, *todo / offen*, *in progress / in Arbeit*, *review*, *waiting / wartet / blockiert*, *done / erledigt / fertig* and *cancelled / abgebrochen*.

To match owners to people, the agent compares the Owner cell with `tracker_login` (or the handle) in `team.yaml`, ignoring upper and lower case. If your sheet says "Mia Huber", set `tracker_login: Mia Huber`.

## It never fails silently

Spreadsheets are looser than issue trackers, so every row the agent can't use is **reported with its exact location**. It's never quietly dropped or guessed. Your brief then says so, in your language:

```
🧾 Nicht alles lesbar: studio (tasks.csv)
  • tasks.csv:Zeile 11: 'P-10' hat als Fälligkeit 'TBD', das ist kein Datum; ohne Termin geprüft
```

| Situation | What happens |
|-----------|--------------|
| Row has content but no ID, or reuses an ID | Skipped and reported. Row numbers are never used as IDs, because they shift when you sort or insert. |
| Unknown status (e.g. "maybe later") | Skipped and reported. A wrong guess could hide or invent a risk; add the word to `status_map`. |
| Due date or estimate not readable ("TBD") | Task kept, value reported |
| `Depends On` names a missing ID | Reported (the chain is broken there) |
| `Depends On` names another tracker (`github:acme/api#42`) | Reported as "can't be checked yet" until cross-tracker dependencies arrive (#59) |
| Formula without a calculated value (file saved by a script) | Reported; open and save the file in Excel or LibreOffice |
| A configured optional column isn't in the sheet | Reported once; set it to `null` if you don't track it |
| Empty rows at the bottom (even formatted ones) | Ignored quietly |
| File missing, wrong sheet, required column missing | Reported as an error; `agent-pm deps` exits with code 1 |

Technical details:
- `.xlsx` files are opened read-only, reading the stored formula results (`=WORKDAY(…)` works).
- CSV is read as UTF-8 with the byte-order mark Excel adds.
- The file is re-read whenever it changes on disk.

## Limits (for now)

- **Read-only.** The agent never writes to your file. Updating it by voice or WhatsApp is part of Phase 3.
- **No change events.** The sheet is read at each brief, digest or `deps` run.
- **One sheet per project.** Dependencies on GitHub or OpenProject items are reported but not yet checked (#59).
