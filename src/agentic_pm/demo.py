"""Demo data for trying briefs and the dependency analyzer without any tracker.

Dates are relative to `today`, so the demo always shows something interesting.
People match `.agent-pm/team.example.yaml` (alex, sam, kim).
"""

from __future__ import annotations

from datetime import date, timedelta

from agentic_pm.adapters.base import Edge, EdgeKind, Task, TaskRef, TaskStatus
from agentic_pm.adapters.memory import InMemoryTracker


def demo_tracker(project: str, today: date) -> InMemoryTracker:
    def ref(i: int) -> TaskRef:
        return TaskRef(tracker="memory", project=project, id=str(i))

    def d(days: int) -> date:
        return today + timedelta(days=days)

    def task(i: int, title: str, who: str, due: int | None, **kw: object) -> Task:
        return Task(
            ref=ref(i),
            title=title,
            assignees=[who],
            due=d(due) if due is not None else None,
            **{"status": TaskStatus.OPEN, **kw},
        )

    tasks = [
        task(10, "Set up Redis monitoring", "sam", -5, status=TaskStatus.DONE),
        task(11, "Redis pool sizing", "sam", -2, status=TaskStatus.IN_PROGRESS, estimate_hours=4),
        task(12, "Fix auth timeout", "sam", 1, estimate_hours=8),
        task(13, "Login UI", "kim", 2, estimate_hours=16, client_facing=True),
        task(14, "Release notes", "alex", 3, estimate_hours=2),
        task(15, "Quarterly roadmap review", "alex", -1),
        task(16, "Docs cleanup", "alex", None),
        task(17, "API schema v2", "kim", 6),
        task(19, "Accessibility review", "kim", 2, estimate_hours=8),
        task(18, "SDK update", "sam", 7),
    ]

    def blocks(a: int, b: int) -> Edge:
        return Edge(source=ref(a), target=ref(b), kind=EdgeKind.BLOCKS)

    edges = [
        blocks(10, 11),  # done, so it no longer blocks
        blocks(11, 12),
        blocks(12, 13),
        blocks(13, 14),
        blocks(17, 18),
        blocks(18, 17),  # circular on purpose
    ]
    return InMemoryTracker(tasks=tasks, edges=edges)
