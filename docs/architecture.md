# Architecture & Modality Mapping

🇬🇧 English · 🇩🇪 [Deutsch](de/architecture.md)

> **This page shows the target architecture.** What is built today:
> - **Trackers:** GitHub, OpenProject, Gitea / Forgejo and spreadsheets, also several at once ([support matrix](trackers.md), [several trackers](sources.md)).
> - **Channels:** email, Matrix and Signal, including voice notes. WhatsApp, Slack, Teams and phone calls are planned.
> - **Language:** Python.
>
> The [README status table](../README.md#status) is the short version.

agentic-pm is a **three-tier middleware layer**. It ingests state from underlying tools, reasons over dependencies and inconsistencies, and translates updates across the communication channels.

## 1. Repository Adapter Layer (Open Core)

Bidirectional connectors that sync **tasks, assignees, deadlines, dependencies and comments**.

| Target | Transport | Notes |
|--------|-----------|-------|
| OpenProject | REST API v3 (HAL+JSON), webhooks | Native work-package relations for dependencies |
| Plane | REST API, webhooks | Self-hostable |
| Taiga | REST API, webhooks | |
| GitHub Issues / Projects | GraphQL + REST, webhooks, MCP | PR review state feeds Inconsistency Detector |
| GitLab Issues | REST/GraphQL, webhooks | |
| Jira | REST, webhooks | Issue links → dependency edges |
| Linear | GraphQL, webhooks | |

Every adapter implements one common interface (sketch):

```python
class TrackerAdapter(Protocol):  # agentic_pm/adapters/base.py
    async def get_task(self, ref: TaskRef) -> Task: ...
    async def list_tasks(self, project: str, *, include_closed: bool = False) -> list[Task]: ...
    async def list_dependencies(self, ref: TaskRef) -> list[Edge]: ...
    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None: ...
    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task: ...
    def subscribe(self, handler: EventHandler) -> Unsubscribe: ...
```

Each adapter is also exposed as an **MCP server**, so the reasoning engine and outside agents use the same tools.

## 2. Agentic Reasoning Engine

A stateful-per-event (but not persistent) orchestration core:

- **Dependency Graph Analyzer:** builds the graph from live tracker data on demand. It finds upstream and downstream blockers, critical-path changes and idle-time risk.
- **Inconsistency Detector:** compares status claims across sources (chat statements, tracker status, PR/CI state, calendar) and pinpoints the exact gap.
- **Knowledge Extractor:** turns conversational explanations into structured Markdown (problem → cause → fix → verification) and writes it back to the ticket.
- **Cadence & Briefing Planner:** decides *who* hears *what*, *when* and *through which channel*.
- **Permission & Audit Guard:** sorts every write into a risk tier and sends high-impact changes for confirmation (see [guardrails](guardrails.md)).

## 3. Omnichannel Interface Layer

A unified routing gateway that shapes outbound briefings and inbound updates to each user's configured preference.

| Modality | User archetype | Inbound | Outbound |
|----------|----------------|---------|----------|
| Reading | "Reader" | Email replies | Morning email brief, digests |
| Writing | "Writer" | WhatsApp / Slack / Teams text | Short chat nudges |
| Talking | "Talker" | Voice calls, voice notes | Outbound 60-second check-in calls |
| Listening | "Listener" | Spoken Q&A during briefing | Spoken status briefing (call or audio) |
| Web control plane | Leads / admins | Approvals, config, audit review | Dashboards (optional) |

## Event flow (example: Task A slips)

1. The tracker webhook for Task A's changed due date reaches the adapter.
2. The engine fetches A plus its dependency neighbourhood live.
3. The Dependency Analyzer finds that B depends on A and B's start is now at risk.
4. The Cadence Planner looks up B's owner (a Talker, afternoons) in `team.yaml`.
5. The Interface Layer schedules a voice check-in and proposes a new date.
6. The owner agrees by voice. The Guard rates the date change: internal means auto, client-facing means a lead must confirm.
7. The adapter writes the update and an audit comment back to the tracker.
