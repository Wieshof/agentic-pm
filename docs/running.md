# Running the agent (Phase 2)

🇬🇧 English · 🇩🇪 [Deutsch](de/running.md)

From Phase 2 on, agentic-pm can **write** to your tracker (behind the permission tiers), **receive replies** by email, ask people for how-tos when they close a task, and run your team's **cadence**. Everything runs in one process:

```bash
uv run agent-pm run                     # scheduler + approvals web + webhooks + inbox
uv run agent-pm run --demo --dry-run    # try it: prints messages instead of sending
uv run agent-pm run --once weekly_digest   # one job now, e.g. from cron
```

## 1. Configure

```yaml
project:
  tracker: github
  repo: your-org/your-repo
  leads: [alex]
  allow_writes: true                    # opt-in; without it the agent only reads
  agent_accounts: [agent-pm-bot]        # the login it writes with (self-trigger protection)
  agent_email: pm@your-org.com          # replies go to pm+142@your-org.com
  control_plane_url: https://pm.your-org.com   # approval links and webhooks
  ticket_language: en

cadence:
  morning_triage: "08:30"               # weekdays; personal briefs (unless brief.when is set)
  end_of_day: "17:30"                   # leads, only if something needs them
  weekly_digest: "Fri 15:00"            # leads
  monthly_health_check: last_friday     # arrives with #54
```

| Spec | Meaning |
|------|---------|
| `"08:30"` | every weekday (no weekend briefs) |
| `"daily 08:30"` | every day |
| `"Fri 15:00"` | weekly |
| `"last_friday 16:00"`, `"first_monday"` | monthly (default time 09:00) |

**Secrets** (environment only): `GITHUB_TOKEN`, `AGENT_PM_SIGNING_KEY` (any long random string, for approval links), `AGENT_PM_GITHUB_WEBHOOK_SECRET`, `AGENT_PM_SMTP_*` (sending) and `AGENT_PM_IMAP_*` (receiving: `HOST`, `PORT`, `USER`, `PASSWORD`, `FOLDER`).

**GitHub webhook:** in your repository settings, point a webhook to `https://pm.your-org.com/webhooks/github`, content type JSON, with the same secret. Subscribe to *Issues* and *Issue comments*.

## 2. What happens

**How-to loop (#10).** When someone closes an issue, they get a short, friendly email in their language: "nice work closing #12! How did you solve it?" They reply in a sentence or two, in any language. The local model turns it into a how-to on the ticket, written in `ticket_language`:

```markdown
### How it was solved
- **Problem:** Auth requests time out under load
- **Root cause:** Redis connection pool exhausted
- **Fix:** Increased the Redis pool size to 50
_Explained by Sam via email (in German), structured by agent-pm._
```

Whether the agent already asked is read from its own audited comment on the ticket, so it never asks twice.

**Other replies (#9).** Replies are matched to the task by the `pm+<id>@` address or the `Message-ID`, and quoted history and signatures are removed. Then:

| The message is … | The agent … |
|------------------|-------------|
| a solution | writes a how-to on the ticket |
| a status update or question | adds it to the ticket as a note |
| new scope ("could you also add …") | tells the lead and creates **no** work (formal change requests: #50) |
| thanks or a greeting | does nothing |
| from someone not in the team file | ignores it |

Each case gets a short "thanks, I've added it" reply.

**Approvals (#11).** Changes that need someone's OK go to them by email with a link to the control plane:
- **Task owner:** internal date or status changes.
- **Lead:** client deadlines, new owners.

Opening the link only *shows* the change, so mail scanners can't approve anything. Clicking ✅ applies it, but only if the task hasn't changed since the proposal. A short "waiting for OK" note on the ticket keeps everyone in the loop.

**Cadence (#45) and collisions (#46).**
- Briefs now show deadline collisions, e.g. "#12 and #31 are due by Tuesday and need about 3 days, but only 2 working days are left. Maybe move #31 or hand it over?"
- Leads get the evening note (only when needed) and the weekly digest.

**Data quality.** Before each brief the agent checks open tasks for missing owners, due dates and links, and asks the right person one short question per gap ([details](data-quality.md)).

**Onboarding (#47).** `uv run agent-pm onboarding --all --send` sends everyone a friendly intro in their language that explains what the agent does with their data ([details](people-data.md)).

## 3. Security model

- **Writes are opt-in** (`allow_writes`) and always go through the permission tiers. Every write carries the audit footer.
- **Approval links** are signed, expire after 72 h, are bound to one approver and re-check the live task. Anyone who has the link can decide, so treat approval emails like any other sensitive email.
- **Email can be forged.** That's why email only ever leads to low-risk writes (comments). It never approves, reassigns or moves dates.
- **Webhooks** must carry a valid signature and pass the [webhook gate](data-model.md#webhook-ingress-no-loops-no-storms), so the agent never reacts to its own changes.

## 4. Local model quality

Eval `uv run agent-pm eval --suite knowledge --model <model>`: 8 cases covering English and German, solutions, status updates, questions, scope requests and thanks. A German message must produce an English how-to when `ticket_language: en`.

| Model | Result (2026-11-12, `reasoning_effort: none`) |
|-------|-----------------------------------------------|
| qwen3.5 | 8/8 |
| gemma4 | 8/8 |

If the model fails the guard (invented ticket ids, missing fix, wrong language), the message is added as a plain note. Nothing gets lost.
