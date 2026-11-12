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

## Phase 2 — Write-back & Documentation
- Low-risk write tier with audit trail (comments, labels, blocker tags)
- Email plus-addressing routing (`pm+repo-task142@…`)
- Knowledge Extractor: email/chat → how-to Markdown on the ticket
- Permission & Audit Guard + lead-confirmation flow (web control plane v0)
- **Exit:** ≥ 50 % of closed pilot tickets carry an agent-written how-to

## Phase 3 — Omnichannel (chat & voice)
- WhatsApp Business integration (reply-context routing, voice notes)
- Voice agent: inbound calls, outbound 60-second check-ins, consent disclosure, RAM-only transcripts
- Adaptive Follow-Up Cadence
- Inconsistency Triangulation + micro-interviews
- **Exit:** blocker surfacing < 2 h; at least one non-tracker user active per pilot team

## Phase 4 — Scrum Artefacts & Spoken Briefings
- Interactive spoken status briefings with Q&A
- Async Daily Scrum, sprint review/retro drafts, DoD checks
- Decide whether the agent remodels artefacts or only reports on them
- **Exit:** a sprint run end-to-end without a separate reporting dashboard

## Phase 5 — Scale & Ecosystem
- Additional adapters by tier, see [trackers](trackers.md) and epic #18
- SSO preference sync (Entra ID / Google Workspace)
- Multi-project / portfolio views, policy-as-code
- KPI measurement & infrastructure-reduction report
