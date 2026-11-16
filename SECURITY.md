# Security policy

🇬🇧 English · 🇩🇪 [Deutsch](SECURITY.de.md)

Thank you for helping keep agentic-pm and the people who use it safe. 💙

## Reporting a vulnerability

Please **don't open a public issue** for a security problem. Instead, report it privately:

👉 **[Report a vulnerability](https://github.com/Wieshof/agentic-pm/security/advisories/new)** (GitHub private vulnerability reporting)

Helpful to include, as far as you know it:

- what an attacker could do, and what they need for it (e.g. "can comment on a ticket", "can reach the MCP server")
- steps or a small example to reproduce it
- the version or commit you looked at

You'll get a first reply within **7 days**. We'll keep you posted while we work on a fix, agree on a disclosure date with you, and credit you in the advisory if you like.

## Supported versions

agentic-pm is still early (0.x). Fixes go into **`main`** only; please always test against the latest `main`.

## What matters most

The agent reads untrusted text (tickets, emails) and can write to trackers. These are the parts where a weakness hurts most, so reports about them are especially welcome:

| Area | What should hold |
|------|------------------|
| **Approvals** | No change above low risk is applied without the owner's confirmation or a lead's signed approval link. Nobody can approve by claiming to be someone. |
| **Signing key** (`AGENT_PM_SIGNING_KEY`) | Approval tokens and the audit footer can't be forged, replayed after they're used, or used for a different task. |
| **Webhooks** | Requests without a valid signature are rejected; the agent never reacts to its own changes and can't be silenced by pasted text. |
| **Ticket and email text** | Untrusted text only ever leads to suggestions or low-risk comments, never to approvals, reassignments or moved dates. |
| **People data** | No per-person scores or history ([ADR-0004](docs/adr/0004-people-data-boundaries.md)). |
| **Secrets** | Tokens and keys live in environment variables only, never in `team.yaml` or in messages. |

The security model is described in [Running the agent](docs/running.md#3-security-model) and in the [guardrails](docs/guardrails.md).

## Not in scope

- Vulnerabilities in a tracker, mail server or LLM runtime itself (please report those to their maintainers)
- Problems that need an already compromised machine or a leaked signing key
- Running with writes enabled but without `AGENT_PM_SIGNING_KEY`, which the docs advise against

Not sure whether something counts? Report it anyway. We'd rather hear about it. 🙂
