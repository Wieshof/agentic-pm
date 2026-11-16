import re
from datetime import date
from pathlib import Path

import pytest

from agentic_pm.actions import Guard
from agentic_pm.adapters import (
    AuditMeta,
    Channel,
    InMemoryTracker,
    ReadOnlyAdapterError,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TrackerAdapter,
    TrackerEvent,
)
from agentic_pm.adapters.catalog import Capabilities
from agentic_pm.approvals import Signer
from agentic_pm.audit import AUDIT_MARKER, RiskTier, classify_patch
from agentic_pm.config import load_team_config
from agentic_pm.mcp_server import TrackerTools, build_server, demo_tracker
from agentic_pm.notify import RecordingNotifier

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

    # Low-risk mutations run directly
    low = await tools.update_fields("demo/app", "1", {"add_labels": ["blocker"]}, **args)
    assert low["applied"] and low["task"]["labels"] == ["blocker"]

    # Medium-risk mutations without token are not applied
    medium = await tools.update_fields("demo/app", "1", {"due": "2026-12-03"}, **args)
    assert not medium["applied"] and medium["tier"] == "medium"
    assert "the task owner" in medium["pending_approval"]

    # Passing owner_confirmed is rejected (parameter not exposed / no self-attestation bypass)
    with pytest.raises(TypeError, match="unexpected keyword argument 'owner_confirmed'"):
        await tools.update_fields(
            "demo/app",
            "1",
            {"due": "2026-12-03"},
            **args,
            owner_confirmed=True,  # type: ignore[call-arg]
        )

    # High-risk mutations without token are not applied
    high = await tools.update_fields("demo/app", "2", {"due": "2026-12-10"}, **args)
    assert not high["applied"] and "team lead" in high["pending_approval"]

    # Passing approved_by is rejected (parameter not exposed / no self-attestation bypass)
    with pytest.raises(TypeError, match="unexpected keyword argument 'approved_by'"):
        await tools.update_fields(
            "demo/app",
            "2",
            {"due": "2026-12-10"},
            **args,
            approved_by="alex",  # type: ignore[call-arg]
        )


async def test_tools_with_guard_and_cryptographic_approval() -> None:
    example = Path(__file__).parents[1] / ".agent-pm" / "team.example.yaml"
    cfg = load_team_config(example)
    tracker = demo_tracker()
    notifier = RecordingNotifier()
    signer = Signer("k" * 32)
    guard = Guard(cfg, tracker, notifier, signer)
    tools = TrackerTools(tracker, guard=guard)
    args = {"actor": "agent", "channel": "system", "reason": "slip detected"}

    # Medium-risk: propose dispatches approval request to the owner (sam)
    medium = await tools.update_fields("demo/app", "1", {"due": "2026-12-03"}, **args)
    assert not medium["applied"] and medium["status"] == "pending"
    assert medium["waiting_for"] == ["sam"]
    assert len(notifier.sent) == 1
    msg = notifier.sent[0]
    token = re.search(r"/approve\?t=([A-Za-z0-9_.-]+)", msg.text).group(1)  # type: ignore[union-attr]

    # Supplying forged or invalid token fails
    forged = await tools.update_fields(
        "demo/app", "1", {"due": "2026-12-03"}, **args, approval_token="invalid.signature"
    )
    assert not forged["applied"]
    assert "Invalid approval token" in forged["error"]

    # Supplying token for a different task fails
    wrong_task = await tools.update_fields(
        "demo/app", "2", {"due": "2026-12-03"}, **args, approval_token=token
    )
    assert not wrong_task["applied"]
    assert "Approval token is for" in wrong_task["error"]

    # Supplying valid token applies the change
    ok = await tools.update_fields(
        "demo/app", "1", {"due": "2026-12-03"}, **args, approval_token=token
    )
    assert ok["applied"] and ok["task"]["due"] == "2026-12-03"

    # Replay is rejected as stale
    replay = await tools.update_fields(
        "demo/app", "1", {"due": "2026-12-03"}, **args, approval_token=token
    )
    assert not replay["applied"] and replay["status"] == "stale"


async def test_tools_respects_readonly_adapter() -> None:
    class ReadOnlyTracker(InMemoryTracker):
        capabilities = Capabilities(
            dependencies="native",
            estimates="native",
            due_dates="native",
            multi_assignee=True,
            hierarchy=True,
            events="webhook",
            writes=False,
        )

    ro_tracker = ReadOnlyTracker()
    tools = TrackerTools(ro_tracker)
    args = {"actor": "agent", "channel": "system", "reason": "test"}

    with pytest.raises(ReadOnlyAdapterError):
        await tools.add_comment("demo/app", "1", "hello", **args)

    with pytest.raises(ReadOnlyAdapterError):
        await tools.update_fields("demo/app", "1", {"add_labels": ["test"]}, **args)


async def test_mcp_server_lists_tools() -> None:
    server = build_server(demo_tracker())
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert names == {"get_task", "list_tasks", "list_dependencies", "add_comment", "update_fields"}

    update_tool = next(t for t in tools if t.name == "update_fields")
    props = update_tool.input_schema["properties"]
    assert "owner_confirmed" not in props
    assert "approved_by" not in props
    assert "approval_token" in props


def test_is_allowed_prevents_self_attestation() -> None:
    from agentic_pm.audit import is_allowed

    meta_plain = AuditMeta(actor="agent", channel=Channel.SYSTEM, reason="test")
    meta_claimed = AuditMeta(
        actor="agent", channel=Channel.SYSTEM, reason="test", approved_by="lead_handle"
    )

    # LOW tier is always allowed
    assert is_allowed(RiskTier.LOW, meta_plain) is True
    assert is_allowed(RiskTier.LOW, meta_claimed) is True

    # MEDIUM tier: requires owner_confirmed=True; setting approved_by alone does NOT allow
    assert is_allowed(RiskTier.MEDIUM, meta_plain, owner_confirmed=False) is False
    assert is_allowed(RiskTier.MEDIUM, meta_claimed, owner_confirmed=False) is False
    assert is_allowed(RiskTier.MEDIUM, meta_plain, owner_confirmed=True) is True

    # HIGH tier: cannot proceed immediately under any self-attested circumstance
    assert is_allowed(RiskTier.HIGH, meta_plain, owner_confirmed=False) is False
    assert is_allowed(RiskTier.HIGH, meta_plain, owner_confirmed=True) is False
    assert is_allowed(RiskTier.HIGH, meta_claimed, owner_confirmed=False) is False
    assert is_allowed(RiskTier.HIGH, meta_claimed, owner_confirmed=True) is False


async def test_mcp_server_call_tool_workflow() -> None:
    from mcp.types import CallToolResult

    server = build_server(demo_tracker())
    args = {
        "project": "demo/app",
        "task_id": "1",
        "patch": {"due": "2026-12-03"},
        "actor": "agent",
        "channel": "system",
        "reason": "slip detected",
    }
    res = await server.call_tool("update_fields", args)
    assert isinstance(res, CallToolResult)
    assert res.structured_content is not None
    assert res.structured_content["applied"] is False
    assert res.structured_content["tier"] == "medium"
    assert "the task owner" in res.structured_content["pending_approval"]
