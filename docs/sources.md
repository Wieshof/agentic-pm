# Several trackers: sources and seams

🇬🇧 English · 🇩🇪 [Deutsch](de/sources.md)

Some teams don't live in one tracker:

- **A freelancer with several clients.** One client uses GitHub, another a shared spreadsheet, and your time is what they share.
- **A company whose departments chose different tools.** Engineering works in GitHub, operations plans the launch in OpenProject.

agentic-pm doesn't copy tickets between them. It reads every tracker, gives each person one brief across all of them, and builds a bridge only where one side's date depends on the other side's work: the **seam**. The decision behind this is [ADR-0006](adr/0006-multiple-trackers-sources-and-seams.md).

## Set it up

Replace `project.tracker` and `project.repo` with `sources:`. Team-wide settings (leads, time zone, email, formality) stay under `project:`.

```yaml
project:
  leads: [lea]
  timezone: Europe/Vienna
sources:
  eng:  {tracker: github, project: acme/app, isolation: open, leads: [erik]}
  ops:  {tracker: openproject, project: launch-q1, base_url: "https://op.acme.de",
         ticket_language: de, isolation: open}
  client-a: {tracker: github, project: client-a/site}     # strict by default
people:
  lea:  {language: de, logins: {ops: "Lea Meier"}}
  erik: {logins: {eng: erik-dev}}
```

Then check what you wrote. `agent-pm validate` lists every source, who leads it, and who can see it:

```bash
uv run agent-pm validate
```

| Per source | Setting | Default |
|------------|---------|---------|
| Tracker and project | `tracker`, `project`, `base_url`, `tracker_options` | required |
| Language the agent writes in there | `ticket_language` | `en` |
| Isolation | `isolation: strict` or `open` | **`strict`** |
| Writing allowed | `allow_writes` | `false` |
| Leads | `leads` | `project.leads` |
| Credentials | environment `AGENT_PM_<SOURCE>_TOKEN`, e.g. `AGENT_PM_CLIENT_A_TOKEN` | the shared token |
| Webhook | `https://pm.your-org.com/webhooks/<source>` with `AGENT_PM_<SOURCE>_WEBHOOK_SECRET` | none |

Task references now carry their source: `eng#142`, `ops#57`. You see them that way in briefs, in chat (`— eng#142`) and in reply addresses (`pm+eng.142@…`), so a reply always finds the right tracker.

## Who sees what

- **A person with `logins:`** belongs to exactly those sources (plus any they lead).
- **A person without `logins:`** belongs to every `open` source. A `strict` source has to name its people.
- **Your own tasks** are in your brief from every source you belong to. That includes collisions between them, such as "acme#14 Review and beta#T-04 Launch are due on the same day, Thu 19 Nov 2026". The brief names tasks and dates, never a workload figure.
- **Leads** see team-level things (unowned work, risks, readiness, coverage) only for the sources they lead. The lead of client B never sees a word about client A.

## Isolation: strict and open

| | `strict` (clients) | `open` (departments) |
|-|--------------------|----------------------|
| Seams to other sources | not followed; leads get `ISOLATION_BOUNDARY_BLOCKED` | rolled up and shown |
| A direct link to another source | not followed, same warning | followed like any dependency |
| Written into this tracker | nothing about any other source | nothing about a `strict` source |

Every write is checked twice. It must act for its target's own source. Its text must not name another source it may not know about (`client-a#3`), or quote a task title from one. If it does, the write is refused. Tests try exactly these leaks.

## Seams

The waiting side says once what it waits for, in its own tracker. Put it in the task text:

````markdown
```agent-pm
waits_for: eng:milestone/v2.0
```
````

Or put it in a spreadsheet's `Depends On` column: `eng:milestone/v2.0`.

| Target | Means |
|--------|-------|
| `eng#142` | one item |
| `eng:milestone/v2.0` | every item in that milestone (OpenProject: version) |
| `eng:label/launch` | every item with that label |

The agent then works out the other side, without a language model and without copying anything:

- items done versus total
- a forecast from due dates, estimates and the dependency graph
- the buffer to the waiting task's date

Each side hears it in its own language:

- **Waiting side** (owner and leads): "ops#57 Launch campaign waits for eng:milestone/v2.0: 14/18 done, forecast Sat 28 Nov 2026, on track (3 days buffer)", or "… 2 days after its date. At risk."
- **Delivering side**: only when a business date is at risk, and only the owners of the items that decide it, plus the leads: "ops#57 Launch campaign on Tue 1 Dec 2026 waits for eng:milestone/v2.0; eng#31 and eng#35 decide it."

If items over there have no date, there's no honest forecast. The waiting side reads "no forecast yet, because 2 open items there have no date". Those items never disappear into the backlog: their owners (or that source's leads) get the usual question about the missing date, marked urgent.

**Suggestions:** if a ticket mentions `eng#142` or `eng:milestone/v2.0` but doesn't declare it, its owner gets one question: "Does it wait for it? Then add `waits_for: …`". Nothing is ever linked automatically.

## What comes later

- **Status lines in the waiting ticket** (`open` sources only), e.g. `eng:milestone/v2.0 · 14/18 done · forecast 2026-11-28 · 3 days buffer`. They come with the editable agent-pm block in step 4.0, so the line is updated in place instead of piling up comments. The write guard they'll go through is already in place.
- **Epics as seam targets**, once adapters can list an epic's items.
