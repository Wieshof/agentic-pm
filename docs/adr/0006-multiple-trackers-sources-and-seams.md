# ADR-0006: Multiple trackers: sources and seams

🇬🇧 English · 🇩🇪 [Deutsch](0006-multiple-trackers-sources-and-seams.de.md)

- **Status:** accepted
- **Date:** 2026-11-17
- **Replaces:** the cross-tracker part of #59 (Phase 7), which moves to step 4.0a

## Context

So far one `team.yaml` means one tracker and one project. A link to another tracker (`github:acme/api#42`) is noticed, but not checked. Two common situations need more:

- **A one-person company with several clients.** Each client uses their own tracker: one has Jira, one GitHub, one a shared spreadsheet. The freelancer's time is the shared resource, and no single tracker can show that Client A's review and Client B's launch both need them on Thursday.
- **A company whose departments use different trackers on purpose.** Engineering tracks pull requests and bugs in GitHub; Operations or Product tracks deliverables and launch milestones in OpenProject. They work at different levels of detail.

Mirroring tickets between such tools is the usual answer, and it fails. Operations is flooded with technical noise, Engineering with business checklists, and two copies drift apart. What matters is the **seam**: the few places where one side's date depends on the other side's work.

## Decision

agentic-pm acts as a **translator and dependency bridge at the seam**, not as a sync tool. Nobody is forced into a shared board or vocabulary.

### 1. Several sources in one team file

```yaml
sources:
  eng:  {tracker: github,      project: acme/app,  ticket_language: en}
  ops:  {tracker: openproject, project: launch-q1, base_url: https://op.acme.de,
         ticket_language: de}
people:
  sam:
    logins: {eng: sam-dev, ops: "Sam Meier"}   # one person, one login per tracker
```

- Today's `project:` stays valid as the shorthand for a single source. Existing team files keep working unchanged.
- Each source has its own **credentials** (`AGENT_PM_<SOURCE>_TOKEN`, e.g. `AGENT_PM_ENG_TOKEN`), **webhook path** (`/webhooks/<source>`), **ticket language**, **write permission** (`allow_writes`) and **leads**.
- Task references carry the source (`eng#142`, `ops#57`). The dependency graph, capacity check, completeness check and briefs work on the union of all sources.

### 2. A seam is one dependency, declared where it's needed

The waiting side states once what it waits for, in its own tracker, in the editable block from [ADR-0003](0003-pm-records-without-a-database.md):

````markdown
```agent-pm
waits_for: eng:milestone/v2.0     # or eng#142, or eng:label/launch
```
````

- The other side can be **a group**: a milestone, a label or an epic. Operations depends on "v2.0", not on 18 pull requests.
- Spreadsheets use their existing `Depends On` column (`eng:milestone/v2.0`).
- The agent **suggests** a seam when ticket text mentions the other side ("waiting for the v2.0 release"), but a person confirms it. Nothing is linked automatically.
- **No item is ever copied** into another tracker.

### 3. Translation at the seam

The agent computes a **roll-up** of the group on the other side. It's deterministic, needs no language model, and gives:
- items done versus total
- items at risk
- a forecast date from due dates, estimates and the dependency graph

Each side then hears about the other once, in its own words:

| Who | What they see |
|-----|---------------|
| Waiting side (Ops) | "Launch campaign: engineering forecast 28 Nov, on track (3 days buffer)", or "at risk: forecast 3 Dec, 2 days after the launch" |
| Delivering side (Eng) | Only when a business date is at risk: "Launch campaign on 1 Dec waits on v2.0; #31 and #35 decide it" |

- Statuses are translated through each tracker's own status names. Technical items stay on their side; the other side sees a forecast, a buffer and a reason.
- Triangulation ([ADR-0005](0005-chat-channels.md)) and follow-up work across the seam the same way: a question goes to whoever owns the item, on their side, in their tracker's language.

### 4. Isolation between sources

Every source has an `isolation` setting:

| Isolation | Default for | What may cross the seam |
|-----------|-------------|-------------------------|
| `strict` | Client sources | **Nothing is written into this source about any other source**: no comments, task titles, names or dates. Cross-source information appears only in the private brief of the people who belong to both. |
| `open` | Internal departments | Seam roll-ups and short status lines may be written as comments on the waiting item, with an audit footer. |

- A freelancer's three clients are three strict sources: one brief for the freelancer, and no leak between clients.
- Departments of one company are usually open to each other.
- `agent-pm validate` refuses a seam that would need to write into a strict source.

### 5. People

- One person can have a login per source (`logins:`).
- Still no per-person history or scores ([ADR-0004](0004-people-data-boundaries.md)).
- Cross-source capacity collisions name tasks and dates, never utilisation.

## Consequences

- ✅ Departments keep their tools, granularity and vocabulary. The agent bridges only where one side's date depends on the other's work.
- ✅ A freelancer gets one view across all clients, including collisions no single client could see, with no data crossing between clients.
- ✅ No copies to drift apart; each tracker stays the source of truth for its own items.
- ✅ The read-only part (one brief, cross-tracker dependencies, collisions) works with every adapter we have today.
- ⚠️ Roll-up forecasts are only as good as the delivering side's due dates and estimates. The completeness checks ask for what's missing.
- ⚠️ Groups as seam targets (milestone, label, epic) need each adapter to list a group's items. Adapters that can't do this support single-item seams only.
- ⚠️ `team.yaml` gets a new shape. `project:` keeps working, and `agent-pm validate` explains how to move to `sources:`.

## Implementation

Step **4.0a** of the [Phase 4 plan](../plan-phase-4.md), before the 4.0 foundation:

1. `sources:` config, per-source credentials, webhooks and ticket language; `project:` stays as shorthand.
2. Multi-source dependency graph, briefs, capacity and completeness, all read-only.
3. Seams: `waits_for:` in the agent-pm block and in spreadsheet cells, group roll-ups (milestone, label), forecast and buffer, plus seam lines in both sides' briefs.
4. Isolation: `strict` / `open`, enforced in every write path and in the guards, with tests that try to leak data.
5. Seam suggestions from ticket text (confirmed by a person).
