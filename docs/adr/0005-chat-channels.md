# ADR-0005: Chat channels, reply routing and follow-up

🇬🇧 English · 🇩🇪 [Deutsch](0005-chat-channels.de.md)

- **Status:** accepted
- **Date:** 2026-11-16

## Context

Phase 3 brings the agent to people who don't use the tracker. The roadmap named WhatsApp Business first. Three things made us look again:

- **WhatsApp Business** (Meta Cloud API) routes message content through Meta. It needs a verified business number, and every message the agent starts outside a 24-hour window needs a template Meta has pre-approved. That clashes with local-first ([ADR-0001](0001-tech-stack-and-llm.md)), and it can't be tried in five minutes.
- Chat has no `Reply-To` or `Message-ID`, yet the agent must stay stateless ([data model](../data-model.md)).
- Issue #14 asked for "per-user responsiveness tracking", which [ADR-0004](0004-people-data-boundaries.md) rules out.

## Decision

1. **Matrix and Signal come first, WhatsApp later.** Both can be self-hosted (a Matrix homeserver, signal-cli), neither needs a business account, and Signal is end-to-end encrypted by default. Both sit behind one `ChatTransport` interface, so WhatsApp (and Slack or Teams) can be added later without touching the routing.
2. **Reply routing through a tag in the agent's own message.** Every agent chat message about a task ends with a short line such as `— #12`, `— #12 · due?` or `— #12 · set status done · 3f9a0c21d4`. A reply carries its context back:
   - **Matrix:** the replied-to message is fetched from the homeserver, and it counts only if the agent sent it.
   - **Signal:** the quote's author must be the agent's number.

   Proposed changes are **HMAC-signed** with `AGENT_PM_SIGNING_KEY`, because a Signal client could send a fake quote. No lookup table exists anywhere.
3. **Chat confirmations count as the owner's confirmation, email doesn't.** Matrix and Signal authenticate the sender, but email can be forged. So a "yes" in chat from the task owner applies a medium-risk change (status, internal due date, estimate) through the existing permission tiers. High-risk changes still need a lead's signed approval link. An email claim only ever starts a normal approval request.
4. **Speech-to-text runs locally** (faster-whisper in-process, or a whisper.cpp server). Audio and transcripts stay in RAM. signal-cli's stored copy of a voice note is deleted after handling.
5. **Adaptive follow-up (#14) is per question, not per person.** Before nudging again, the agent counts the unanswered nudges for **one open question**, using what's visible in the conversation and on the ticket. After `escalate_after_ignored` nudges it switches to the person's next channel in `prefer` (set by them), and non-urgent questions are bundled. Nothing is stored per person, and no responsiveness score exists. Built next, after this foundation.
6. **Inconsistency triangulation (#15) asks, never fixes.** A claim like "done", "stuck" or "started" that contradicts the tracker becomes one question to whoever can settle it. The detection rules are conservative: negations, questions, "almost" and mixed claims don't count.

## Consequences

- ✅ Chat works end-to-end on infrastructure the team can run itself, with no new database.
- ✅ The same `Router` handles email and chat: notes, how-tos, scope, triangulation.
- ✅ A forged email or quote can't change a ticket.
- ⚠️ Matrix end-to-end encrypted rooms need Pantalaimon. Without it, use unencrypted direct chats.
- ⚠️ People who hide their phone number in Signal can't be matched to `team.yaml`.
- ⚠️ WhatsApp users wait for a later step. The interface is ready for it.
