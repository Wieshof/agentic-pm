"""Dependency Graph Analyzer (read-only).

Builds the "blocks" graph live from a tracker and answers:

* `risks(today)`   - which open tasks will probably miss their due date because
                     something upstream is late (also transitively, A -> B -> C)?
* `impact_of(...)` - what-if: if this task moves to a new date, who is affected?
* `cycles()`       - circular dependencies that make scheduling impossible.

Scheduling model (deliberately simple and explainable):

* Calendar days, no weekends/holidays yet.
* A task needs `ceil(estimate_hours / 8)` days, at least 1 day. No estimate = 1 day.
* A task can start the day after all open blockers finish.
* An open task that is already overdue is assumed to finish today at the earliest.
* Closed tasks never block.
"""

from __future__ import annotations

import asyncio
import math
from collections import defaultdict, deque
from datetime import date, timedelta

from pydantic import BaseModel

from agentic_pm.adapters.base import (
    CLOSED_STATUSES,
    Edge,
    EdgeKind,
    Task,
    TaskNotFoundError,
    TaskRef,
    TrackerAdapter,
)
from agentic_pm.adapters.catalog import Capabilities

HOURS_PER_DAY = 8


def duration_days(task: Task) -> int:
    if not task.estimate_hours:
        return 1
    return max(1, math.ceil(task.estimate_hours / HOURS_PER_DAY))


class Risk(BaseModel):
    task: Task
    blocker: Task
    projected_finish: date
    days_late: int
    proposed_due: date
    reason: str


