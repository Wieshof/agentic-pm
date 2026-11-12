# agentic-pm

**An omnichannel, agentic project-management layer that sits on top of the issue trackers you already run.**

agentic-pm doesn't replace your issue tracker. It's an intelligent orchestration layer that:

- **ingests** live state from existing open-source and API-first trackers (OpenProject, Plane, Taiga, GitHub/GitLab Issues, Jira, Linear),
- **reasons** over dependencies, inconsistencies and tacit knowledge, and
- **talks to every contributor through their natural medium**: reading (email), writing (chat/WhatsApp), talking (voice calls) or listening (spoken briefings), plus a lightweight web control plane.

The underlying tracker stays the single, synchronized source of truth. The agent keeps **no permanent task state** of its own.

> Status: 🧭 concept / early design. See the [roadmap](docs/roadmap.md).

---

## Why

Classic PM tooling forces every contributor into the same rigid workflow: open the tracker, find the ticket, edit fields, write the docs. Most people don't, so tickets go stale, blockers surface late and knowledge stays in people's heads.

agentic-pm turns this around. Contributors stay in the channel they already use, and the agent does the ticket work for them.

### It shrinks your stack instead of adding to it

1. **Fewer shadow tools and reporting dashboards.** You no longer need separate BI connectors, status-reporting plugins or custom Excel trackers. Readers get tailored email briefs and talkers get spoken briefings, both built from live ticket data.
2. **Fewer PM seat licenses.** Stakeholders, field staff and executives who only use phone, WhatsApp or email never need a tracker account. The agent acts as their proxy through one service integration.
3. **No standalone wikis for operational knowledge.** The agent pulls out *how* problems were solved during voice and chat check-ins and writes that onto the ticket itself. Teams stop keeping separate documentation tools that go stale.

---

## Architecture at a glance

```
            ┌──────────────────────────────────────────────────────────┐
  Email ───►│                                                          │
  WhatsApp ►│   Omnichannel Interface Layer  (routing gateway,         │
  Voice ───►│   per-user modality preferences, transport-level tagging)│
  Web UI ──►│                                                          │
            └──────────────────────────┬───────────────────────────────┘
                                       │
            ┌──────────────────────────▼───────────────────────────────┐
            │   Agentic Reasoning Engine                               │
            │   • Dependency Graph Analyzer   • Inconsistency Detector │
            │   • Knowledge Extractor         • Cadence / Briefing     │
            │   • Permission & Audit Guard                             │
            └──────────────────────────┬───────────────────────────────┘
                                       │
            ┌──────────────────────────▼───────────────────────────────┐
            │   Repository Adapter Layer (Open Core)                   │
            │   REST / GraphQL / MCP connectors                        │
            └───┬──────────┬──────────┬──────────┬──────────┬──────────┘
                ▼          ▼          ▼          ▼          ▼
          OpenProject    Plane      Taiga   GitHub/GitLab  Jira/Linear
```

Details: [docs/architecture.md](docs/architecture.md)

## Core agentic loops

| # | Loop | What it does |
|---|------|--------------|
| 1 | **Proactive Dependency Resolution** | When an estimate slips, it walks the dependency graph, warns downstream owners on their preferred channel and proposes new schedules before anyone sits idle. |
| 2 | **Inconsistency Triangulation** | Spots conflicting stories, e.g. "done" in WhatsApp while the PR is still unreviewed. It works out who has the missing context and runs a short micro-interview. |
| 3 | **Frictionless How-To Docs** | Turns voice notes and calls ("fixed the auth timeout by raising the Redis pool size…") into structured Markdown on the ticket. |
| 4 | **Adaptive Follow-Up Cadence** | Tracks how quickly each person responds and switches channel when one isn't working. Non-urgent questions are bundled into digests. |
| 5 | **Status Updates & Scrum Artefacts** | Sends email or spoken status briefings you can ask questions about. Keeps Scrum artefacts (backlog, sprint, burndown, review notes) in sync. |

Details: [docs/workflows.md](docs/workflows.md)

## Stateless by design

| Data | Where it lives |
|------|----------------|
| Tasks, deadlines, dependencies | The existing tracker, fetched live on every event |
| User preferences ("Drucker profiles") | `.agent-pm/team.yaml` in the repo, or SSO directory attributes (Entra ID / Google Workspace) |
| How-to docs & audit logs | Ticket comments, or Markdown committed to `/docs` |
| Conversation → ticket routing | Transport-level tags: email plus-addressing / `Message-ID`, WhatsApp reply context, voice session RAM |

Details: [docs/data-model.md](docs/data-model.md) · example config: [.agent-pm/team.example.yaml](.agent-pm/team.example.yaml)

## Guardrails & KPIs

- **Tiered write permissions:** low-risk actions run automatically with an audit trail. High-impact changes need a team lead to confirm.
- **Consent & privacy:** voice calls announce when transcription is on. Logs are scoped to the project workspace and are never used to train external models.
- **KPIs:** at least 70% less manual ticket editing, under 2 h to surface a dependency blocker, and the cross-modality engagement rate.

Details: [docs/guardrails.md](docs/guardrails.md)

## Repository layout

```
.agent-pm/            example team / preference config
docs/
  architecture.md     three-tier architecture & modality mapping
  workflows.md        the five autonomous loops
  data-model.md       stateless data placement & routing
  guardrails.md       permissions, privacy, KPIs
  roadmap.md          phased delivery plan
  adr/                architecture decision records
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Design discussion happens in GitHub Issues. Each roadmap phase has a milestone.

## License

[Apache License 2.0](LICENSE)
