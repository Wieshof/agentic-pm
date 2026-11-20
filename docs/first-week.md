# Your first week with agentic-pm

🇬🇧 English · 🇩🇪 [Deutsch](de/first-week.md)

Three people usually touch agentic-pm, so this guide has three lanes. Read yours; skip the others.

| You are… | Your lane | Time |
|----------|-----------|------|
| The owner or project lead who wants it | [1. Decide](#1-for-the-owner-decide) | about 15 minutes, nothing technical |
| The person who looks after your IT | [2. Set it up](#2-for-it-set-it-up) | about an hour (a guess: no one has timed it yet) |
| Someone on the team who will get briefs | [3. Use it](#3-for-the-team-use-it) | 5 minutes of reading |

Where it stands: everything below is built and tested, but no pilot team has run it in production yet. Week one only reads, so trying it is safe.

## 1. For the owner: decide

1. **Choose one project to start with.** One, not all. You learn everything from a small start.
2. **Say where its tasks live.** A spreadsheet (Excel or CSV) or a tracker: GitHub, OpenProject, or Gitea / Forgejo. All of them work today. Several at once, e.g. one per client, also work ([several trackers](sources.md)).
3. **Decide who gets a morning brief, and when.** Start with yourself at 8:00, in your language. Others join later, each with their own time and language.
4. **Decide where it runs.** Any computer that is switched on at briefing time. Your laptop is fine for trying it; for daily use, a small machine that stays on, with at least 16 GB of memory if it runs the language model.
5. **Hand over to your IT person.** Send them this page and these four answers:
   - which spreadsheet or tracker (and which project in it)
   - an email account the assistant may send from, e.g. `pm@your-company.com`
   - your people list: name, email, language, brief time
   - the machine it runs on
6. **Week one only reads.** The assistant writes nothing into your projects: no comments, no status or date changes. It does send the briefs; that's its job. Check each morning whether they're right.
7. **After one accurate week, decide about writing.** First comments and how-tos, then date and status changes, which always need a "yes" from the task's owner (client deadlines: from a lead). See [what it may change](guardrails.md).

**Tell your team before the first brief arrives.** Share [what the agent does with data about you](people-data.md). Where you have a data protection officer or a works council, involve them first.

## 2. For IT: set it up

You need a terminal, Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/).

**Step 1: install and try the demo** (no accounts needed):

```bash
git clone https://github.com/Wieshof/agentic-pm.git
cd agentic-pm
uv sync
uv run agent-pm brief --demo --person alex
uv run agent-pm run --demo --dry-run --once briefs
```

**Step 2: a read-only token for the tracker.**

| Tracker | What to create | Environment variable |
|---------|----------------|----------------------|
| GitHub | a fine-grained token with *Issues: read* for the one repository | `GITHUB_TOKEN` |
| OpenProject | an API key of a user who can see the project | `OPENPROJECT_API_KEY` |
| Gitea / Forgejo | a token with issue read access | `AGENT_PM_GITEA_TOKEN` |
| Spreadsheet | nothing; the file just has to be readable on this machine | none |

Tokens go into environment variables only, never into a file in the repository.

**Step 3: describe the team.** Copy `.agent-pm/team.example.yaml` to `.agent-pm/team.yaml`, enter the tracker and the people from the owner's list, then check it:

```bash
uv run agent-pm validate
uv run agent-pm brief --person <handle>
```

For a spreadsheet, follow [spreadsheet mode](spreadsheets.md) instead; the [solo example](../examples/solo/) is ready to copy.

**Step 4 (optional): the local language model.** It writes a two-sentence summary on top of each brief. Without it, the brief works the same, just without that summary.

```bash
ollama pull gemma4
uv run agent-pm eval --model gemma4
uv run agent-pm brief --person <handle> --llm
```

**Step 5: email.** Set `AGENT_PM_SMTP_HOST`, `AGENT_PM_SMTP_PORT`, `AGENT_PM_SMTP_USER`, `AGENT_PM_SMTP_PASSWORD` and `AGENT_PM_SMTP_FROM`. Week one only needs sending.

Replies come later, and they need a mailbox with plus-addressing (`pm+142@your-company.com` must reach `pm@your-company.com`). Not every mail provider supports it, so check before you promise replies to the team.

**Step 6: keep it running.** `uv run agent-pm run` sends each brief at the time the person chose. Run it as a service that starts with the machine, or schedule only the briefs with cron ([getting started](getting-started.md#4-morning-briefs)).

**Step 7 (week two or later): writing and replies.** Do this only after the owner says yes:

- `allow_writes: true`
- `project.agent_accounts`
- a random `AGENT_PM_SIGNING_KEY` of at least 32 characters
- `AGENT_PM_IMAP_*` for replies
- optionally webhooks and the approval pages

All of it is in [running the agent](running.md).

### When something doesn't work

| What you see | Usually means |
|--------------|---------------|
| `401` or `404` from GitHub | The token can't see that repository, or lacks *Issues: read*. |
| "model not found" | `ollama pull <model>` first; the message lists the models that are installed. |
| The model is very slow or the machine freezes | The model is too big for the memory; try a smaller one and run the eval again. |
| No brief arrived | The machine was asleep at briefing time, or `agent-pm run` wasn't running. |
| Replies are ignored | The mailbox doesn't do plus-addressing, or `AGENT_PM_IMAP_*` isn't set. |
| `validate` complains | It names the exact line. Times need quotes in YAML: `"08:00"`. |

## 3. For the team: use it

- **What you get:** one short message a day, at the time you chose. It covers your own tasks: what's overdue, what others are waiting for, what's due soon. Where details are missing, it asks one question. Here is [a real example](../README.md#what-it-does-for-you).
- **How to answer:** change the task in your tracker as usual. If your team has switched on replies, you can also just reply to the email, in your own language; your answer is added to the task as a note. In Matrix or Signal, a short "Friday" or "2 days" is enough, and the agent asks you to confirm the change.
- **What it does with data about you:** [one page in plain language](people-data.md). In short: no scores, no response-time tracking, and the language model runs on your company's own machine.
- **Don't want the brief, or want another time or language?** Ask your lead to change your entry in the team file. Replying "stop" to the agent doesn't switch it off yet.