class DependencyGraph:
    def __init__(
        self, tasks: list[Task], edges: list[Edge], capabilities: Capabilities | None = None
    ) -> None:
        self.capabilities = capabilities
        self.tasks: dict[str, Task] = {
            str(t.ref): t for t in tasks if t.status not in CLOSED_STATUSES
        }
        self._up: dict[str, set[str]] = defaultdict(set)
        self._down: dict[str, set[str]] = defaultdict(set)
        for e in edges:
            s, t = str(e.source), str(e.target)
            if e.kind is EdgeKind.BLOCKS and s in self.tasks and t in self.tasks and s != t:
                self._up[t].add(s)
                self._down[s].add(t)

    @classmethod
    async def build(
        cls, adapter: TrackerAdapter, project: str, concurrency: int = 8
    ) -> DependencyGraph:
        """Fetch all open tasks of `project` and their dependencies, live."""
        tasks = {str(t.ref): t for t in await adapter.list_tasks(project)}
        limit = asyncio.Semaphore(concurrency)

        async def deps(ref: TaskRef) -> list[Edge]:
            async with limit:
                return await adapter.list_dependencies(ref)

        if adapter.capabilities.dependencies == "none":
            return cls(list(tasks.values()), [], adapter.capabilities)
        per_task = await asyncio.gather(*(deps(t.ref) for t in tasks.values()))
        edges: list[Edge] = [e for group in per_task for e in group]
        # Blockers in other projects/repos: fetch them so they can block, too.
        for e in edges:
            for ref in (e.source, e.target):
                if str(ref) not in tasks:
                    try:
                        tasks[str(ref)] = await adapter.get_task(ref)
                    except TaskNotFoundError:
                        continue
        return cls(list(tasks.values()), edges, adapter.capabilities)

    # -------------------------------------------------------------- queries

    def task(self, ref: TaskRef) -> Task:
        return self.tasks[str(ref)]

    def blockers(self, ref: TaskRef) -> list[Task]:
        return [self.tasks[k] for k in sorted(self._up[str(ref)])]

    def downstream(self, ref: TaskRef) -> list[Task]:
        """All tasks transitively waiting for `ref` (breadth-first)."""
        seen: set[str] = set()
        queue = deque(self._down[str(ref)])
        order: list[str] = []
        while queue:
            k = queue.popleft()
            if k in seen:
                continue
            seen.add(k)
            order.append(k)
            queue.extend(self._down[k])
        return [self.tasks[k] for k in order]

    def limitations(self) -> list[str]:
        """What this tracker cannot tell us (shown to leads, so silence is never mistaken for
        'all good')."""
        caps = self.capabilities
        if caps is None:
            return []
        out = []
        if caps.dependencies == "none":
            out.append("dependencies")
        if caps.due_dates == "none":
            out.append("due_dates")
        if caps.estimates == "none":
            out.append("estimates")
        return out

    def cycles(self) -> list[list[TaskRef]]:
        """Strongly connected components with more than one task (Tarjan)."""
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        result: list[list[TaskRef]] = []
        counter = 0

        def visit(v: str) -> None:
            nonlocal counter
            index[v] = low[v] = counter
            counter += 1
            stack.append(v)
            on_stack.add(v)
            for w in self._down[v]:
                if w not in index:
                    visit(w)
                    low[v] = min(low[v], low[w])
                elif w in on_stack:
                    low[v] = min(low[v], index[w])
            if low[v] == index[v]:
                comp: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    result.append([self.tasks[k].ref for k in sorted(comp)])

        for v in sorted(self.tasks):
            if v not in index:
                visit(v)
        return result

    # ----------------------------------------------------------- scheduling

    def _topo_order(self, skip: set[str]) -> list[str]:
        indeg = {k: len(self._up[k] - skip) for k in self.tasks if k not in skip}
        queue = deque(sorted(k for k, d in indeg.items() if d == 0))
        order: list[str] = []
        while queue:
            k = queue.popleft()
            order.append(k)
            for d in sorted(self._down[k]):
                if d in indeg:
                    indeg[d] -= 1
                    if indeg[d] == 0:
                        queue.append(d)
        return order

    def _project(
        self, today: date, overrides: dict[str, date] | None = None
    ) -> tuple[dict[str, date | None], dict[str, str]]:
        """Projected finish date per task, plus the upstream task that drives it."""
        overrides = overrides or {}
        in_cycle = {str(r) for comp in self.cycles() for r in comp}
        finish: dict[str, date | None] = {}
        driver: dict[str, str] = {}
        for k in self._topo_order(in_cycle):
            t = self.tasks[k]
            due = overrides.get(k, t.due)
            own = max(due, today) if due else None
            best_up: tuple[date, str] | None = None
            for u in self._up[k]:
                f = finish.get(u)
                if f is not None and (best_up is None or f > best_up[0]):
                    best_up = (f, u)
            candidate = best_up[0] + timedelta(days=duration_days(t)) if best_up else None
            if candidate and (own is None or candidate > own):
                finish[k] = candidate
                assert best_up is not None
                driver[k] = best_up[1]
            else:
                finish[k] = own
        return finish, driver

    def risks(self, today: date) -> list[Risk]:
        """Open tasks projected to finish after their due date because of a blocker."""
        return self._risks(today, None)

    def impact_of(self, ref: TaskRef, new_due: date, today: date) -> list[Risk]:
        """What-if: tasks that become (more) late if `ref` moves to `new_due`."""
        before = {str(r.task.ref): r.days_late for r in self._risks(today, None)}
        after = self._risks(today, {str(ref): new_due})
        downstream = {str(t.ref) for t in self.downstream(ref)}
        return [
            r
            for r in after
            if str(r.task.ref) in downstream and r.days_late > before.get(str(r.task.ref), 0)
        ]

    def _risks(self, today: date, overrides: dict[str, date] | None) -> list[Risk]:
        finish, driver = self._project(today, overrides)
        out: list[Risk] = []
        for k, up in driver.items():
            t = self.tasks[k]
            f = finish[k]
            if t.due is None or f is None or f <= t.due:
                continue
            blocker = self.tasks[up]
            blocker_due = (overrides or {}).get(up, blocker.due)
            if blocker_due and blocker_due < today:
                reason = "blocker_overdue"
            elif self._up[up] and up in driver:
                reason = "chain_delay"
            else:
                reason = "blocker_due_too_late"
            out.append(
                Risk(
                    task=t,
                    blocker=blocker,
                    projected_finish=f,
                    days_late=(f - t.due).days,
                    proposed_due=f,
                    reason=reason,
                )
            )
        return sorted(out, key=lambda r: (-r.days_late, str(r.task.ref)))
