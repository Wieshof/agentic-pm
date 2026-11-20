# What the agent does with data about you

🇬🇧 English · 🇩🇪 [Deutsch](de/people-data.md)

A plain-language summary for everyone on a team that uses agentic-pm. The design rules behind it are in [ADR-0004](adr/0004-people-data-boundaries.md).

## What it uses

| Data | Where it comes from | What for |
|------|---------------------|----------|
| Your name, channels (email, phone, …), language, brief time | The team file `.agent-pm/team.yaml`, which your team maintains | Reaching you the way you prefer |
| Tasks assigned to you, their dates, estimates, dependencies | Your tracker (e.g. GitHub), read live | Briefs, risk warnings, deadline collisions |
| Messages you send to the agent | The agent's mailbox, or your chat with it (Matrix, Signal) | Adding them to the right task (how-to, note) |
| Voice notes you send in chat | Your chat, fetched into memory | Transcribed locally into text, then the audio is dropped |

## What it doesn't do

- **No scores about people.** No rankings, utilisation or productivity numbers.
- **No history about you.** Every check looks at the tasks as they are right now. Deadline collisions name tasks ("#12 and #31 are both due Friday"), not people's performance.
- **No guessing moods.** Messages aren't analysed for stress, sentiment or burnout.
- **No outside training.** Messages are processed by a model running on your organisation's own servers by default, and they're never used to train models.
- **No acting on strangers.** Email or chat from senders who aren't in the team file is ignored.
- **No reply-time tracking.** If a question goes unanswered, the agent counts nudges for that one question, never how quickly *you* usually answer.

## How long things are kept

- The agent itself keeps **nothing permanently**. What it writes (how-tos, notes, audit entries) lives in your tracker, where your team can see and edit it.
- Short-lived working data (for example to avoid processing the same webhook twice) stays in memory only and disappears on restart.
- Emails stay in the agent's mailbox under your organisation's normal mail retention.
- Chat: Signal messages leave Signal's queue once the agent has read them, and Matrix messages stay in your chat on your homeserver. **Voice notes and their transcripts are never stored by the agent.** Only the resulting note on the ticket remains.

## What it writes, and when it asks first

- **Automatically, with an audit note:** comments, how-tos and labels, plus one short note when it first asks about a missing detail ("🙋 Asked Sam about a missing detail: no due date"). That note is how it knows when to follow up. Nothing about you is stored elsewhere.
- **Your OK first:** changes to your task's dates or status. You get a friendly email with a link, or in chat a question you answer with "yes" or "no". Nothing changes until you decide.
- **A lead's OK first:** client deadlines, new owners, deleting things.

## Your choices

- Change your channel, language or brief time in the team file, or just ask your lead.
- Switch off briefs or reminders: remove the `brief:` line from your entry in the team file, or ask your lead to. Replying "stop" to an agent email doesn't do this yet: a reply about a task is added to that task as a note.
- Ask your lead what the team file says about you.

Before rolling out, your team should involve the data protection officer and, where there is one, the works council.
