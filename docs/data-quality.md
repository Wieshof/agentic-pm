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

## Backlog, and what never disappears into it

Every real tracker has open items nobody has planned yet: ideas, roadmap items, someday maybes. Asking "who takes it?" about each of them every morning would be noise. So an open item with **no owner, no due date, no progress and nothing depending on it** counts as backlog. It isn't asked about, just counted once: "46 more in the backlog, not planned yet". That line appears in the lead's readiness section and in the weekly digest.

An item is **never** backlog when something says it matters:

| Signal | Example | What leads see |
|--------|---------|----------------|
| Other work is linked as waiting on it | #201 depends on #200 | "#200 Payment API contract has no owner, but other work is waiting for it: #201 Checkout page. Who takes it?" |
| Another ticket's text names it | #203 says "waiting on #204" | the same, naming #203 |
| An urgent label | `blocker`, `critical`, `urgent`, `P0`, `P1`, `sev1`, `security`, `hotfix`, `priority: high`, `dringend`, `kritisch` … | "#202 Prod login broken is marked "blocker" but has no owner. Who takes it?" |

- **These come first.** "Who takes it?" questions lead the list, ordered by how much waits on them, then urgent labels, then the nearest due date. A blocker never ends up behind "… and 41 more".
- **They're asked every day** instead of weekly ([follow-up](chat.md#follow-up-gentle-per-question)).
- **Labels are compared loosely:** `Priority: High`, `priority/high` and `priority-high` are the same label. A plain `bug` doesn't count as urgent on its own.
- **More labels:** add your team's own with `completeness.urgent_labels`. Each language file brings its own list too ([languages](languages.md)).
- **No backlog at all:** `completeness.backlog: check` asks about every open item again.

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
  urgent_labels: [must-have]    # your own urgent labels, on top of blocker, P0, critical, …
  backlog: separate             # or: check (ask about every open item)
```

Checks a tracker can't support are skipped. A tracker without due dates is never asked for them.

`uv run agent-pm deps` prints the readiness ratio and every gap. Questions follow up gently: urgent ones daily, the rest weekly ([follow-up](chat.md#follow-up-gentle-per-question)). People with a [chat brief](chat.md#briefs-in-chat) get each urgent question as its own chat message. They can just reply ("Friday", "2 days"), and after a quick "yes" the ticket is updated.
