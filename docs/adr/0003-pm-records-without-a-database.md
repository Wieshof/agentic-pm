# ADR-0003: PM records without a database

🇬🇧 English · 🇩🇪 [Deutsch](0003-pm-records-without-a-database.de.md)

- **Status:** accepted
- **Date:** 2026-11-12

## Context

A project manager keeps more than tasks: a RAID register (risks, assumptions, issues, dependencies), change requests, decisions, baselines, meeting notes and a working rhythm. The agent is stateless by design ([data model](../data-model.md)), so these records need a home in infrastructure the team already runs, where people can see and edit them without the agent.

## Decision

| Record | Primary home | Fallback |
|--------|--------------|----------|
| Risk, assumption, issue, external dependency | Tracker item with a native type if the tracker has one (Jira, Azure DevOps), otherwise label `type:risk` / `type:assumption` / `type:issue` / `type:dependency` | — |
| Change request | Tracker item `type:change-request` that links the work it would create | — |
| Decision | Tracker item `type:decision`, or Markdown in `.agent-pm/decisions/NNNN-title.md` | Repo file |
| Milestone | The tracker's milestone or epic | Item `type:milestone` |
| Baseline | Snapshot file `.agent-pm/baselines/YYYY-MM-DD.json` (due dates and estimates per task), committed via pull request | — |
| Meeting notes | Comment on the related item, or `.agent-pm/meetings/YYYY-MM-DD-topic.md` | Repo file |
| Operating cadence | `cadence:` section in `team.yaml` | — |

**Structured fields** (probability, impact, mitigation, review date) use the tracker's custom fields where they exist. Otherwise they go into a small fenced block in the description that people can also edit:

````markdown
```agent-pm
probability: 3   # 1-5
impact: 4        # 1-5
mitigation: Second supplier quoted by 2026-12-01
review: 2026-11-20
```
````

**Writes follow the permission tiers.**
- Proposing a risk or decision is low-risk and audited.
- Re-baselining and WBS drafts are high-impact, so they are drafts until a lead approves.
- New scope never becomes work items without an approved change request.

## Consequences

- ✅ Everything stays visible and editable in the tools the team already uses. It survives without the agent.
- ✅ Baselines and decisions get version history and review through Git.
- ⚠️ A label convention is weaker than native types. Mixed teams need to agree on the labels once (`agent-pm validate` will check them later).
- ⚠️ Reading the register means listing items with those labels on every run. That's fine at project scale, but heavier for large portfolios.
