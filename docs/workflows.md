# Core Agentic Workflows

🇬🇧 English · 🇩🇪 [Deutsch](de/workflows.md)

To work like a human project manager, the agent runs five loops. This page describes each loop and says honestly how much of it is built today.

✅ built and tested · 🗓️ planned (see the [roadmap](roadmap.md)) · 🚫 deliberately not

## 1. Proactive Dependency Resolution

**Trigger:** an estimate changes, a due date moves or a new sub-requirement appears.

The agent walks the dependency graph. If Task B depends on Task A and A slips two days, B's owner hears about it and gets **a proposed new date before idle time occurs**.

| | What | |
|-|------|-|
| ✅ | Risks along the whole chain (A → B → C), with a proposed new date, in the morning brief and the lead's end-of-day note | [data quality](data-quality.md) |
| ✅ | Dependencies across trackers, between departments or clients | [several trackers](sources.md) |
| 🗓️ | An instant message the moment a date moves (today: the next brief) | not scheduled yet |
| 🗓️ | Assignee calendars as an input | deferred |

- Output: a notification and a proposed date. Changing the date itself needs an approval (client-facing dates: a lead's).
- KPI target (not yet measured in a pilot): a blocker is visible within 2 hours.

## 2. Inconsistency Triangulation

**Trigger:** two sources disagree, e.g. "done" in a chat reply while the ticket is still open.

The agent pinpoints the gap, works out **who holds the missing context**, and asks that person **one short question** to set the record straight.

| | What | |
|-|------|-|
| ✅ | Status claims in email and chat ("done", "stuck") compared with the tracker; the owner confirms with "yes", others go through an approval | [chat](chat.md) |
| ✅ | A latest ticket comment that claims another status, shown in the owner's brief | |
| 🗓️ | Pull request review and CI state as sources | not scheduled yet |
| 🗓️ | A 60-second phone call as the way to ask | Phase 3, [#13](https://github.com/Wieshof/agentic-pm/issues/13) |

- Output: the corrected status, with an audit comment explaining who confirmed it.

## 3. Frictionless "How-To" Documentation

**Trigger:** a contributor explains a fix by email, in a chat or in a voice note. For example: *"I fixed the auth timeout by increasing the Redis pool size and updating the retry header."*

The agent turns this into clean Markdown and appends it to the ticket. The explanation can come in any language; the how-to is written in the tracker's `ticket_language` (e.g. a German voice note becomes an English how-to):

```markdown
### How it was solved
- **Problem:** Auth requests timing out under load
- **Root cause:** Redis connection pool exhausted
- **Fix:** Increased Redis pool size; updated retry header
- **Verified by:** <owner>, <date>
- **Source:** voice note (transcribed)
```

| | What |
|-|------|
| ✅ | From email replies and from Matrix or Signal messages, including voice notes (transcribed locally) |
| ✅ | When a task is closed, the owner is asked once for a short how-to |
| 🗓️ | From phone calls ([#13](https://github.com/Wieshof/agentic-pm/issues/13)) |

## 4. Adaptive Follow-Up Cadence

The agent adapts **per open question, never per person** ([ADR-0005](adr/0005-chat-channels.md)). It keeps no history about anyone and computes no responsiveness score ([ADR-0004](adr/0004-people-data-boundaries.md)).

| | What |
|-|------|
| ✅ | **The only memory is the ticket.** When the agent first asks (e.g. for a due date), it leaves one short note on the ticket. A reply, or any comment by the people asked, counts as an answer. |
| ✅ | **Urgent questions** (no owner, a blocker, other work waiting) come in every brief. Everything else is bundled and asked once a week. |
| ✅ | **Another channel:** after a few unanswered nudges *for that question* (`escalate_after_ignored`, default 3), the agent also tries the next channel the person listed under `prefer`. |
| ✅ | **Leads see the task, not the person:** "#12 still has no due date", never "Sam didn't answer". |
| ✅ | Quiet hours, interruption preferences and channels come from each person's own entry in `team.yaml`. |
| 🗓️ | A phone call as one of those channels ([#13](https://github.com/Wieshof/agentic-pm/issues/13)) |
| 🚫 | Tracking how fast someone answers, or comparing people |

## 5. Status Updates & Scrum Artefacts

Regular status updates go out **by email or in chat**, at the time each person chose: a morning brief for everyone, an end-of-day note and a weekly digest for leads.

| | What |
|-|------|
| ✅ | Morning brief (email or chat), end-of-day note, weekly digest |
| 🗓️ | Spoken briefings where listeners can ask follow-up questions ([#13](https://github.com/Wieshof/agentic-pm/issues/13)) |
| 🗓️ | Scrum artefacts, below (Phase 5) |

Planned for Phase 5: keeping Scrum artefacts up to date from live tracker data.

| Artefact | How the agent will support it |
|----------|-------------------------------|
| Product Backlog | Flags stale / unestimated items, proposes refinement questions |
| Sprint Backlog | Tracks commitment vs. progress, surfaces at-risk items |
| Increment / Definition of Done | Checks DoD signals (PR merged, tests green, docs attached) |
| Daily Scrum | Async stand-up via each person's channel, summary to the team |
| Sprint Review / Retro | Pre-drafted review notes and retro prompts from sprint data |
| Burndown | Generated in briefings rather than a separate dashboard |

> Open question: should the agent *remodel* artefacts (e.g. propose re-slicing stories), or only report on them? Tracked in the roadmap as a Phase 5 item.
