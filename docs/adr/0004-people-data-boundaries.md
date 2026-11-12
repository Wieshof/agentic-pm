# ADR-0004: Boundaries for data about people

🇬🇧 English · 🇩🇪 [Deutsch](0004-people-data-boundaries.de.md)

- **Status:** accepted
- **Date:** 2026-11-12

## Context

A PM's job includes people topics: workload, capacity conflicts, morale, coaching, performance. An agent that reads every ticket and message could easily turn into a surveillance tool. That would destroy the trust it depends on, and it would cause legal problems:
- GDPR: purpose limitation, transparency, and usually a data protection impact assessment.
- In Germany and Austria: works-council co-determination over technical systems that can monitor behaviour or performance (§ 87 (1) no. 6 BetrVG; §§ 96, 96a ArbVG).

## Decision

1. **Purpose: delivering the project, never evaluating people.** The agent doesn't rate, rank or score individuals.
2. **Task-centric, not person-centric.** Capacity checks look at **current** open work and say what collides, e.g. "#12 and #31 are both due Friday and both on the critical path". They suggest a fix (move, split, hand over). There are no utilisation percentages or per-person scores.
3. **No people history.** No stored profiles, trends or rankings per person. Per-person signals the agent needs to work, such as which channel someone answers on, stay in process memory with a short lifetime. They're visible to that person and can be switched off.
4. **Team-level aggregates only** for team metrics (engagement, pulse surveys), with a minimum group size of 5 before anything is shown.
5. **No inferred states.** No sentiment, stress, morale or burnout detection from messages or activity.
6. **Assist-only topics.** Performance management, coaching, conflict resolution, hiring, and approving invoices or purchase orders stay human. The agent may prepare neutral material, e.g. the open items for a 1:1 agenda, but doesn't judge or decide.
7. **Transparency.** Docs and onboarding messages list what the agent processes, why, and for how long. People can see the data that concerns them.

Before a rollout, involve your data protection officer and, where one exists, the works council. This ADR is a design principle, not legal advice.

## Consequences

- ✅ Workload problems are still found early, as planning problems with a concrete fix rather than as judgments about people.
- ✅ Easier approval with data protection officers and works councils.
- ⚠️ Some "classic PM dashboard" numbers (individual utilisation, productivity) are deliberately not offered.
- ⚠️ The adaptive follow-up cadence (Phase 3) has to work with short-lived, per-person signals that people can switch off.
