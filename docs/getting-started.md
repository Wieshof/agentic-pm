# Getting started (Phase 1: read-only insight)

> Ready for writes, how-tos, approvals and the team cadence? Continue with [Running the agent (Phase 2)](running.md).

🇬🇧 English · 🇩🇪 [Deutsch](de/getting-started.md)

In Phase 1, agentic-pm **reads** your tracker, finds dependency risks and sends each "Reader" a friendly morning email. It never writes to the tracker.

## 1. Try it with demo data (no accounts needed)

> Working alone or in a tiny team with a spreadsheet? Start with [your `.xlsx` or `.csv`](spreadsheets.md) instead.

```bash
uv sync
uv run agent-pm deps  --demo                 # dependency risks and cycles
uv run agent-pm brief --demo --person alex   # English brief for a lead
uv run agent-pm brief --demo --person sam    # German brief ("Du")
```

The demo dates are relative to today, so there is always something to see: an overdue task, a delay that passes down a chain, and a circular dependency.

## 2. Connect your tracker

GitHub Issues and OpenProject work today. For all other trackers (Jira, Asana, Notion, Trello, …) see the [support matrix](trackers.md).

Copy `.agent-pm/team.example.yaml` to `.agent-pm/team.yaml` and adjust it. Check it with `uv run agent-pm validate`. Secrets only ever come from environment variables.

### GitHub Issues

```yaml
project: {tracker: github, repo: your-org/your-repo, leads: [alex]}
```

Set `GITHUB_TOKEN` (or `AGENT_PM_GITHUB_TOKEN`) to a token that can read issues. If someone's GitHub login differs from their handle, set `tracker_login`.

GitHub has no due dates or estimates, so agentic-pm reads these conventions:

| What | How to write it |
|------|-----------------|
| Due date | A line `Due: 2026-12-01` in the issue body, otherwise the milestone's due date |
| Estimate | A line `Estimate: 4h` / `2d` / `1w`, or a label `estimate:4h` (1d = 8h) |
| Dependencies | GitHub's native "blocked by / blocking" and sub-issues, or lines `Blocked by #12` / `Blocks #15` |
| Status | Closed → done. Open + label `status:in-progress`, `status:in-review` or `status:blocked` |
| Client deadline | Label `client-facing` (date changes then need a team lead's approval later on) |

### OpenProject

```yaml
project: {tracker: openproject, repo: my-project, base_url: https://op.example.com, leads: [alex]}
```

Set `OPENPROJECT_API_KEY`. Due dates, estimates, status, the assignee (display name) and relations (blocks / precedes / follows / relates, parent / child) are read natively. Use the display name as `tracker_login`.

> The OpenProject adapter is tested against recorded API responses. It has not yet been tested against a live instance, so please report anything that looks off.

## 3. How the risk check works

The analyzer is plain, explainable code, not model guesswork:

- A task needs `estimate ÷ 8h` days (at least 1). Tasks without an estimate count as 1 day.
- A task can start the day after all its open blockers finish. An overdue blocker is assumed to finish today at the earliest.
- If that pushes the finish past the due date, the task is **at risk**. The analyzer gives a reason (blocker overdue / blocker due too late / delay further up the chain) and suggests a new date.
- Calendar days only for now. Weekends and holidays are not considered yet.

## 4. Morning briefs

```bash
uv run agent-pm brief --person alex                    # print to the terminal
uv run agent-pm brief --all --format eml --out briefs/ # one .eml per Reader
uv run agent-pm brief --all --send                     # send via SMTP
```

Each task appears once, in its most important section: overdue, others waiting for you, at risk, due soon, waiting on something. Leads also see team risks and circular dependencies. `language: de` gives a German brief using the informal "Du".

**Sending** uses `AGENT_PM_SMTP_HOST`, `AGENT_PM_SMTP_PORT` (587), `AGENT_PM_SMTP_USER`, `AGENT_PM_SMTP_PASSWORD` and `AGENT_PM_SMTP_FROM`.

**Scheduling:** until the agent has its own scheduler, use cron, for example weekdays at 07:30:

```cron
30 7 * * 1-5  cd /srv/agentic-pm && uv run agent-pm brief --all --send --llm
```

## 5. Optional: a short summary from your local model

With `--llm`, a local model (see `llm:` in `team.yaml`) adds 1–3 friendly opening sentences. Safety rails:

- The model only sees the computed facts.
- German "du/dich/dein" is capitalized automatically. Formal "Sie" is rejected.
- Summaries that mention unknown task numbers, contain stray `#` tags or are too long are **dropped**, and the brief goes out without them.
- On quiet days the model isn't asked at all (models tend to invent tasks when given nothing).

For thinking models such as qwen3.x, set `reasoning_effort: none`.

### Comparing models: the eval

```bash
uv run agent-pm eval --model qwen3.5
uv run agent-pm eval --model gemma4
```

There are 8 cases (English and German, busy and quiet days), all with deterministic graders and no LLM judge. Results on 2026-11-12 (two runs each, `reasoning_effort: none`):

| Model | Run 1 | Run 2 | Typical failure (caught by the guard) |
|-------|-------|-------|---------------------------------------|
| qwen3.5 | 8/8 | 6/8 | Leaves out an important task, or writes `#{15}` |
| gemma4 | 7/8 | 8/8 | Leaves out an important task |

Add your own cases to `src/agentic_pm/evals/brief_summary_cases.yaml` before switching models.
