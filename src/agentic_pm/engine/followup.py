"""Adaptive follow-up (#14): per question, never per person (ADR-0004, ADR-0005).

For every open completeness question (a `Gap`), decide whether to ask today,
on which channel, and whether the leads should hear about the *task*.

Stateless: the only memory is the ticket itself.
* When the agent first asks, it leaves one audited note on the ticket
  ("🙋 Asked Sam for a due date", reason `followup:MISSING_DUE`).
* Any later activity by the people asked (a comment, or a note the agent
  filed for them from chat or email) counts as an answer and restarts the count.
* "Ignored" = working days since then without an answer.
* Read-only projects can't leave the note; the task's last update is used instead.

Rhythm:
* Urgent questions (no owner, blocker done, blocked without reason, other
  work waits on it, or due soon): every brief, each as its own question.
* Everything else: bundled into the brief, and only once a week.
* After `escalate_after_ignored` unanswered nudges, the next channel in the
  person's `prefer` order is tried as well.
* Urgent and still unanswered after twice that: shown to the leads, about the
  task ("#12 still has no due date"), never as a count about a person.

Nothing here is stored per person, and nobody gets a responsiveness score.
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel

from agentic_pm.audit import audit_meta_in
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine.completeness import CompletenessReport, Gap
from agentic_pm.engine.dependencies import DependencyGraph

REASON_PREFIX = "followup:"
URGENT_CODES = frozenset(
    {"MISSING_OWNER", "OWNER_NOT_IN_TEAM", "BLOCKER_DONE", "BLOCKED_WITHOUT_REASON"}
)
NON_URGENT_EVERY = 5  # working days: once a week


class FollowUp(BaseModel):
    gap: Gap
    urgent: bool
    asked_on: date | None  # first asked (or last answered); None = never asked yet
    ignored: int  # working days since then without an answer
    due_today: bool  # ask in today's brief
    switch: bool  # also try the person's next channel
    stalled: bool  # urgent and long unanswered: tell the leads about the task

    @property
    def key(self) -> str:
        return f"{self.gap.task.ref}|{self.gap.code}"


def working_days(start: date, end: date) -> int:
    """Weekdays after `start`, up to and including `end`."""
    if end <= start:
        return 0
    return sum(1 for i in range(1, (end - start).days + 1) if (start + timedelta(i)).weekday() < 5)


def _anchor(cfg: TeamConfig, gap: Gap, writes: bool) -> date | None:
    asked: date | None = None
    answered: date | None = None
    logins = {cfg.people[h].login(h).lower() for h in gap.recipients if h in cfg.people}
    for c in gap.task.comments:
        day = c.created_at.date()
        meta = audit_meta_in(c.body)
        if meta is not None and meta.reason == f"{REASON_PREFIX}{gap.code}":
            asked = max(asked or day, day)
        elif (meta is not None and meta.actor in gap.recipients) or (
            meta is None and c.author.lower() in logins
        ):
            answered = max(answered or day, day)
    if asked is None:
        if writes:
            return None  # never asked: today is the first time
        updated = gap.task.updated_at
        return updated.date() if updated else None
    return max(asked, answered) if answered else asked


def plan(
    cfg: TeamConfig,
    report: CompletenessReport,
    graph: DependencyGraph,
    today: date,
    *,
    writes: bool,
) -> list[FollowUp]:
    horizon = today + timedelta(days=cfg.project.brief_horizon_days)
    out: list[FollowUp] = []
    for gap in report.gaps:
        task = gap.task
        urgent = (
            gap.code in URGENT_CODES
            or bool(graph.downstream(task.ref))
            or (task.due is not None and task.due <= horizon)
        )
        limit = min(
            (cfg.people[h].escalate_after_ignored for h in gap.recipients if h in cfg.people),
            default=3,
        )
        anchor = _anchor(cfg, gap, writes)
        ignored = working_days(anchor, today) if anchor else 0
        nudges = ignored if urgent else ignored // NON_URGENT_EVERY
        out.append(
            FollowUp(
                gap=gap,
                urgent=urgent,
                asked_on=anchor,
                ignored=ignored,
                due_today=urgent or ignored % NON_URGENT_EVERY == 0,
                switch=nudges >= limit,
                stalled=urgent and ignored >= 2 * limit,
            )
        )
    return out
