"""Deadline collisions: task-centric capacity check (ADR-0004).

For each person, walk their open tasks by due date. If the estimated work due
by a date is more than the working hours left until then, those tasks collide.
The result names tasks and suggests a fix ("move #31 or hand it over"); it
never stores history or computes utilisation scores for people.

Assumptions: Mon-Fri working days, `hours_per_day` (default 8), tasks without
an estimate count as one day, today counts as a full working day.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from pydantic import BaseModel

from agentic_pm.adapters.base import Task
from agentic_pm.engine.dependencies import HOURS_PER_DAY, DependencyGraph

# Who a task's assignee is: (task, login) -> person key. Default: the login itself.
Who = Callable[[Task, str], str]


def _by_login(_: Task, login: str) -> str:
    return login.lower()  # "Sam" and "sam" are the same person


class Collision(BaseModel):
    login: str  # the person: team handle when known, else the tracker login
    tasks: list[Task]  # sorted by due date
    by: date  # the due date where it stops fitting
    needed_hours: float
    available_hours: float
    critical: list[str]  # ids of tasks others are waiting for
    suggestion_id: str | None  # the task that is easiest to move / hand over


def working_days(start: date, end: date) -> int:
    """Mon-Fri days from start to end, both inclusive (0 if end < start)."""
    days = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            days += 1
        d += timedelta(days=1)
    return days


def find_collisions(
    graph: DependencyGraph,
    today: date,
    *,
    horizon_days: int = 14,
    hours_per_day: float = HOURS_PER_DAY,
    who: Who = _by_login,
) -> list[Collision]:
    by_person = _due_by_person(graph, today + timedelta(days=horizon_days), who)

    out: list[Collision] = []
    for login, tasks in sorted(by_person.items()):
        tasks.sort(key=lambda t: (t.due or today, t.ref.id))
        if len(tasks) < 2:
            continue
        needed = 0.0
        for i, t in enumerate(tasks):
            needed += t.estimate_hours or hours_per_day
            until = max(t.due or today, today)
            available = working_days(today, until) * hours_per_day
            if needed > available and i >= 1:
                involved = tasks[: i + 1]
                critical = [x.ref.id for x in involved if graph.downstream(x.ref)]
                movable = [x for x in reversed(involved) if x.ref.id not in critical]
                out.append(
                    Collision(
                        login=login,
                        tasks=involved,
                        by=until,
                        needed_hours=needed,
                        available_hours=available,
                        critical=critical,
                        suggestion_id=movable[0].ref.id if movable else None,
                    )
                )
                break
    return out


def _due_by_person(graph: DependencyGraph, horizon: date, who: Who) -> dict[str, list[Task]]:
    by_person: dict[str, list[Task]] = {}
    for t in graph.tasks.values():
        if t.due is None or t.due > horizon:
            continue
        for person in dict.fromkeys(who(t, login) for login in t.assignees):
            by_person.setdefault(person, []).append(t)
    return by_person


class SameDay(BaseModel):
    """Tasks from different sources due on the same day for one person (ADR-0006, rule 4):
    tasks and a date, never a utilisation figure."""

    person: str
    due: date
    tasks: list[Task]


def same_day_across_sources(
    graph: DependencyGraph, today: date, *, horizon_days: int = 14, who: Who = _by_login
) -> list[SameDay]:
    out: list[SameDay] = []
    by_person = _due_by_person(graph, today + timedelta(days=horizon_days), who)
    for person, tasks in sorted(by_person.items()):
        by_day: dict[date, list[Task]] = {}
        for t in tasks:
            if t.due is not None and t.due >= today:
                by_day.setdefault(t.due, []).append(t)
        for day, group in sorted(by_day.items()):
            if len({t.ref.source for t in group}) > 1:
                group.sort(key=lambda t: (t.ref.source or "", t.ref.id))
                out.append(SameDay(person=person, due=day, tasks=group))
    return out
