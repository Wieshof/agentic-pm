# Data quality: garbage in, garbage out

🇬🇧 English · 🇩🇪 [Deutsch](de/data-quality.md)

The agent's checks are only as good as the tickets behind them:
- A task **without an owner** appears in nobody's brief.
- A task **without a due date** is left out of the risk and collision checks.
- A task **without an estimate** is counted as one day.

So before every brief, the agent checks the open tasks and **asks the right person one short question** per gap. It runs in read-only mode, needs no model, and never changes a ticket on its own.

## What it checks

| Gap | What it means | Who is asked |
|-----|---------------|--------------|
| No owner | The task appears in nobody's brief | Leads (or `completeness.triage`) |
| Owner not in the team file | They never get a brief | Leads |
| No due date | Not part of risk or collision checks | The owner |
| Due date only in the text ("deadline 2026-11-25") | Suggested, never set automatically | The owner |
| No estimate (off by default) | Counted as one day | The owner |
| Blocked, but nothing linked and no explanation | Nobody knows what it's waiting for | The owner |
| Blocked, but its blocker is already done | It may be able to continue | The owner |
| Text says "waiting on #14", but nothing is linked | Dependency checks can't see it | The owner |

In the brief, it looks like this:

```
🧩 Hier fehlen noch ein paar Angaben
  • #P-3 Client picks logo ist als blockiert markiert, aber #P-2 ist schon erledigt.
    Kann es weitergehen, oder wartet es noch auf etwas anderes?
```

Leads also see a **readiness ratio** for the team, and the weekly digest shows it too:

```
📊 Data readiness
  • 75% of 8 open tasks have everything the checks need
  • missing: 1 blocked by something already done, 1 without due date
```

## Careful with free text

- **Ticket text is untrusted.** Phrases like "waiting on #14" or "deadline 2026-11-25" only ever become a **question** to the owner. Nothing is linked or changed automatically. Only the short matched phrase is quoted, never the rest of the text.
- **Only real task references count:** `#14`, `#P-7`, `T-08`, `APP-12`, `studio:T-08` or `github:acme/api#42`. Dates ("after 2026-11-25") and words ("after review", "blocked by the client") are ignored.
- **A date only counts as a due date** when it follows a word like *due, deadline, by, until, target, bis, fällig, Termin, Abgabe* or *spätestens*. "Created 2026-01-01" doesn't count.
- **No noise:** references to tasks that are done or unknown are skipped. Values a spreadsheet couldn't read ("TBD") are reported once, as a [coverage warning](spreadsheets.md#it-never-fails-silently), not again as a gap.

## People, not scores

Gaps go to the person who can fix them. Leads see unowned work and team-level numbers, **never "Sam has 7 incomplete tickets"**, because that would be a per-person score ([ADR-0004](adr/0004-people-data-boundaries.md)).

## Configure

```yaml
completeness:
  require_owner: true
  require_due: true
  require_estimate: false       # turn on if your team estimates
  require_blocker_reason: true
  detect_hints: true            # suggest links for "waiting on #14" & co.
  triage: [alex]                # who gets unowned tasks (default: the leads)
  max_per_brief: 5              # at most this many questions per person and day
```

Checks a tracker can't support are skipped. A tracker without due dates is never asked for them.

`uv run agent-pm deps` prints the readiness ratio and every gap. Later, in Phase 3, the same questions will go out as single WhatsApp or voice prompts, and an answer can update the ticket after confirmation.
