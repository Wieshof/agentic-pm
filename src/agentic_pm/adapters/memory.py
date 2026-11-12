"""In-memory tracker. Used for tests, demos and as the reference adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_pm.adapters.base import (
    CLOSED_STATUSES,
    AuditMeta,
    Comment,
    Edge,
    EventHandler,
    Task,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TrackerEvent,
    TrackerEventKind,
    Unsubscribe,
)
from agentic_pm.audit import render_audit_footer


class InMemoryTracker:
    name = "memory"

    def __init__(self, tasks: list[Task] | None = None, edges: list[Edge] | None = None) -> None:
        self._tasks: dict[str, Task] = {str(t.ref): t for t in tasks or []}
        self._edges: list[Edge] = list(edges or [])
        self._handlers: list[EventHandler] = []

    def _require(self, ref: TaskRef) -> Task:
        try:
            return self._tasks[str(ref)]
        except KeyError:
            raise TaskNotFoundError(str(ref)) from None

    async def _emit(self, kind: TrackerEventKind, ref: TaskRef, fields: list[str]) -> None:
        evt = TrackerEvent(kind=kind, ref=ref, changed_fields=fields, at=datetime.now(UTC))
        for h in list(self._handlers):
            await h(evt)

    async def get_task(self, ref: TaskRef) -> Task:
        return self._require(ref).model_copy(deep=True)

    async def list_tasks(self, project: str, *, include_closed: bool = False) -> list[Task]:
        return [
            t.model_copy(deep=True)
            for t in self._tasks.values()
            if t.ref.project == project and (include_closed or t.status not in CLOSED_STATUSES)
        ]

    async def list_dependencies(self, ref: TaskRef) -> list[Edge]:
        self._require(ref)
        return [e for e in self._edges if ref in (e.source, e.target)]

    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None:
        task = self._require(ref)
        body = f"{markdown}\n\n{render_audit_footer(meta)}"
        comment = Comment(author="agent-pm", body=body, created_at=datetime.now(UTC))
        self._tasks[str(ref)] = task.model_copy(update={"comments": [*task.comments, comment]})
        await self._emit(TrackerEventKind.COMMENTED, ref, ["comments"])

    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task:
        task = self._require(ref)
        update: dict[str, object] = {}
        for field in ("status", "due", "estimate_hours", "assignees"):
            value = getattr(patch, field)
            if value is not None:
                update[field] = value
        if patch.add_labels or patch.remove_labels:
            labels = [lbl for lbl in task.labels if lbl not in patch.remove_labels]
            labels += [lbl for lbl in patch.add_labels if lbl not in labels]
            update["labels"] = labels
        new = task.model_copy(update=update)
        self._tasks[str(ref)] = new
        await self._emit(TrackerEventKind.UPDATED, ref, sorted(update))
        await self.add_comment(ref, f"Updated fields: {', '.join(sorted(update))}", meta)
        return self._tasks[str(ref)].model_copy(deep=True)

    def subscribe(self, handler: EventHandler) -> Unsubscribe:
        self._handlers.append(handler)
        return lambda: self._handlers.remove(handler)
