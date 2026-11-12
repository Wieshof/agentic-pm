from datetime import date

import pytest

from agentic_pm.adapters import (
    AuditMeta,
    Channel,
    InMemoryTracker,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TrackerAdapter,
    TrackerEvent,
)
from agentic_pm.audit import AUDIT_MARKER, RiskTier, classify_patch
from agentic_pm.mcp_server import TrackerTools, build_server, demo_tracker

META = AuditMeta(actor="sam", channel=Channel.VOICE, reason="test")


def ref(i: str) -> TaskRef:
    return TaskRef(tracker="memory", project="demo/app", id=i)


def test_memory_tracker_satisfies_protocol() -> None:
    assert isinstance(InMemoryTracker(), TrackerAdapter)


async def test_get_and_dependencies() -> None:
    t = demo_tracker()
    task = await t.get_task(ref("1"))
    assert task.title == "Auth service"
    edges = await t.list_dependencies(ref("2"))
    assert [e.source.id for e in edges] == ["1"]
    with pytest.raises(TaskNotFoundError):
        await t.get_task(ref("99"))


async def test_comment_has_audit_footer_and_emits_event() -> None:
    t = demo_tracker()
    seen: list[TrackerEvent] = []

    async def handler(e: TrackerEvent) -> None:
        seen.append(e)

    unsub = t.subscribe(handler)
    await t.add_comment(ref("1"), "### How it was solved\n- bigger Redis pool", META)
    unsub()
    await t.add_comment(ref("1"), "after unsubscribe", META)
    task = await t.get_task(ref("1"))
    assert AUDIT_MARKER in task.comments[0].body
    assert len(seen) == 1


async def test_returned_task_is_a_copy() -> None:
    t = demo_tracker()
    task = await t.get_task(ref("1"))
    task.labels.append("mutated")
    assert (await t.get_task(ref("1"))).labels == []


@pytest.mark.parametrize(
    ("task_id", "patch", "tier"),
    [
        ("1", TaskPatch(add_labels=["blocked"]), RiskTier.LOW),
        ("1", TaskPatch(due=date(2026, 12, 3)), RiskTier.MEDIUM),
        ("2", TaskPatch(due=date(2026, 12, 10)), RiskTier.HIGH),  # client-facing
        ("1", TaskPatch(assignees=["kim"]), RiskTier.HIGH),
        ("1", TaskPatch(assignees=["sam"]), RiskTier.LOW),  # unchanged
    ],
)
async def test_classify_patch(task_id: str, patch: TaskPatch, tier: RiskTier) -> None:
    task = await demo_tracker().get_task(ref(task_id))
    assert classify_patch(task, patch) is tier


async def test_tools_enforce_permission_tiers() -> None:
    tools = TrackerTools(demo_tracker())
    args = {"actor": "agent", "channel": "system", "reason": "slip detected"}

    low = await tools.update_fields("demo/app", "1", {"add_labels": ["blocker"]}, **args)
    assert low["applied"] and low["task"]["labels"] == ["blocker"]

    medium = await tools.update_fields("demo/app", "1", {"due": "2026-12-03"}, **args)
    assert not medium["applied"] and medium["tier"] == "medium"
    medium_ok = await tools.update_fields(
        "demo/app", "1", {"due": "2026-12-03"}, **args, owner_confirmed=True
    )
    assert medium_ok["applied"]

    high = await tools.update_fields(
        "demo/app", "2", {"due": "2026-12-10"}, **args, owner_confirmed=True
    )
    assert not high["applied"] and "team lead" in high["pending_approval"]
    high_ok = await tools.update_fields(
        "demo/app", "2", {"due": "2026-12-10"}, **args, approved_by="alex"
    )
    assert high_ok["applied"] and high_ok["task"]["due"] == "2026-12-10"


async def test_mcp_server_lists_tools() -> None:
    server = build_server(demo_tracker())
    names = {t.name for t in await server.list_tools()}
    assert names == {"get_task", "list_tasks", "list_dependencies", "add_comment", "update_fields"}
