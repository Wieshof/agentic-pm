from typing import Any

import pytest

from agentic_pm.adapters import AuditMeta, Channel
from agentic_pm.adapters.github import GitHubAdapter
from agentic_pm.audit import render_audit_footer
from agentic_pm.ingress import WebhookGate


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock() -> Clock:
    return Clock()


def test_duplicate_delivery_is_dropped(clock: Clock) -> None:
    g = WebhookGate(coalesce_window=0, clock=clock)
    assert g.admit(ticket="t#1", kind="updated", delivery_id="d1").admitted
    assert g.admit(ticket="t#1", kind="updated", delivery_id="d1").reason == "duplicate_delivery"
    clock.t = 4000  # after dedup_ttl the id is forgotten
    assert g.admit(ticket="t#1", kind="updated", delivery_id="d1").admitted


def test_self_authored_by_account_or_footer(clock: Clock) -> None:
    g = WebhookGate(agent_accounts=["Agent-PM-Bot"], clock=clock)
    assert g.admit(ticket="t#1", kind="commented", actor="agent-pm-bot").reason == "self_authored"
    footer = render_audit_footer(AuditMeta(actor="agent", channel=Channel.VOICE, reason="how-to"))
    d = g.admit(ticket="t#2", kind="commented", actor="sam", text=f"### How\n{footer}")
    assert d.reason == "self_authored"
    assert g.admit(ticket="t#3", kind="commented", actor="sam", text="thanks!").admitted


def test_bursts_are_coalesced_per_ticket_and_kind(clock: Clock) -> None:
    g = WebhookGate(coalesce_window=10, clock=clock)
    assert g.admit(ticket="t#1", kind="updated").admitted
    clock.t = 3
    assert g.admit(ticket="t#1", kind="updated").reason == "coalesced"
    assert g.admit(ticket="t#1", kind="commented").admitted  # other kind
    assert g.admit(ticket="t#2", kind="updated").admitted  # other ticket
    clock.t = 11
    assert g.admit(ticket="t#1", kind="updated").admitted  # window over


def test_memory_is_bounded(clock: Clock) -> None:
    g = WebhookGate(max_entries=100, coalesce_window=0, clock=clock)
    for i in range(1000):
        g.admit(ticket=f"t#{i}", kind="updated", delivery_id=f"d{i}")
    assert len(g._deliveries) <= 100


async def test_github_webhook_uses_gate(clock: Clock) -> None:
    a = GitHubAdapter(token=None, gate=WebhookGate(agent_accounts=["agent-pm-bot"], clock=clock))
    got: list[Any] = []

    async def h(e: Any) -> None:
        got.append(e)

    a.subscribe(h)
    repo = {"full_name": "acme/app"}
    issue = {"number": 4}
    comment = {"action": "created", "issue": issue, "repository": repo}

    own = {**comment, "sender": {"login": "agent-pm-bot"}, "comment": {"body": "done"}}
    assert await a.handle_webhook("issue_comment", own, "d1") is None
    assert a.last_decision is not None and a.last_decision.reason == "self_authored"

    human = {**comment, "sender": {"login": "sam"}, "comment": {"body": "fixed it"}}
    evt = await a.handle_webhook("issue_comment", human, "d2")
    assert evt is not None and evt.actor == "sam"
    assert await a.handle_webhook("issue_comment", human, "d2") is None  # retry of same delivery
    assert len(got) == 1
