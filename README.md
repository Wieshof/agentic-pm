# agentic-pm

🇬🇧 English · 🇩🇪 [Deutsch](README.de.md)

**A calm project assistant that works on top of the tools you already use, and runs its AI on your own hardware.**

agentic-pm reads your task list or tracker, notices what's slipping, and talks to each person the way they prefer: a short email in the morning, a chat message, a quick "yes" to confirm a change. It keeps no database of its own. Your spreadsheet or tracker stays the one place where the truth lives.

🌐 [Website](https://wieshof.github.io/agentic-pm/) · 🚀 [Getting started](docs/getting-started.md) · 📊 [Start with a spreadsheet](docs/spreadsheets.md) · 🗺️ [Roadmap](docs/roadmap.md)

---

## Why it exists

Projects rarely fail for lack of tools. They slip because nobody has time to keep tickets up to date, chase status across emails, or notice that Friday's launch quietly depends on something nobody is working on. At the same time, many teams and freelancers don't want to send their internal plans to a cloud AI.

agentic-pm takes on that busywork, and its language model runs on your machine (with [Ollama](https://ollama.com) or any OpenAI-compatible server).

## What it does for you

- **Warns you before a deadline slips.** It follows the dependencies between tasks and tells the right person early: *"#14 Release notes may slip 1 day because #13 Login UI is delayed further up the chain."*
- **Meets people where they are.** A morning brief by email, or a short brief in Matrix or Signal. People reply in their own language, while tickets stay in the team's language.
- **Asks one friendly question per missing detail.** "#16 has no due date. When should it be done?" Reply "Friday", confirm with "yes", and the ticket is updated.
- **Turns "here's how I fixed it" into a how-to** on the ticket, from an email reply or a voice note (transcribed locally).
- **Notices when the story doesn't add up.** Someone writes "#12 is done" while #12 is still open, so it asks once instead of guessing.
- **Follows up gently.** Urgent questions come daily, everything else weekly and bundled. If a channel doesn't work, it tries the next one, and it never keeps a score about people.

A real morning brief (from the built-in demo):

```
Good morning, Alex!

⏰ Overdue
  • #15 Quarterly roadmap review (1 day overdue)

⚠️ At risk because of a blocker
  • #14 Release notes may slip 1 day because #13 Login UI is delayed further up
    the chain. Suggested new date: 2026-11-21

🧩 A few details are missing
  • #16 Docs cleanup has no due date, so I can't tell whether it's at risk.
    When should it be done?

You have 3 open tasks. Just reply to this email if anything looks off. 💬
```

## Who it's for

| You are… | Start with |
|----------|------------|
| A freelancer or small studio planning in Excel or a CSV | [Spreadsheet mode](docs/spreadsheets.md): no accounts, nothing to install on a server |
| A team on GitHub, OpenProject or Gitea / Forgejo | [Getting started](docs/getting-started.md) |
| Someone who'd rather not open a tracker at all | Ask your team to add you with email, Matrix or Signal ([chat](docs/chat.md)) |

Not technical? Send the [getting-started guide](docs/getting-started.md) to whoever looks after your IT. The setup is one small config file.

## Private and careful by design

- **The AI runs locally.** Messages and task text go to a model on your own hardware, never to a cloud AI, and they're never used for training.
- **No second database.** Tasks, dates and dependencies are read live from your tool. Notes and how-tos are written back there, where everyone can see them.
- **You stay in control.** The agent only reads until you switch writing on. Comments and labels run automatically. Changing your own task's date or status needs your "yes", and client deadlines or new owners need a lead's signed approval.
- **No surveillance.** No scores, rankings or response-time tracking about people, and no guessing moods ([ADR-0004](docs/adr/0004-people-data-boundaries.md), [what it does with people's data](docs/people-data.md)).
- **Secrets stay out of the repo.** Tokens and passwords live in environment variables only, and `agent-pm validate` rejects anything that looks like one.

## Status

| | What | |
|-|------|-|
| ✅ | **Read-only insight:** dependency risks, deadline collisions, data-quality questions, morning briefs | Phase 1 |
| ✅ | **Write-back:** comments, how-tos, signed approvals, email replies, daily and weekly cadence | Phase 2 |
| ✅ | **Chat on Matrix and Signal:** voice notes, triangulation, adaptive follow-up | Phase 3 |
| ⏳ | WhatsApp, phone check-ins and spoken briefings | Phase 3 |
| 🗓️ | Planning and control, Scrum artefacts, portfolio and money | Phases 4–7 |

Everything marked ✅ is built and tested (more than 300 automated tests). No pilot team has run it in production yet. If you'd like to be the first, [open an issue](https://github.com/Wieshof/agentic-pm/issues). Full plan: [roadmap](docs/roadmap.md).

**Trackers:** Excel/CSV, GitHub Issues, OpenProject and Gitea / Forgejo work today. Jira, GitLab, Linear, Plane, Asana, Azure DevOps and 15 more are mapped out and planned ([support matrix](docs/trackers.md)).

## Try it in two minutes

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Wieshof/agentic-pm && cd agentic-pm
uv sync
uv run agent-pm brief --demo --person alex       # the brief above, from demo data
uv run agent-pm run --demo --dry-run --once briefs   # the whole agent, printing instead of sending
```

Then describe your own team in `.agent-pm/team.yaml`. This file is committed to your repository, so it never contains secrets:

```yaml
project:
  tracker: github                # spreadsheet | github | openproject | gitea
  repo: your-org/your-repo
  leads: [alex]
  ticket_language: en            # tickets stay in English ...
people:
  alex:
    role: team-lead
    archetype: reader            # reader | writer | talker | listener
    language: de                 # ... while Alex talks German with the agent
    channels: {email: alex@example.com}
    brief: {when: "08:00", format: email}
```

```bash
uv run agent-pm validate                  # checks the file, also for pasted secrets
uv run agent-pm brief --person alex       # your real brief (needs GITHUB_TOKEN)
```

Next steps: [getting started](docs/getting-started.md) · [running the agent](docs/running.md) · [full example config](.agent-pm/team.example.yaml)

---

## How it works

```
   Email ─┐                                            ┌─ Excel / CSV
  Matrix ─┤   ┌───────────────┐   ┌────────────────┐   ├─ GitHub Issues
  Signal ─┼──►│ Channels      │──►│ Reasoning      │──►├─ OpenProject
     Web ─┤   │ (who, where,  │   │ (dependencies, │   ├─ Gitea / Forgejo
   (MCP) ─┘   │  which task)  │   │  gaps, guards) │   └─ 21 more planned
              └───────────────┘   └────────────────┘
                     ▲                     │
                     └── local model ──────┘
```

| Loop | What it does |
|------|--------------|
| **Dependency risks** | When a task slips, it walks the dependency graph, warns the people downstream and suggests new dates before anyone is left waiting. |
| **Triangulation** | A status claim ("done", "stuck") that contradicts the tracker becomes one question to whoever can settle it. |
| **How-to docs** | Replies and voice notes about a fix become a structured how-to on the ticket, in the ticket's language. |
| **Adaptive follow-up** | Counts unanswered nudges per question, never per person. Urgent ones come daily, the rest weekly and bundled, and it tries the next channel when one isn't working. |
| **Briefs & cadence** | Morning briefs, an end-of-day note for leads, and a weekly digest, each sent at the time the person chose. |

**No database.** Tasks live in the tracker, and team preferences in `.agent-pm/team.yaml`. Which reply belongs to which task travels with the message itself: an email plus-address (`pm+142@…`) or a short signed tag in chat. Details: [architecture](docs/architecture.md) · [data model](docs/data-model.md) · [workflows](docs/workflows.md) · [how this maps to the full PM role](docs/pm-coverage.md)

---

## For developers

```bash
uv sync                                           # install
uv run pytest                                     # tests
uv run agent-pm validate .agent-pm/team.yaml      # check a team file
uv run agent-pm deps  --demo                      # dependency risks, gaps and cycles
uv run agent-pm brief --demo --person alex        # morning brief
uv run agent-pm run   --demo --dry-run            # the whole agent, printing instead of sending
uv run agent-pm eval  --model qwen3.5             # compare local models (--suite knowledge)
uv run agent-pm mcp                               # MCP tracker server (stdio, demo data)
uv run agent-pm trackers                          # which trackers are built / planned
```

**Local model:** run any OpenAI-compatible server, e.g. [Ollama](https://ollama.com), and set `llm.model` / `llm.base_url` in `team.yaml` ([ADR-0001](docs/adr/0001-tech-stack-and-llm.md)). Live test: `AGENT_PM_LIVE_LLM=<model> uv run pytest tests/test_llm.py`.

### Secrets

Everything secret comes from environment variables (or your secret manager), never from `team.yaml`:

| Variable | Used for |
|----------|----------|
| `GITHUB_TOKEN` / `AGENT_PM_GITHUB_TOKEN` | GitHub |
| `OPENPROJECT_API_KEY` | OpenProject |
| `AGENT_PM_GITEA_TOKEN` | Gitea / Forgejo |
| `AGENT_PM_SIGNING_KEY` | Approval links, chat confirmations and the audit footer (at least 32 random characters) |
| `AGENT_PM_GITHUB_WEBHOOK_SECRET` · `AGENT_PM_GITEA_WEBHOOK_SECRET` | Verifying webhooks |
| `AGENT_PM_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FROM` | Sending email |
| `AGENT_PM_IMAP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FOLDER` | Reading replies in the agent's mailbox |
| `AGENT_PM_MATRIX_HOMESERVER`, `_USER`, `_TOKEN` | Chat on Matrix |
| `AGENT_PM_SIGNAL_API_URL`, `_NUMBER` | Chat on Signal (signal-cli-rest-api) |
| `AGENT_PM_LLM_API_KEY` | Only if your model server needs a key |

### Code map

| Module | Purpose |
|--------|---------|
| `agentic_pm.config` | `team.yaml` schema and validation |
| `agentic_pm.adapters` | `TrackerAdapter` protocol; spreadsheet, GitHub, OpenProject, Gitea; tracker catalog; contract tests |
| `agentic_pm.engine` | Dependencies, capacity, completeness, follow-up, triangulation |
| `agentic_pm.briefs` | Morning brief, end-of-day note, weekly digest, guarded LLM summary |
| `agentic_pm.actions` · `approvals` · `audit` | Permission tiers, signed approvals, audit footer |
| `agentic_pm.email_routing` · `inbox` · `inbound` | Email routing, IMAP inbox, reply handling, how-to loop |
| `agentic_pm.chat` · `speech` | Matrix and Signal, reply tags, local speech-to-text |
| `agentic_pm.web` · `ingress` | Approval pages, webhooks, de-duplication |
| `agentic_pm.knowledge` · `llm` · `evals` | How-to extraction, model interface, model evals |
| `agentic_pm.cadence` · `runtime` · `cli` | Scheduler, `agent-pm run`, command line |
| `agentic_pm.mcp_server` | MCP tools over any adapter, with the same permission tiers |

### Repository layout

```
.agent-pm/        example team config
docs/             guides (German versions in docs/de/), website (index.html)
  adr/            architecture decision records
examples/solo/    a one-person studio planning in a CSV
schemas/          JSON Schema for team.yaml
src/agentic_pm/   the agent
tests/            automated tests
```

---

## Contributing

Ideas, questions and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Design discussion happens in [GitHub Issues](https://github.com/Wieshof/agentic-pm/issues), and each roadmap phase has a milestone.

**New tracker adapters** implement the `TrackerAdapter` protocol and pass the shared contract tests (`agentic_pm.testing`). Copying the GitHub adapter and its tests is the easiest start, and its tests use recorded API responses, so you need no account ([adapter epic #18](https://github.com/Wieshof/agentic-pm/issues/18)).

**Found a security problem?** Please report it privately, see [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE)
