# Stateless Data Model

🇬🇧 English · 🇩🇪 [Deutsch](de/data-model.md)

Every piece of data the agent needs can live in infrastructure the company already runs. The agent itself holds **no permanent task state**.

## Tasks, deadlines & dependencies → existing tracker

When an event arrives (a git webhook, an incoming email or a phone call), the agent fetches live context from the tracker's API, reasons over it and writes the updated status or blocker tags straight back.

## User preferences ("Drucker profiles") → repo config or SSO

Preferences such as "morning email" or "afternoon phone call" live in one human-readable file in the repository (`.agent-pm/team.yaml`) or in directory attributes (Microsoft Entra ID / Google Workspace). Anyone can change their own preference by editing the file or sending the agent a message.

See [`.agent-pm/team.example.yaml`](../.agent-pm/team.example.yaml).

## How-to docs & audit logs → ticket comments & Markdown

There's no separate database or wiki. The agent appends structured Markdown to the ticket or commits it to `/docs` in the repo. Audit entries are ticket comments with a machine-readable footer.

## Conversation → ticket routing → transport-level tagging

No lookup table is needed to know which reply belongs to which task.

| Channel | Mechanism |
|---------|-----------|
| Email | Dynamic plus-addressing (`pm+repo-task142@yourdomain.com`) or `Message-ID` / `In-Reply-To` headers |
| WhatsApp | WhatsApp Business reply-context metadata, or a short reference tag in the prompt |
| Voice | The transcript is held only in the call session's RAM for the 2–3 minute call. Structured updates are written to the tracker when the caller hangs up, then the transcript is discarded. |

## What the agent *does* keep (ephemeral / operational only)

- Short-lived caches with a TTL and no source-of-truth role
- Delivery and retry queues for outbound messages
- Responsiveness counters for adaptive cadence. These can also be stored back in `team.yaml` or SSO attributes if full statelessness is required.

## Webhook ingress: no loops, no storms

Every write the agent makes (a comment, a how-to section) causes the tracker to send a webhook straight back. `agentic_pm.ingress.WebhookGate` drops, without any database:

| Dropped | How it's recognised |
|---------|---------------------|
| Retries of the same delivery | Delivery id (e.g. `X-GitHub-Delivery`), remembered for 1 h |
| The agent's own changes | Sender is in `project.agent_accounts`, or the text carries the audit footer |
| Bursts for one ticket | Same ticket + event kind within 10 s |

Dropping is safe because the agent fetches the live ticket on every admitted event anyway. The memory is process-local and bounded; a restart simply starts fresh. With several agent processes, route webhooks for one repository to the same process (or accept the occasional duplicate question).

## Languages: people vs. tickets

Two separate settings in `team.yaml`:

- `people.<handle>.language` is the language the agent **speaks** with that person (briefs, chats, calls).
- `project.ticket_language` is the language the agent **writes** into the tracker.

So a developer can explain a fix in a German voice note while the agent writes the how-to in English into the GitHub issue. Any ISO code works (`en`, `de`, `pt-BR`). Brief templates exist for English and German so far; other languages get English templates with a summary in their own language.
