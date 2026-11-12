"""Shared contract tests every tracker adapter must pass.

Use it in your adapter's test file (built-in or plugin):

    from agentic_pm.testing import AdapterContract

    class TestJiraContract(AdapterContract):
        project = "APP"
        existing_id = "APP-1"      # an open task in your recorded fixtures
        missing_id = "APP-999"     # must raise TaskNotFoundError

        async def make(self) -> TrackerAdapter:
            return JiraAdapter(..., transport=httpx.MockTransport(recorded_routes))

Recorded API responses keep the suite runnable without accounts.
"""

from __future__ import annotations

import pytest

from agentic_pm.adapters.base import (
    CLOSED_STATUSES,
    AuditMeta,
    Channel,
    ReadOnlyAdapterError,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TrackerAdapter,
)
from agentic_pm.adapters.catalog import Capabilities, load_catalog


class AdapterContract:
    project: str
    existing_id: str
    missing_id: str

    async def make(self) -> TrackerAdapter:
        raise NotImplementedError

    def ref(self, adapter: TrackerAdapter, task_id: str) -> TaskRef:
        return TaskRef(tracker=adapter.name, project=self.project, id=task_id)

    async def test_implements_protocol(self) -> None:
        a = await self.make()
        assert isinstance(a, TrackerAdapter)
        assert a.name
        assert isinstance(a.capabilities, Capabilities)

    async def test_capabilities_match_catalog(self) -> None:
        a = await self.make()
        entry = load_catalog().get(a.name)
        if entry is None:
            pytest.skip(f"'{a.name}' is not in the catalog (plugin or test adapter)")
        declared = a.capabilities.model_dump(exclude={"writes"})
        assert declared == entry.capabilities().model_dump(exclude={"writes"}), (
            "adapter capabilities and catalog.yaml disagree; update one of them"
        )

    async def test_list_tasks_returns_open_tasks_of_project(self) -> None:
        a = await self.make()
        tasks = await a.list_tasks(self.project)
        assert tasks, "fixtures should contain at least one open task"
        for t in tasks:
            assert t.ref.tracker == a.name
            assert t.ref.project == self.project
            assert t.status not in CLOSED_STATUSES
            assert t.title

    async def test_get_task_matches(self) -> None:
        a = await self.make()
        t = await a.get_task(self.ref(a, self.existing_id))
        assert t.ref == self.ref(a, self.existing_id)

    async def test_missing_task_raises(self) -> None:
        a = await self.make()
        with pytest.raises(TaskNotFoundError):
            await a.get_task(self.ref(a, self.missing_id))

    async def test_dependencies_touch_the_task(self) -> None:
        a = await self.make()
        ref = self.ref(a, self.existing_id)
        edges = await a.list_dependencies(ref)
        for e in edges:
            assert ref in (e.source, e.target)

    async def test_writes_respect_capabilities(self) -> None:
        a = await self.make()
        if a.capabilities.writes:
            pytest.skip("adapter supports writes; covered by its own tests")
        meta = AuditMeta(actor="agent", channel=Channel.SYSTEM, reason="contract test")
        ref = self.ref(a, self.existing_id)
        with pytest.raises(ReadOnlyAdapterError):
            await a.add_comment(ref, "hello", meta)
        with pytest.raises(ReadOnlyAdapterError):
            await a.update_fields(ref, TaskPatch(add_labels=["x"]), meta)
