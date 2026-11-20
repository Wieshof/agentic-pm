"""Several trackers as one: sources, routing and the isolation guard (ADR-0006).

`MultiTracker` implements `TrackerAdapter` on top of one adapter per source, so
the engine, briefs and write paths work unchanged:

* Every reference that comes out carries its source (`TaskRef.source`). A
  reference into another configured source (same tracker and project) is tagged
  with *that* source; everything else with the source it came from.
* Reads route by `ref.source`; `list_tasks("*")` is the union of all sources.
* A dependency link between two sources where either side is `strict` is not
  followed. It becomes the coverage warning `ISOLATION_BOUNDARY_BLOCKED`, so
  leads see that something was left out on purpose.
* Writes are guarded twice (rule 2): the write must act for the target's own
  source (`AuditMeta.source`), and its text must not mention, or quote a task
  title from, another source it may not know about. Into a `strict` source
  nothing about any other source is written; into an `open` one nothing about a
  `strict` source.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from agentic_pm.adapters.base import (
    AuditMeta,
    Edge,
    EventHandler,
    Task,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TrackerAdapter,
    TrackerEvent,
    Unsubscribe,
)
from agentic_pm.adapters.catalog import Capabilities
from agentic_pm.adapters.coverage import CoverageReport

if TYPE_CHECKING:
    from agentic_pm.config.team import TeamConfig

ISOLATION_CODE = "ISOLATION_BOUNDARY_BLOCKED"
MIN_TITLE = 8  # shorter titles ("Bug", "Release") are too common to count as a leak
_TOKEN_NAMES = (
    "AGENT_PM_GITHUB_TOKEN",
    "GITHUB_TOKEN",
    "AGENT_PM_GITEA_TOKEN",
    "OPENPROJECT_API_KEY",
)
_ORDER = {"none": 0, "convention": 1, "relation": 1, "field": 1, "native": 2}


class IsolationError(PermissionError):
    """A write would carry information across a source boundary it may not cross."""


def _weakest(caps: list[Capabilities]) -> Capabilities:
    """Combined capabilities: a limitation of any source is a limitation of the whole."""
    first = caps[0]
    data = first.model_dump()
    for field in ("dependencies", "estimates", "due_dates"):
        data[field] = min((getattr(c, field) for c in caps), key=lambda v: _ORDER.get(v, 1))
    data["multi_assignee"] = all(c.multi_assignee for c in caps)
    data["hierarchy"] = all(c.hierarchy for c in caps)
    data["events"] = "webhook" if all(c.events == "webhook" for c in caps) else "polling"
    data["writes"] = any(c.writes for c in caps)
    return Capabilities.model_validate(data)


class MultiTracker:
    name = "multi"

    def __init__(self, cfg: TeamConfig, adapters: Mapping[str, TrackerAdapter]) -> None:
        if not adapters:
            raise ValueError("MultiTracker needs at least one source")
        self.cfg = cfg
        self.adapters = dict(adapters)
        self.capabilities = _weakest([a.capabilities for a in self.adapters.values()])
        self.last_coverage: CoverageReport | None = None
        self._index = {
            (self.adapters[k].name, src.project): k
            for k, src in cfg.sources.items()
            if k in adapters
        }
        self._titles: dict[str, set[str]] = {k: set() for k in self.adapters}
        self._blocked: set[tuple[str, str]] = set()
        self._groups: dict[str, list[Task]] = {}

    # ------------------------------------------------------------ tagging

    def _adapter(self, ref: TaskRef) -> tuple[str, TrackerAdapter]:
        key = ref.source or self._index.get((ref.tracker, ref.project))
        if key is None or key not in self.adapters:
            raise TaskNotFoundError(f"{ref}: not in any configured source")
        return key, self.adapters[key]

    def tag(self, ref: TaskRef, origin: str) -> TaskRef:
        key = self._index.get((ref.tracker, ref.project), origin)
        return ref.model_copy(update={"source": key})

    def _task(self, task: Task, origin: str) -> Task:
        tagged = task.model_copy(update={"ref": self.tag(task.ref, origin)})
        if len(task.title.strip()) >= MIN_TITLE and tagged.ref.source:
            self._titles.setdefault(tagged.ref.source, set()).add(task.title.strip().casefold())
        return tagged

    def _coverage(self) -> CoverageReport:
        if self.last_coverage is None:
            self.last_coverage = CoverageReport(source="sources")
        return self.last_coverage

    def boundary_blocked(self, a: TaskRef, b: TaskRef) -> bool:
        """True (and reported once) if a link between a and b would cross a strict source."""
        if a.source == b.source:
            return False
        if not (self.cfg.is_strict(a.source) or self.cfg.is_strict(b.source)):
            return False
        self.report_blocked(a.label, a.source, b.label, b.source, a.id)
        return True

    def report_blocked(
        self, a: str, a_source: str | None, b: str, b_source: str | None, task_id: str
    ) -> None:
        """Record ISOLATION_BOUNDARY_BLOCKED once: shown to the waiting side's leads."""
        if (a, b) in self._blocked:
            return
        self._blocked.add((a, b))
        self._coverage().add(
            ISOLATION_CODE,
            f"{a} → {b}",
            f"{a} depends on {b} in another source; not followed because one side is "
            "isolated (strict)",
            task_id,
            source=a_source or "",
            other=b_source or "",
            a=a,
            b=b,
        )

    # -------------------------------------------------------------- reads

    async def list_tasks(self, project: str, *, include_closed: bool = False) -> list[Task]:
        keys = [project] if project in self.adapters else list(self.adapters)
        if project not in self.adapters:  # a fresh read of everything: fresh coverage
            self.last_coverage = CoverageReport(source="sources")
            self._blocked.clear()
            self._groups.clear()
        out: list[Task] = []
        for key in keys:
            adapter = self.adapters[key]
            tasks = await adapter.list_tasks(
                self.cfg.sources[key].project, include_closed=include_closed
            )
            out += [self._task(t, key) for t in tasks]
            sub: CoverageReport | None = getattr(adapter, "last_coverage", None)
            if sub is not None and project not in self.adapters:
                report = self._coverage()
                report.rows_scanned += sub.rows_scanned
                report.tasks_loaded += sub.tasks_loaded
                for w in sub.warnings:
                    report.warnings.append(
                        w.model_copy(
                            update={
                                "location": f"{key}: {w.location}",
                                "params": {**w.params, "source": key},
                            }
                        )
                    )
        return out

    async def get_task(self, ref: TaskRef) -> Task:
        key, adapter = self._adapter(ref)
        return self._task(await adapter.get_task(ref.bare()), key)

    async def list_dependencies(self, ref: TaskRef) -> list[Edge]:
        key, adapter = self._adapter(ref)
        out: list[Edge] = []
        for e in await adapter.list_dependencies(ref.bare()):
            src, dst = self.tag(e.source, key), self.tag(e.target, key)
            if self.boundary_blocked(src, dst):
                continue
            out.append(e.model_copy(update={"source": src, "target": dst}))
        return out

    async def group(self, source: str, kind: str, name: str) -> list[Task]:
        """All items (open and closed) of a milestone or label in one source."""
        if source not in self._groups:
            adapter = self.adapters[source]
            tasks = await adapter.list_tasks(self.cfg.sources[source].project, include_closed=True)
            self._groups[source] = [self._task(t, source) for t in tasks]
        want = name.strip().casefold()
        if kind == "milestone":
            return [t for t in self._groups[source] if (t.milestone or "").casefold() == want]
        return [t for t in self._groups[source] if want in (lbl.casefold() for lbl in t.labels)]

    # ------------------------------------------------------------- writes

    def guard(self, ref: TaskRef, text: str, meta: AuditMeta) -> str:
        """Refuse a write that would carry information across a boundary. Returns the source."""
        key, _ = self._adapter(ref)
        if meta.source != key:
            raise IsolationError(
                f"write to {ref.label} acts for source '{meta.source}', not '{key}'; refused"
            )
        target_strict = self.cfg.is_strict(key)
        folded = text.casefold()
        for other in self.adapters:
            if other == key or not (target_strict or self.cfg.is_strict(other)):
                continue
            if re.search(rf"(?<![\w-]){re.escape(other)}(?:#|:)", text):
                raise IsolationError(f"text for {ref.label} mentions source '{other}'; refused")
            if any(title in folded for title in self._titles.get(other, ())):
                raise IsolationError(
                    f"text for {ref.label} quotes a task title from source '{other}'; refused"
                )
        return key

    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None:
        key = self.guard(ref, markdown, meta)
        await self.adapters[key].add_comment(ref.bare(), markdown, meta)

    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task:
        key = self.guard(ref, " ".join(patch.add_labels + patch.remove_labels), meta)
        return self._task(await self.adapters[key].update_fields(ref.bare(), patch, meta), key)

    def subscribe(self, handler: EventHandler) -> Unsubscribe:
        stops: list[Unsubscribe] = []
        for key, adapter in self.adapters.items():

            async def tagged(event: TrackerEvent, key: str = key) -> None:
                await handler(event.model_copy(update={"ref": self.tag(event.ref, key)}))

            stops.append(adapter.subscribe(tagged))

        def stop() -> None:
            for s in stops:
                s()

        return stop


def source_env(cfg: TeamConfig, key: str, env: Mapping[str, str]) -> dict[str, str]:
    """The environment one source's adapter sees: AGENT_PM_<SOURCE>_TOKEN wins over the
    shared token names, so each client or department can have its own credentials."""
    out = dict(env)
    prefix = cfg.sources[key].env_prefix(key)
    if token := env.get(f"{prefix}TOKEN"):
        out.update(dict.fromkeys(_TOKEN_NAMES, token))
    if secret := env.get(f"{prefix}WEBHOOK_SECRET"):
        out["AGENT_PM_GITHUB_WEBHOOK_SECRET"] = secret
        out["AGENT_PM_GITEA_WEBHOOK_SECRET"] = secret
    return out


def build_tracker(cfg: TeamConfig, env: Mapping[str, str] | None = None) -> TrackerAdapter:
    """One adapter for `project:`, or a MultiTracker over every source."""
    from agentic_pm.adapters.registry import build_adapter

    env = os.environ if env is None else env
    if not cfg.multi:
        return build_adapter(cfg.project, env)
    return MultiTracker(
        cfg,
        {k: build_adapter(cfg.source_project(k), source_env(cfg, k, env)) for k in cfg.sources},
    )
