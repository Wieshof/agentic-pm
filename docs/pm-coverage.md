# PM coverage map

🇬🇧 English · 🇩🇪 [Deutsch](de/pm-coverage.md)

How agentic-pm maps to the full project-manager role: responsibilities, daily/weekly/monthly cadence and success metrics. It shows what's built, what's planned (with its issue), what stays with humans, and what we deliberately don't do.

✅ built · 🗓️ planned · 🤝 assist only (the agent prepares, a human decides) · 🚫 deliberately not (see [ADR-0004](adr/0004-people-data-boundaries.md))

## Responsibilities

### Project planning & initiation

| Responsibility | | Where |
|---|:-:|---|
| Scope, objectives, deliverables, success criteria from a sponsor brief | 🗓️ | [#48](https://github.com/Wieshof/agentic-pm/issues/48) |
| WBS, milestones, acceptance criteria, first dependencies | 🗓️ | [#48](https://github.com/Wieshof/agentic-pm/issues/48) |
| Schedule, critical path, baselines | 🗓️ | slip detection ✅; [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Risk register, communication & quality plans | 🗓️ | [#49](https://github.com/Wieshof/agentic-pm/issues/49), [#61](https://github.com/Wieshof/agentic-pm/issues/61), [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Budget estimates, resource plan | 🗓️ | [#58](https://github.com/Wieshof/agentic-pm/issues/58), [#46](https://github.com/Wieshof/agentic-pm/issues/46) |
| Feasibility study, business case | 🤝 | drafts only |
| Governance, decision framework, escalation paths | 🗓️ | permission tiers ✅; [#11](https://github.com/Wieshof/agentic-pm/issues/11), [#51](https://github.com/Wieshof/agentic-pm/issues/51) |

### Execution & leadership

| Responsibility | | Where |
|---|:-:|---|
| Monitor progress, follow up, remove blockers | ✅ | briefs, dependency analyzer; [#14](https://github.com/Wieshof/agentic-pm/issues/14), [#15](https://github.com/Wieshof/agentic-pm/issues/15) |
| Coordinate dependencies across workstreams | ✅ | one project; across projects [#59](https://github.com/Wieshof/agentic-pm/issues/59) |
| Assign tasks, set expectations | 🗓️ | suggestions only, lead approves [#11](https://github.com/Wieshof/agentic-pm/issues/11) |
| Workload & capacity conflicts | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46) (task-centric) |
| Coaching, feedback, performance management | 🤝 | neutral 1:1 material at most, see ADR-0004 |
| Conflict resolution, motivation | 🤝 | human |

### Stakeholders & communication

| Responsibility | | Where |
|---|:-:|---|
| Tailored updates per person and channel | ✅ | email briefs (EN/DE); [#12](https://github.com/Wieshof/agentic-pm/issues/12), [#13](https://github.com/Wieshof/agentic-pm/issues/13), [#16](https://github.com/Wieshof/agentic-pm/issues/16) |
| Status reports, executive briefings, forecasts | 🗓️ | [#45](https://github.com/Wieshof/agentic-pm/issues/45), [#54](https://github.com/Wieshof/agentic-pm/issues/54) |
| Stakeholder map & engagement plan | 🗓️ | [#61](https://github.com/Wieshof/agentic-pm/issues/61) |
| Workshops, steering meetings: agendas, minutes, decisions | 🗓️ | [#51](https://github.com/Wieshof/agentic-pm/issues/51) |
| Primary point of contact for questions | 🗓️ | [#9](https://github.com/Wieshof/agentic-pm/issues/9), [#12](https://github.com/Wieshof/agentic-pm/issues/12), [#13](https://github.com/Wieshof/agentic-pm/issues/13) |

### Risk, issue & change management

| Responsibility | | Where |
|---|:-:|---|
| Dependency risks and slips | ✅ | analyzer |
| Conflicting status claims | 🗓️ | [#15](https://github.com/Wieshof/agentic-pm/issues/15) |
| RAID register with probability × impact, owners, mitigation | 🗓️ | [#49](https://github.com/Wieshof/agentic-pm/issues/49) |
| Formal change control incl. scope creep from chats | 🗓️ | [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Escalation of issues | 🗓️ | [#11](https://github.com/Wieshof/agentic-pm/issues/11), [#49](https://github.com/Wieshof/agentic-pm/issues/49) |

### Budget, schedule & resources

| Responsibility | | Where |
|---|:-:|---|
| Monitor schedule and recover delays | ✅ | risks + suggested dates; [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Capacity planning, resource conflicts | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46), [#53](https://github.com/Wieshof/agentic-pm/issues/53) |
| Budget vs. actuals, burn rate, forecasts | 🗓️ | [#57](https://github.com/Wieshof/agentic-pm/issues/57), [#58](https://github.com/Wieshof/agentic-pm/issues/58) |
| Procurement, vendor contracts, invoices | 🤝 | reminders and summaries; approvals stay human |

### Quality & delivery

| Responsibility | | Where |
|---|:-:|---|
| Acceptance criteria, testing and UAT status | 🗓️ | [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Definition of done checks | 🗓️ | [#17](https://github.com/Wieshof/agentic-pm/issues/17) |
| Closure, post-implementation review, lessons learned | 🗓️ | [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Knowledge capture during the project | 🗓️ | [#10](https://github.com/Wieshof/agentic-pm/issues/10) |

### Process improvement & compliance

| Responsibility | | Where |
|---|:-:|---|
| Methodologies: Scrum, Kanban, PRINCE2, hybrid | 🗓️ | [#17](https://github.com/Wieshof/agentic-pm/issues/17), [#60](https://github.com/Wieshof/agentic-pm/issues/60) |
| Audit trail, permission tiers, consent | ✅ | audit footer, webhook gate; [#8](https://github.com/Wieshof/agentic-pm/issues/8), [#11](https://github.com/Wieshof/agentic-pm/issues/11) |
| Portfolio reporting and prioritisation | 🗓️ | [#59](https://github.com/Wieshof/agentic-pm/issues/59) |
| PMO templates and process improvement | 🗓️ | [#56](https://github.com/Wieshof/agentic-pm/issues/56) |

## Operating cadence

A PM's rituals become **scheduled triggers** in `team.yaml` ([#45](https://github.com/Wieshof/agentic-pm/issues/45)). The agent's own rhythm is reviewed monthly and changes are proposed as a pull request ([#56](https://github.com/Wieshof/agentic-pm/issues/56)), so the operating cadence is a living document.

### Daily

| Responsibility | | Where |
|---|:-:|---|
| Morning triage: red flags, overdue, blockers | ✅ | morning brief; trigger [#45](https://github.com/Wieshof/agentic-pm/issues/45) |
| Scan RAID log for new or escalating items | 🗓️ | [#49](https://github.com/Wieshof/agentic-pm/issues/49), [#45](https://github.com/Wieshof/agentic-pm/issues/45) |
| Follow up on critical-path tasks | 🗓️ | [#14](https://github.com/Wieshof/agentic-pm/issues/14), [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Document decisions and action items in real time | 🗓️ | [#51](https://github.com/Wieshof/agentic-pm/issues/51), [#10](https://github.com/Wieshof/agentic-pm/issues/10) |
| End of day: update RAID, log new risks and changes | 🗓️ | [#45](https://github.com/Wieshof/agentic-pm/issues/45), [#49](https://github.com/Wieshof/agentic-pm/issues/49), [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Review overnight messages, clear inbox | 🤝 | the agent answers routine questions itself [#9](https://github.com/Wieshof/agentic-pm/issues/9) |

### Weekly

| Responsibility | | Where |
|---|:-:|---|
| Schedule review, critical path, slippage | 🗓️ | [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Weekly status report / steering roll-up | 🗓️ | [#45](https://github.com/Wieshof/agentic-pm/issues/45) |
| Process change requests | 🗓️ | [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Resource allocation for the next 1–2 weeks | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46), [#53](https://github.com/Wieshof/agentic-pm/issues/53) |
| 1:1s, morale, recognition | 🤝 | human; no inferred morale (ADR-0004) |

### Monthly

| Responsibility | | Where |
|---|:-:|---|
| Health check against baseline and success criteria | 🗓️ | [#54](https://github.com/Wieshof/agentic-pm/issues/54) |
| Financial review and forecast | 🗓️ | [#58](https://github.com/Wieshof/agentic-pm/issues/58) |
| Capacity planning for 1–3 months | 🗓️ | [#46](https://github.com/Wieshof/agentic-pm/issues/46), [#59](https://github.com/Wieshof/agentic-pm/issues/59) |
| Retrospective / lessons learned | 🗓️ | [#17](https://github.com/Wieshof/agentic-pm/issues/17), [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Review and adapt the operating cadence itself | 🗓️ | [#56](https://github.com/Wieshof/agentic-pm/issues/56) |
| Performance and development conversations | 🚫 | never automated (ADR-0004) |

## Success metrics

Our earlier KPIs measure the tool (less ticket editing, faster blocker detection). These measure the project:

| Metric | Source | Issue |
|---|---|---|
| On-time delivery rate | tracker + baseline | [#54](https://github.com/Wieshof/agentic-pm/issues/54), [#52](https://github.com/Wieshof/agentic-pm/issues/52) |
| Budget variance | time tracking / finance | [#58](https://github.com/Wieshof/agentic-pm/issues/58) |
| Scope adherence, change volume and impact | change requests | [#50](https://github.com/Wieshof/agentic-pm/issues/50) |
| Stakeholder satisfaction | pulse surveys (team level) | [#61](https://github.com/Wieshof/agentic-pm/issues/61) |
| Team engagement | pulse surveys, min. group size 5 | [#61](https://github.com/Wieshof/agentic-pm/issues/61), [#47](https://github.com/Wieshof/agentic-pm/issues/47) |
| Risk and issue resolution | RAID register | [#49](https://github.com/Wieshof/agentic-pm/issues/49) |
| Quality of deliverables | defects, acceptance | [#55](https://github.com/Wieshof/agentic-pm/issues/55) |
| Process improvement & knowledge sharing | how-tos, lessons learned | [#10](https://github.com/Wieshof/agentic-pm/issues/10), [#55](https://github.com/Wieshof/agentic-pm/issues/55) |

## Where PM records live

RAID items, change requests, decisions and baselines live in the tracker (types or labels) or as versioned files under `.agent-pm/`, never in an agent database. See [ADR-0003](adr/0003-pm-records-without-a-database.md).

## Data sources beyond trackers

Calendars ([#53](https://github.com/Wieshof/agentic-pm/issues/53)), time tracking and finance ([#57](https://github.com/Wieshof/agentic-pm/issues/57)), plus all trackers in the [support matrix](trackers.md), now including Azure DevOps, Smartsheet and MS Project.

## Boundaries

The agent supports people topics, but it doesn't monitor or judge people. Capacity checks are task-centric, there's no per-person history or score, team metrics are shown only at team level, and nothing is inferred about mood. Details and legal background: [ADR-0004](adr/0004-people-data-boundaries.md).

Phases: [roadmap](roadmap.md).
