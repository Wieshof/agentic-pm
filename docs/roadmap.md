# Phased Delivery Roadmap

🇬🇧 English · 🇩🇪 [Deutsch](de/roadmap.md)

Each phase is a GitHub milestone. The phases build on each other. Every phase ends with something a pilot team can actually use.

## Phase 0 — Foundations ✅
- Repository, docs, ADR process, contribution guidelines
- Pick the tech stack and LLM provider (ADR)
- `team.yaml` schema + validator
- Common `TrackerAdapter` interface + MCP tool surface

## Phase 1 — Read-only Insight (single tracker, email) ✅ built · pilot pending
- GitHub Issues adapter (read), then OpenProject or Plane
- Dependency Graph Analyzer (read-only)
- Morning email brief for "Readers"
- **Exit:** a pilot team gets accurate daily briefs with zero writes

## Phase 2 — Write-back, Documentation & Cadence ✅ built · pilot pending

See [Running the agent](running.md).

- Low-risk write tier with audit trail (comments, labels, blocker tags)
- Email plus-addressing routing (`pm+repo-task142@…`)
- Knowledge Extractor: email/chat → how-to Markdown on the ticket
- Permission & Audit Guard + lead-confirmation flow (web control plane v0)
- **Operating cadence:** scheduled triggers in `team.yaml` (morning triage, end-of-day RAID check, weekly digest, monthly health check)
- **Capacity & deadline collisions** across all connected projects (read-only, task-centric)
- **People-data boundaries** written down and enforced ([ADR-0004](adr/0004-people-data-boundaries.md))
- **Exit:** ≥ 50 % of closed pilot tickets carry an agent-written how-to; weekly digest replaces the manual status mail

## Phase 3 — Omnichannel (chat & voice) 🚧 in progress
- ✅ Chat on **Matrix and Signal**: reply-context routing, chat briefs with one question per gap, yes/no confirmations ([chat](chat.md), [ADR-0005](adr/0005-chat-channels.md))
- ✅ Voice notes, transcribed locally (faster-whisper / whisper.cpp), RAM only
- ✅ Inconsistency Triangulation + micro-interviews (#15)
- ✅ Adaptive Follow-Up Cadence (#14): per question, not per person; urgent daily, the rest weekly and bundled; next channel after N nudges
- ⏳ WhatsApp Business behind the same chat interface (#12)
- ⏳ Voice agent: inbound calls, outbound 60-second check-ins, consent disclosure, RAM-only transcripts (#13)
- **Exit:** blocker surfacing < 2 h; at least one non-tracker user active per pilot team

## Phase 4 — Plan & Control 📋 planned in detail
Records live in the tracker or the repo, never in an agent database ([ADR-0003](adr/0003-pm-records-without-a-database.md)). **Order and decisions: [Phase 4 plan](plan-phase-4.md)**: 4.0a several trackers, sources and seams ([ADR-0006](adr/0006-multiple-trackers-sources-and-seams.md), ✅ [built](sources.md)) → 4.0 foundation (creating records) → WBS generator → RAID → change control → baselines → health check → decisions → closure. Calendar deferred.
- **Initiation / WBS generator:** a sponsor describes a goal by voice, email or chat; the agent drafts milestones, work items, acceptance criteria and first dependencies in the tracker, **as a draft for approval**
- **RAID register:** risks, assumptions, issues and dependencies as tracker items (`type:risk` …) with probability × impact, owner and mitigation
- **Change control:** new scope arriving in any channel ("could you also add …") is flagged with its timeline impact and routed to the lead for approval **before** work items are created
- **Decision log & meeting notes:** agendas from open items, decisions and action items written back to the tracker
- **Baselines & critical path:** baseline snapshots, float, slippage against baseline; calendar source for availability *(deferred)*
- **Monthly health check** against baseline and success criteria; project KPIs (on-time rate, change volume, risk resolution, defect trend)
- **Quality & closure:** acceptance criteria and UAT status, defect trends, closure report and lessons learned
- **Exit:** a pilot project runs a month with RAID, change control and health check maintained by the agent

## Phase 5 — Scrum Artefacts & Spoken Briefings
- Interactive spoken status briefings with Q&A
- Async Daily Scrum, sprint review/retro drafts, DoD checks
- Decide whether the agent remodels artefacts or only reports on them
- **Self-improving cadence:** a monthly retrospective of the agent's own cadence, proposed as a pull request to `team.yaml`
- **Exit:** a sprint run end-to-end without a separate reporting dashboard

## Phase 6 — Scale & Ecosystem
Adapter work can run in parallel to other phases.
- Additional adapters by tier, see [trackers](trackers.md) and epic #18 (incl. Azure DevOps, Smartsheet, MS Project)
- SSO preference sync (Entra ID / Google Workspace)
- Policy-as-code
- KPI measurement & infrastructure-reduction report

## Phase 7 — Money & Portfolio (new)
- Time-tracking and finance sources (e.g. Tempo, Harvest, Clockify, spreadsheets)
- Budget vs. actuals, burn rate, variance explanations and forecasts
- Portfolio view for leadership: prioritisation across projects (cross-tracker dependencies and capacity move to 4.0a, [ADR-0006](adr/0006-multiple-trackers-sources-and-seams.md))
- Methodology profiles: Scrum, Kanban, PRINCE2 stage gates, hybrid
- Stakeholder map and one-question pulse surveys through each person's channel

How this maps to the full PM role: [PM coverage map](pm-coverage.md).
