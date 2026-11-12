# Core Agentic Workflows

🇬🇧 English · 🇩🇪 [Deutsch](de/workflows.md)

To work like a human project manager, the system runs five autonomous loops in the background.

## 1. Proactive Dependency Resolution

**Trigger:** an estimate changes, a due date moves or a new sub-requirement appears.

The agent walks the dependency graph. If Task B depends on Task A and A slips two days, it notifies B's owner right away on their preferred channel and **proposes adjusted schedules before idle time occurs**.

- Inputs: tracker relations, estimates, assignee calendars (optional)
- Output: notification + proposed reschedule (approval needed if client-facing)
- KPI: mean time to surface a blocker < 2 h

## 2. Inconsistency Triangulation

**Trigger:** two sources disagree, e.g. "feature complete" in WhatsApp while the linked PR is still unreviewed.

The agent pinpoints the gap, works out **who holds the missing context**, and starts a targeted **micro-interview** (email, chat or a 60-second call) to set the record straight.

- Sources: chat statements, tracker status, PR/MR review & CI state, commits
- Output: reconciled status + audit comment explaining the resolution

## 3. Frictionless "How-To" Documentation

**Trigger:** a contributor explains a fix in a call, voice note or chat. For example: *"I fixed the auth timeout by increasing the Redis pool size and updating the retry header."*

The agent turns this into clean Markdown and appends it to the ticket:

```markdown
### How it was solved
- **Problem:** Auth requests timing out under load
- **Root cause:** Redis connection pool exhausted
- **Fix:** Increased Redis pool size; updated retry header
- **Verified by:** <owner>, <date>
- **Source:** voice note (transcribed)
```

## 4. Adaptive Follow-Up Cadence

The agent tracks how responsive each person is, per channel, instead of sending the same generic reminders to everyone.

- A **Talker** who ignores three emails gets a short outbound voice check-in instead.
- A **Reader** who wants no interruptions gets non-urgent questions bundled into the morning email brief.
- Urgency, quiet hours and channel preferences come from `team.yaml`.

## 5. Status Updates & Scrum Artefacts

Regular status updates go out **by email or as a spoken briefing**. Listeners can **ask follow-up questions and clarifications** during the briefing.

The agent can also keep Scrum artefacts up to date from live tracker data:

| Artefact | How the agent supports it |
|----------|---------------------------|
| Product Backlog | Flags stale / unestimated items, proposes refinement questions |
| Sprint Backlog | Tracks commitment vs. progress, surfaces at-risk items |
| Increment / Definition of Done | Checks DoD signals (PR merged, tests green, docs attached) |
| Daily Scrum | Async stand-up via each person's channel, summary to the team |
| Sprint Review / Retro | Pre-drafted review notes and retro prompts from sprint data |
| Burndown | Generated in briefings rather than a separate dashboard |

> Open question: should the agent *remodel* artefacts (e.g. propose re-slicing stories), or only report on them? Tracked in the roadmap as a Phase 4 item.
