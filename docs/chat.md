# Chat: Matrix and Signal (Phase 3)

🇬🇧 English · 🇩🇪 [Deutsch](de/chat.md)

People who don't live in the tracker can work with the agent in a chat app they already use. They get a short brief, answer one question at a time, send voice notes, and simply reply "yes" to confirm a change. Nobody needs a tracker account for that.

Why Matrix and Signal first, and not WhatsApp: see [ADR-0005](adr/0005-chat-channels.md).

## What people can do

| They send | What happens |
|-----------|--------------|
| A reply to one of the agent's messages | Goes to that task, no number needed |
| Free text with one task number, "#12 review is running" | Added to #12 as a note, the same as an email reply |
| A voice note | Transcribed locally, then handled like text. The note on the ticket says "(voice note)". |
| "Friday" to "When should it be done?" | The agent asks back: "Should I set the due date of #12 to Fri 20 Nov 2026?" |
| "yes" / "ja" to that question | The change is made, if they own the task. Otherwise the owner gets a normal approval request. |
| "#12 is done" while #12 is still open | See [Triangulation](#triangulation-when-the-story-doesnt-add-up) below |

Messages from people who aren't in `team.yaml` are ignored. A Matrix invite from a stranger is never accepted.

## Briefs in chat

With `brief.format: chat`, the agent sends a short brief in the person's chat at their brief time. Then it sends **each missing detail as its own question** (at most `completeness.max_per_brief`), so they can answer each one with a single reply:

```
#12 Fix auth timeout hat keinen Termin, deshalb kann ich nicht sagen, ob es eng wird.
Bis wann soll es fertig sein?

— #12 · due?
```

The last line is the **tag**. It tells the agent which task, and what kind of answer it expects, when someone replies. Nothing has to be stored for that ([data model](data-model.md#conversation--ticket-routing--transport-level-tagging)). A quiet day sends nothing.

## Triangulation: when the story doesn't add up

When a message or a fresh ticket comment says something the tracker doesn't, the agent asks **once**. Examples: "done" while the task is open, "I'm stuck" while it's in progress, or "started" while it's still open.

| Who says it | Where | What the agent does |
|-------------|-------|---------------------|
| The task owner | Matrix / Signal | "You wrote “… done”, but #12 is still in progress. Should I set it to done?" They reply yes or no. |
| Someone else | Chat | Asks the owner through the normal approval flow, and tells the sender it has asked |
| Anyone | Email | Same as "someone else": email can be forged, so it never counts as the owner's confirmation |
| A ticket comment (last 24 h) | Tracker | Shows up in the owner's brief, and as a single yes/no question if they use chat |

The rules are deliberately cautious. "Not done yet", "almost finished", "is it done?" and "done with the API, but stuck on the UI" don't count. The agent never changes a status without a "yes" or an approval.

## Set up Matrix

1. Create an account for the agent on your homeserver, e.g. `@agent-pm:example.org`, and get an access token for it.
2. Put each person's Matrix id into `team.yaml`: `channels: { matrix: "@sam:example.org" }`.
3. Set the environment variables:

   | Variable | Example |
   |----------|---------|
   | `AGENT_PM_MATRIX_HOMESERVER` | `https://matrix.example.org` |
   | `AGENT_PM_MATRIX_USER` | `@agent-pm:example.org` |
   | `AGENT_PM_MATRIX_TOKEN` | the agent account's access token |

4. A person starts a direct chat with the agent, or the agent opens one when it first writes to them.

**Encryption.** The agent talks plain HTTP to the homeserver and can't decrypt end-to-end encrypted rooms. Use an **unencrypted direct chat** with the agent on a homeserver you trust, or run the agent behind [Pantalaimon](https://github.com/matrix-org/pantalaimon), which handles E2EE for it. In an encrypted room, the agent replies that it can't read the message instead of staying silent.

**Nothing to remember.** What the agent has already handled is its own read marker on the homeserver, the same idea as "seen" in the IMAP inbox. On its very first start it marks everything as read rather than answering old history.

## Set up Signal

1. Run [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) in `normal` or `native` mode (not `json-rpc`), and register or link a number for the agent.
2. Put each person's number into `team.yaml`: `channels: { signal: "+43 660 1234567" }`.
3. Set `AGENT_PM_SIGNAL_API_URL` (e.g. `http://localhost:8080`) and `AGENT_PM_SIGNAL_NUMBER`.

Signal is end-to-end encrypted, and signal-cli keeps the keys on your machine. Reading a message takes it off Signal's queue, so the agent stores nothing. Voice notes are fetched into memory, and signal-cli's copy is deleted as soon as the message has been handled. Group chats are ignored, so only direct chats count.

If someone hides their phone number in Signal's privacy settings, the agent can't match them to `team.yaml`. They'll need to allow their number to be seen by contacts.

## Voice notes

Transcription runs **locally**. It's off until you choose an engine:

```yaml
speech:
  engine: faster-whisper   # uv sync --extra voice
  model: small             # tiny | base | small | medium | large-v3
# or
speech:
  engine: whisper-cpp
  url: http://localhost:8080/inference   # your whisper.cpp server
```

Audio and transcripts stay in memory and are never written to disk by the agent. Only the resulting note is kept, as a comment on the ticket. Without an engine, the agent kindly asks the person to type instead.

## Which channel the agent uses

Each person can set an order with `prefer: [signal, email]`. Without it, readers get email first and everyone else chat first. Replies always go back on the channel the message came from. Approval links go out the same way, so treat them like any other private message.

## Running it

`uv run agent-pm run` polls each configured chat every `cadence.chat_poll_seconds` (default 15). To check one round by hand, run `uv run agent-pm run --once chat`.

The agent's chat confirmations need `AGENT_PM_SIGNING_KEY` and `project.allow_writes: true`. Without them it still files notes, but it never offers to change anything.
