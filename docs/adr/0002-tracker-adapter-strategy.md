# ADR-0002: Tracker adapter strategy

🇬🇧 English · 🇩🇪 [Deutsch](0002-tracker-adapter-strategy.de.md)

- **Status:** accepted
- **Date:** 2026-11-12
- **Issue:** #18

## Context

Teams use very different trackers: Jira, Asana, monday.com, Notion, Trello, Planner, Redmine, Bugzilla, Linear, GitLab and more. They differ in what they can offer (native dependencies, estimates, webhooks) and in how data is modelled (fixed fields vs. user-defined columns and properties). We can't build all adapters at once, but we must not paint ourselves into a corner, and users need to see clearly what works with their tracker.

## Decision

1. **One catalog as source of truth.** `src/agentic_pm/adapters/catalog.yaml` lists every known tracker with its capabilities, status (available / planned / candidate), tier and issue. The docs matrix (EN/DE), `agent-pm trackers` and `team.yaml` validation are generated from it. CI fails if the docs drift.
2. **Declared capabilities, graceful degradation.** Each adapter exposes `capabilities` (dependencies, estimates, due dates, multi-assignee, hierarchy, events, writes). The engine adapts to them and reports limitations to leads instead of staying silent.
3. **One protocol, one contract suite.** All adapters implement `TrackerAdapter` and pass `agentic_pm.testing.AdapterContract`, using recorded API responses so CI needs no accounts.
4. **Plugins via entry points** (`agentic_pm.adapters`), so adapters can live outside this repository.
5. **Mappings in config, not code.** Trackers with user-defined fields are configured through `project.tracker_options` (never secrets).
6. **Read-only first.** Every adapter ships read-only. Writes follow per tracker in Phase 2, behind the permission tiers.
7. **Tiers set the order.** Tier 1: Jira, GitLab, Linear, Plane, GitHub Projects, Asana. Tier 2: ClickUp, monday.com, Wrike, Shortcut, Redmine, Gitea/Forgejo, Taiga, Notion. Tier 3: Bugzilla, Trello, MantisBT, Microsoft Planner, Todoist, Taskade.

Still open, each tracked as an issue: a polling event source (#22), a validated mapping schema (#23), and an MCP bridge for the long tail (#24).

## Consequences

- ✅ Users see support status and limitations before they connect anything.
- ✅ New adapters are mostly mechanical: implement the protocol, record responses, pass the contract suite.
- ⚠️ Catalog rows for unbuilt trackers come from documentation and can be wrong. They're marked "not yet verified live" until an adapter exists.
- ⚠️ Trackers with free-form data (Notion, monday.com, Trello) need a mapping step per team. That's more setup than fixed-schema trackers.
