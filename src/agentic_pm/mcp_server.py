"""MCP tool surface over any `TrackerAdapter`.

The same tools are used by the reasoning engine and by external agents.
Writes go through the permission tiers in `agentic_pm.audit`: anything the
caller is not allowed to apply comes back as `pending_approval` instead of
being executed.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.mcpserver import MCPServer

from agentic_pm.actions import Guard
from agentic_pm.adapters.base import (
    AuditMeta,
    Channel,
    Edge,
    EdgeKind,
    ReadOnlyAdapterError,
    Task,
    TaskPatch,
    TaskRef,
    TaskStatus,
    TrackerAdapter,
)
from agentic_pm.approvals import InvalidToken
from agentic_pm.audit import RiskTier, classify_patch


class TrackerTools:
    """Plain-Python implementation of the MCP tools (easy to unit-test)."""

    def __init__(self, adapter: TrackerAdapter | Guard, guard: Guard | None = None) -> None:
        if isinstance(adapter, Guard):
            self.guard: Guard | None = adapter
            self.adapter: TrackerAdapter = adapter.adapter
        else:
            self.adapter = adapter
            self.guard = guard

    def _require_writes(self) -> None:
        if self.guard is not None:
            self.guard._require_writes()
        elif not self.adapter.capabilities.writes:
            raise ReadOnlyAdapterError(
                "writes are disabled for this project (set project.allow_writes: true)"
            )

    def _ref(self, project: str, task_id: str) -> TaskRef:
        """`project` is the repo, or the source key with several trackers (ADR-0006)."""
        from agentic_pm.adapters.multi import MultiTracker

        if isinstance(self.adapter, MultiTracker) and project in self.adapter.adapters:
            src = self.adapter.cfg.sources[project]
            sub = self.adapter.adapters[project]
            return TaskRef(tracker=sub.name, project=src.project, id=task_id, source=project)
        return TaskRef(tracker=self.adapter.name, project=project, id=task_id)

    async def get_task(self, project: str, task_id: str) -> dict[str, Any]:
        task = await self.adapter.get_task(self._ref(project, task_id))
        return task.model_dump(mode="json")

    async def list_tasks(self, project: str, include_closed: bool = False) -> list[dict[str, Any]]:
        tasks = await self.adapter.list_tasks(project, include_closed=include_closed)
        return [t.model_dump(mode="json", exclude={"comments", "description"}) for t in tasks]

    async def list_dependencies(self, project: str, task_id: str) -> list[dict[str, Any]]:
        edges = await self.adapter.list_dependencies(self._ref(project, task_id))
        return [e.model_dump(mode="json") for e in edges]

    async def add_comment(
        self, project: str, task_id: str, markdown: str, actor: str, channel: str, reason: str
    ) -> dict[str, Any]:
        self._require_writes()
        ref = self._ref(project, task_id)
        meta = AuditMeta(actor=actor, channel=Channel(channel), reason=reason, source=ref.source)
        if self.guard is not None:
            await self.guard.comment(ref, markdown, meta)
        else:
            await self.adapter.add_comment(ref, markdown, meta)
        return {"applied": True, "tier": "low"}

    async def update_fields(
        self,
        project: str,
        task_id: str,
        patch: dict[str, Any],
        actor: str,
        channel: str,
        reason: str,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        self._require_writes()
        ref = self._ref(project, task_id)
        parsed = TaskPatch.model_validate(patch)
        meta = AuditMeta(actor=actor, channel=Channel(channel), reason=reason, source=ref.source)

        if approval_token is not None:
            if self.guard is None or self.guard.signer is None:
                return {
                    "applied": False,
                    "error": (
                        "Approval token verification requires a configured Guard with signing key."
                    ),
                }
            try:
                req = self.guard.signer.verify(approval_token)
            except InvalidToken as e:
                return {"applied": False, "error": f"Invalid approval token: {e}"}

            if req.ref != ref:
                return {
                    "applied": False,
                    "error": f"Approval token is for {req.ref}, not {ref}.",
                }

            outcome = await self.guard.decide(approval_token, approve=True)
            if outcome.applied:
                return {
                    "applied": True,
                    "tier": outcome.tier.value,
                    "task": outcome.task.model_dump(mode="json") if outcome.task else None,
                }
            return {
                "applied": False,
                "tier": outcome.tier.value,
                "status": outcome.status,
                "message": outcome.message,
            }

        current = await self.adapter.get_task(ref)
        tier = classify_patch(current, parsed)
        if tier is RiskTier.LOW:
            if self.guard is not None:
                outcome = await self.guard.propose(ref, parsed, meta)
                return {
                    "applied": True,
                    "tier": tier.value,
                    "task": outcome.task.model_dump(mode="json") if outcome.task else None,
                }
            updated = await self.adapter.update_fields(ref, parsed, meta)
            return {"applied": True, "tier": tier.value, "task": updated.model_dump(mode="json")}

        who = "the task owner" if tier is RiskTier.MEDIUM else "a team lead"
        result: dict[str, Any] = {
            "applied": False,
            "tier": tier.value,
            "pending_approval": f"Change needs confirmation from {who}.",
        }
        if self.guard is not None and self.guard.signer is not None:
            outcome = await self.guard.propose(ref, parsed, meta)
            result["status"] = outcome.status
            result["waiting_for"] = outcome.waiting_for
        return result


def build_server(adapter: TrackerAdapter | Guard, guard: Guard | None = None) -> MCPServer:
    tools = TrackerTools(adapter, guard=guard)
    server = MCPServer("agentic-pm-tracker")

    @server.tool()
    async def get_task(project: str, task_id: str) -> dict[str, Any]:
        """Fetch one task live from the tracker."""
        return await tools.get_task(project, task_id)

    @server.tool()
    async def list_tasks(project: str, include_closed: bool = False) -> list[dict[str, Any]]:
        """List tasks of a project (open only by default), without comments."""
        return await tools.list_tasks(project, include_closed)

    @server.tool()
    async def list_dependencies(project: str, task_id: str) -> list[dict[str, Any]]:
        """List dependency edges (blocks / relates / parent_of) touching a task."""
        return await tools.list_dependencies(project, task_id)

    @server.tool()
    async def add_comment(
        project: str, task_id: str, markdown: str, actor: str, channel: str, reason: str
    ) -> dict[str, Any]:
        """Append a Markdown comment with an audit footer (low-risk, runs automatically)."""
        return await tools.add_comment(project, task_id, markdown, actor, channel, reason)

    @server.tool()
    async def update_fields(
        project: str,
        task_id: str,
        patch: dict[str, Any],
        actor: str,
        channel: str,
        reason: str,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        """Update status / due / estimate / assignees / labels, subject to permission tiers.

        Returns `pending_approval` instead of applying when the change's risk tier
        requires confirmation that has not been given. For medium/high risk changes,
        a cryptographic approval_token is required.
        """
        return await tools.update_fields(
            project, task_id, patch, actor, channel, reason, approval_token=approval_token
        )

    return server


def demo_tracker() -> TrackerAdapter:
    from agentic_pm.adapters.memory import InMemoryTracker

    def ref(i: str) -> TaskRef:
        return TaskRef(tracker="memory", project="demo/app", id=i)

    return InMemoryTracker(
        tasks=[
            Task(
                ref=ref("1"),
                title="Auth service",
                status=TaskStatus.IN_PROGRESS,
                assignees=["sam"],
                due=date(2026, 12, 1),
            ),
            Task(
                ref=ref("2"),
                title="Login UI",
                status=TaskStatus.OPEN,
                assignees=["kim"],
                due=date(2026, 12, 8),
                client_facing=True,
            ),
        ],
        edges=[Edge(source=ref("1"), target=ref("2"), kind=EdgeKind.BLOCKS)],
    )


def run_demo() -> None:
    build_server(demo_tracker()).run()
