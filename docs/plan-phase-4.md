# Phase 4 plan: Plan & Control

🇬🇧 English · 🇩🇪 [Deutsch](de/plan-phase-4.md)

- **Status:** agreed, not started
- **Date:** 2026-11-17
- **Issues:** #48 #49 #50 #51 #52 #54 #55, the cross-tracker part of #59 (#53 deferred)

Phases 1–3 let the agent read, warn, ask and update. Phase 4 lets it **keep the project's records**: a plan drafted from a goal, risks, change requests, decisions, baselines and a monthly health check. All of these are records the team can see and edit without the agent ([ADR-0003](adr/0003-pm-records-without-a-database.md)).

## Decisions

| Question | Decision |
|----------|----------|
| Where do records live? | **In the tracker**, the single source of truth. The interface is provisioned for every tracker; we build it where it's needed (GitHub now). |
| Spreadsheet users? | **Extra sheets** in the same workbook (`Plan draft`, `RAID`, `Changes`, `Decisions`) that the agent owns. The task sheet itself is only ever appended to, after approval. |
| Files in the repo (baselines, decisions, meeting notes)? | **Pull request**, so a person reviews and merges. |
| First feature after the foundation? | **WBS generator (#48)**: a goal becomes a draft plan for approval. |
| Calendar (#53)? | **Deferred.** It may come at the end of Phase 4 or in Phase 6. |
| Several trackers (clients, departments)? | **Sources and seams** ([ADR-0006](adr/0006-multiple-trackers-sources-and-seams.md)), built first as step 4.0a. Records can then sit at the seam between departments. |
| Asana? | A good fit (native milestones, approval tasks and custom fields; #30). The foundation is designed so Asana can be the next writing tracker. |

## Steps

### 4.0a Several trackers: sources and seams ([ADR-0006](adr/0006-multiple-trackers-sources-and-seams.md))

The agent works across several trackers without mirroring tickets. It's a translator and dependency bridge at the seam between departments, or between clients.

- **`sources:`** in `team.yaml`: one entry per tracker, with its own credentials, webhook path, ticket language, write permission and leads. `project:` keeps working as the one-source shorthand. One person can have a login per source (`logins:`).
- **One picture across sources:** dependency graph, briefs, capacity collisions and completeness work on all sources together, read-only.
- **Seams:** the waiting side declares `waits_for: eng:milestone/v2.0` (or one item, or a label) in its own tracker or spreadsheet cell.
  - The agent rolls up the other side deterministically: done versus total, at risk, forecast, buffer.
  - Each side hears about it once, in its own words. Operations sees "engineering forecast 28 Nov, 3 days buffer"; Engineering hears only when a business date is at risk, and which issues decide it.
- **Isolation:** `strict` (the default for clients) means nothing about another source is ever written into it. `open` (departments) allows short seam status lines as audited comments. There are tests that try to leak data.
- **Suggestions:** ticket text that mentions the other side becomes a seam suggestion that a person confirms.
- **Done when:**
  - A freelancer with a GitHub client and a spreadsheet client gets one brief with a collision across both, and neither tracker receives anything about the other.
  - An OpenProject milestone waiting on a GitHub milestone shows a forecast and buffer on both sides.

### 4.0 Foundation: creating records

Everything in Phase 4 creates things. Today the agent can only comment on and update existing tasks, and only on GitHub.

- **Protocol:** `create_task(project, NewTask, meta)` and `add_dependency(a, b, meta)`, both optional and guarded by capabilities.
  - `NewTask` carries the title, description, type, labels, owner, due date, estimate, parent or milestone, and dependencies.
  - Adapters that can't create raise a friendly read-only error.
- **Capabilities** (catalog): `creates` and `records`, where `records` is one of
  - `native`: Jira, Azure DevOps, OpenProject work-package types
  - `custom_field`: Asana
  - `label`: GitHub, GitLab, Gitea
  - `sheet`: spreadsheet
  - `none`

  The docs matrix shows them.
- **Record layer** (`agentic_pm.records`): record types are milestone, risk, assumption, issue, dependency, change request, decision and plan draft.
  - It reads and writes the small editable data block from ADR-0003.
  - It lists records of a type.
  - `agent-pm validate` checks the label convention.
- **Approvals for "create":** today a signed approval carries a field change. A plan can have 30 items, too many for a link. So the draft lives **in the tracker as one item** (`type:plan-draft`, readable plan plus a YAML block), and the approval token carries only that item and a hash of its content.
  - People can edit the draft before approving. A changed draft gets a fresh approval request instead of applying stale content.
- **GitHub:** create issues, labels, milestones and dependencies.
- **Spreadsheet:** writes go to agent-owned sheets only.
  - Before the first write the agent keeps a backup copy.
  - If the workbook contains things `openpyxl` can't preserve (charts, pivot tables, images), it writes a companion file `<name>.agent-pm.xlsx` instead and says so.
  - CSV users get sibling files (`raid.csv`, …).
- **Repo writer:** branch plus commit plus pull request through the GitHub API, used from 4.3 on. Gitea comes later.
- **Done when:** the contract tests cover creation, GitHub and spreadsheets create items in tests, and the other adapters say clearly that they can't yet.

### 4.1 WBS generator (#48)

A sponsor describes a goal by email, chat or voice note, or with `agent-pm plan --from goal.md`. The agent drafts a plan:

1. **Model step** (local LLM, JSON schema): milestones, work items with acceptance criteria, rough estimates, dependencies between them, and **open questions** it needs answered (scope, constraints, success criteria).
2. **Guard**, like the brief summary and how-tos:
   - sizes within limits, every item in a milestone, no invented ids
   - dependencies form no cycle, estimates are plausible
   - written in the ticket language, not inventing people
3. **Deterministic scheduling:** a forward pass over dependencies and estimates gives proposed dates and the critical path. Today's capacity check flags collisions with existing work.
4. **Draft:** one `type:plan-draft` item (spreadsheet: the `Plan draft` sheet). The leads get an approval request (high-impact tier), and the sponsor gets the open questions in their channel.
5. **On approval:** milestones, items and dependencies are created. The draft is closed with links to everything it created. Owners are asked once to confirm their items and dates.

- **Model quality:** a new eval suite `agent-pm eval --suite wbs` (goals in English and German, small to medium), run on qwen3.5 and gemma4. If the guard rejects too often, the agent falls back to a skeleton (milestones only) plus open questions rather than a weak plan.
- **Done when:** a goal written in German produces a reviewable English plan for an English-language project. Approve creates it; editing the draft first creates the edited version; reject leaves nothing behind.

### 4.2 RAID register (#49)

- Risks, assumptions, issues and dependencies as records, with probability × impact, owner, mitigation and review date.
- **The agent proposes risks** from what it already sees: slips, contradictions, blocked work and vendor dates. It proposes them as low-risk, audited items that people can close if they disagree.
- Briefs and the end-of-day note show new, escalating, unowned or overdue-for-review items. The weekly digest shows score trends.

### 4.3 Change control (#50)

- Today a `scope_change` message only tells the lead. Now it becomes a `type:change-request` item, in the requester's own words, with:
  - **timeline impact** (dependency what-if)
  - effort and risks
- The lead approves or declines. **No work items before approval.** On approval, the work is created through the 4.1 machinery.
- Change volume becomes a project KPI.

### 4.4 Baselines & critical path (#52)

- A baseline snapshot `.agent-pm/baselines/YYYY-MM-DD.json` is created when a plan is approved, via pull request. Re-baselining needs lead approval.
- The dependency analyzer gains critical path and float.
- Slippage against the baseline per milestone appears in the weekly digest.

### 4.5 Monthly health check (#54)

- Fills today's `monthly_health_check` stub with:
  - on-time rate and slippage against the baseline
  - change volume and impact
  - risk age and overdue reviews
  - how-tos written
  - a RAG status per area with reasons, and the decisions needed
- **Team and project level only** ([ADR-0004](adr/0004-people-data-boundaries.md)).

### 4.6 Decisions & meetings (#51)

- Decisions are captured from threads and replies as `type:decision` items or `.agent-pm/decisions/` files (via pull request).
- Agenda drafts come from open RAID items, change requests and decisions needed.
- Action items become tasks once their owner confirms them.

### 4.7 Quality & closure (#55)

- Acceptance criteria and UAT status per milestone, plus the defect trend.
- A closure report: delivered against planned, and open items handed over.
- Lessons learned, gathered with one short question per person, kept as Markdown via pull request.

### Deferred: calendar (#53)

Absences in capacity checks and meeting prep. ICS/CalDAV would come first.

## Risks

- **No pilot yet.** Phases 2 and 3 haven't run with a real team, and Phase 4 adds a lot of writing. A live test of what exists (GitHub writes, email, Matrix/Signal) should come before or alongside 4.0.
- **WBS quality on a local model.** Mitigated by the guard, the eval suite, the skeleton fallback and approval before anything is created.
- **Spreadsheets are fragile to write.** Mitigated by agent-owned sheets, a backup, the companion-file fallback and append-only writes to the task sheet.
- **Only GitHub creates items for now.** OpenProject, Gitea and Asana users get a clear "not yet" until their adapter gains `create_task`.

## Exit

A pilot project runs for a month with a plan created from a goal, plus the RAID register, change control and health check kept by the agent.
