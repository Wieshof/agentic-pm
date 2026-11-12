# Stateless Data Model

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
