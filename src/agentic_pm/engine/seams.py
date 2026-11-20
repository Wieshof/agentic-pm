"""Seams between sources: who waits for what on the other side (ADR-0006).

The waiting side declares once what it waits for, in its own tracker:

* in the editable agent-pm block of the task text (ADR-0003)::

      ```agent-pm
      waits_for: eng:milestone/v2.0     # or eng#142, or eng:label/launch
      ```

* or, in a spreadsheet, in the `Depends On` column (`Task.waits_for`).

The agent then computes a deterministic roll-up of the other side (done/total,
items at risk, forecast date, buffer), with no language model and without
copying a single item across. A seam that touches a `strict` source is never
resolved: it becomes the coverage warning ISOLATION_BOUNDARY_BLOCKED.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel

from agentic_pm.adapters.base import CLOSED_STATUSES, Task, TaskNotFoundError

if TYPE_CHECKING:
    from agentic_pm.adapters.base import TrackerAdapter
    from agentic_pm.config.team import TeamConfig
    from agentic_pm.engine.dependencies import DependencyGraph

_BLOCK = re.compile(r"```agent-pm[ \t]*\r?\n(.*?)```", re.S)
_TARGET = re.compile(
    r"^(?P<source>[a-z][a-z0-9_-]{0,31})"
    r"(?:#(?P<id>[A-Za-z0-9][\w.-]*)|:(?P<kind>milestone|label)/(?P<name>\S.*))$"
)
# Mentions in free text, for suggestions: eng#142, eng:milestone/v2.0, eng:label/launch
_MENTION = re.compile(
    r"(?<![\w#/-])(?P<source>[a-z][a-z0-9_-]{0,31})"
    r"(?:#(?P<id>[A-Za-z0-9][\w-]*)|:(?P<kind>milestone|label)/(?P<name>[\w.-]+))"
)
SEAM_UNKNOWN = "SEAM_UNKNOWN_TARGET"


class Target(BaseModel):
    source: str
    kind: Literal["item", "milestone", "label"]
    name: str

    @property
    def text(self) -> str:
        if self.kind == "item":
            return f"{self.source}#{self.name}"
        return f"{self.source}:{self.kind}/{self.name}"


def parse_target(text: str) -> Target | None:
    m = _TARGET.match(text.strip())
    if not m:
        return None
    if m.group("id"):
        return Target(source=m.group("source"), kind="item", name=m.group("id"))
    kind: Literal["milestone", "label"] = "milestone" if m.group("kind") == "milestone" else "label"
    return Target(source=m.group("source"), kind=kind, name=m.group("name").strip())


def block_fields(text: str | None) -> dict[str, object]:
    """The agent-pm block of a task text as a mapping ({} if there is none or it's broken)."""
    for m in _BLOCK.finditer(text or ""):
        try:
            data = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def declared(task: Task) -> list[str]:
    """Everything this task says it waits for (structured field + agent-pm block)."""
    raw = block_fields(task.description).get("waits_for")
    items = raw if isinstance(raw, list) else [raw] if raw else []
    out = [*task.waits_for, *(str(x) for x in items)]
    return list(dict.fromkeys(x.strip() for x in out if str(x).strip()))


class RollUp(BaseModel):
    done: int
    total: int
    forecast: date | None  # latest projected finish of the open items
    undated: list[Task] = []  # open items with no date at all: no honest forecast
    late: list[Task] = []  # open items already overdue or at risk
    deciding: list[Task] = []  # open items that set the forecast (or have no date)


class Seam(BaseModel):
    waiting: Task
    target: Target
    status: Literal["ok", "blocked", "unknown", "empty"]
    rollup: RollUp | None = None

    @property
    def buffer(self) -> int | None:
        """Days between forecast and the waiting task's due date (negative = late)."""
        r = self.rollup
        if r is None or r.forecast is None or r.undated or self.waiting.due is None:
            return None
        return (self.waiting.due - r.forecast).days

    @property
    def done(self) -> bool:
        return (
            self.rollup is not None
            and self.rollup.total > 0
            and self.rollup.done == self.rollup.total
        )

    @property
    def at_risk(self) -> bool:
        """A business date depends on it and it isn't safe."""
        if self.status != "ok" or self.done or self.waiting.due is None:
            return False
        b = self.buffer
        return b is None or b < 0


async def _items(
    adapter: TrackerAdapter, graph: DependencyGraph, cfg: TeamConfig, t: Target
) -> list[Task]:
    from agentic_pm.adapters.multi import MultiTracker

    if t.kind == "item":
        ref = cfg.ref(t.name, t.source)
        if ref is None:
            return []
        if str(ref) in graph.tasks:
            return [graph.tasks[str(ref)]]
        try:
            return [await adapter.get_task(ref)]
        except TaskNotFoundError:
            return []
    if isinstance(adapter, MultiTracker):
        return await adapter.group(t.source, t.kind, t.name)
    return []


def rollup(items: list[Task], graph: DependencyGraph, today: date) -> RollUp:
    finish = graph.projected_finish(today)
    open_items = [t for t in items if t.status not in CLOSED_STATUSES]
    at_risk = {str(r.task.ref) for r in graph.risks(today)}
    dated: dict[str, date] = {}
    undated: list[Task] = []
    for t in open_items:
        f = finish.get(str(t.ref)) or (max(t.due, today) if t.due else None)
        if f is None:
            undated.append(t)
        else:
            dated[str(t.ref)] = f
    forecast = max(dated.values()) if dated else (today if not open_items else None)
    deciding = undated or [t for t in open_items if dated.get(str(t.ref)) == forecast]
    late = [t for t in open_items if (t.due and t.due < today) or str(t.ref) in at_risk]
    key = lambda t: t.ref.label  # noqa: E731
    return RollUp(
        done=len(items) - len(open_items),
        total=len(items),
        forecast=forecast,
        undated=sorted(undated, key=key),
        late=sorted(late, key=key),
        deciding=sorted(deciding, key=key),
    )


async def resolve(
    cfg: TeamConfig, adapter: TrackerAdapter, graph: DependencyGraph, today: date
) -> list[Seam]:
    """All seams of the open tasks in `graph`, resolved once per graph."""
    from agentic_pm.adapters.multi import MultiTracker

    if graph.seams is not None:
        return list(graph.seams)
    seams: list[Seam] = []
    if not cfg.multi or not isinstance(adapter, MultiTracker):
        graph.seams = seams
        return seams
    for task in sorted(graph.tasks.values(), key=lambda t: t.ref.label):
        for text in declared(task):
            target = parse_target(text)
            src = task.ref.source
            if target is None or target.source not in cfg.sources:
                adapter._coverage().add(
                    SEAM_UNKNOWN,
                    task.ref.label,
                    f"{task.ref.label} waits for '{text}', which isn't a source in team.yaml "
                    "(write e.g. eng#142 or eng:milestone/v2.0)",
                    task.ref.id,
                    source=src or "",
                    target=text,
                )
                seams.append(
                    Seam(
                        waiting=task,
                        target=target or Target(source="?", kind="item", name=text),
                        status="unknown",
                    )
                )
                continue
            if target.source != src and (cfg.is_strict(src) or cfg.is_strict(target.source)):
                adapter.report_blocked(task.ref.label, src, target.text, target.source, task.ref.id)
                seams.append(Seam(waiting=task, target=target, status="blocked"))
                continue
            items = await _items(adapter, graph, cfg, target)
            if not items:
                seams.append(Seam(waiting=task, target=target, status="empty"))
                continue
            for item in items:
                if item.status not in CLOSED_STATUSES:
                    graph.seam_waiters.setdefault(str(item.ref), []).append(task)
            seams.append(
                Seam(waiting=task, target=target, status="ok", rollup=rollup(items, graph, today))
            )
    graph.seams = seams
    return list(seams)


def mentions(task: Task, cfg: TeamConfig) -> list[Target]:
    """Seams the task text names but doesn't declare (suggestions, confirmed by a person).
    Only between sources a seam may connect; nothing is ever linked automatically."""
    if not cfg.multi:
        return []
    have = {t.text for x in declared(task) if (t := parse_target(x))}
    body = _BLOCK.sub(" ", task.description or "")
    out: dict[str, Target] = {}
    for m in _MENTION.finditer(f"{task.title}\n{body}"):
        source = m.group("source")
        if source not in cfg.sources or source == task.ref.source:
            continue
        if cfg.is_strict(source) or cfg.is_strict(task.ref.source):
            continue
        target = parse_target(m.group(0))
        if target is not None and target.text not in have:
            out.setdefault(target.text, target)
    return list(out.values())
