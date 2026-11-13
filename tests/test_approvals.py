import hashlib
import hmac
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from agentic_pm.actions import Guard
from agentic_pm.adapters import AuditMeta, Channel, TaskPatch, TaskRef
from agentic_pm.approvals import ExpiredToken, InvalidToken, Signer
from agentic_pm.config import load_team_config
from agentic_pm.demo import demo_tracker
from agentic_pm.notify import RecordingNotifier
from agentic_pm.web import create_app

TODAY = date(2026, 11, 13)
EXAMPLE = Path(__file__).parents[1] / ".agent-pm" / "team.example.yaml"
META = AuditMeta(actor="agent", channel=Channel.SYSTEM, reason="Fix auth timeout slipped")


class Clock:
    t = 1_800_000_000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def env() -> Any:
    cfg = load_team_config(EXAMPLE)
    cfg = cfg.model_copy(
        update={
            "project": cfg.project.model_copy(
                update={"control_plane_url": "https://pm.example.com"}
            )
        }
    )
    tracker = demo_tracker(cfg.project.repo, TODAY)
    notifier = RecordingNotifier()
    clock = Clock()
    guard = Guard(cfg, tracker, notifier, Signer("k" * 32, clock=clock))
    return cfg, tracker, notifier, clock, guard


def ref(cfg: Any, i: int) -> TaskRef:
    return TaskRef(tracker="memory", project=cfg.project.repo, id=str(i))


def token_from(text: str) -> str:
    m = re.search(r"/approve\?t=([A-Za-z0-9_.-]+)", text)
    assert m, text
    return m.group(1)


async def test_low_risk_applies_directly(env: Any) -> None:
    cfg, _tracker, notifier, _, guard = env
    out = await guard.propose(ref(cfg, 12), TaskPatch(add_labels=["risk"]), META)
    assert out.applied and out.status == "applied"
    assert notifier.sent == []


async def test_medium_goes_to_owner_and_applies_after_ok(env: Any) -> None:
    cfg, tracker, notifier, _, guard = env
    new_due = TODAY + timedelta(days=4)
    out = await guard.propose(ref(cfg, 12), TaskPatch(due=new_due), META)
    assert out.status == "pending" and out.waiting_for == ["sam"]
    [msg] = notifier.sent
    assert msg.handle == "sam" and msg.subject.startswith("🙋 Dein OK gebraucht")  # Sam: German
    assert "Hallo Sam" in msg.text and "https://pm.example.com/approve?t=" in msg.text
    task = await tracker.get_task(ref(cfg, 12))
    assert task.due != new_due and "⏳" in task.comments[-1].body  # waiting note on the ticket

    done = await guard.decide(token_from(msg.text), approve=True)
    assert done.applied and done.task is not None and done.task.due == new_due
    assert '"approved_by": "sam"' in done.task.comments[-1].body
    again = await guard.decide(token_from(msg.text), approve=True)
    assert again.status == "stale"  # replay is harmless


async def test_high_goes_to_leads(env: Any) -> None:
    cfg, _, notifier, _, guard = env
    out = await guard.propose(ref(cfg, 13), TaskPatch(due=TODAY + timedelta(days=9)), META)
    assert out.tier == "high" and out.waiting_for == ["alex"]
    assert notifier.sent[0].subject.startswith("🙋 Your OK needed")


async def test_stale_when_task_changed(env: Any) -> None:
    cfg, tracker, notifier, _, guard = env
    await guard.propose(ref(cfg, 12), TaskPatch(due=TODAY + timedelta(days=4)), META)
    approved = AuditMeta(actor="sam", channel=Channel.WEB, reason="manual", approved_by="sam")
    await tracker.update_fields(ref(cfg, 12), TaskPatch(due=TODAY + timedelta(days=2)), approved)
    out = await guard.decide(token_from(notifier.sent[0].text), approve=True)
    assert out.status == "stale" and not out.applied


async def test_decline_is_idempotent(env: Any) -> None:
    cfg, _tracker, notifier, _, guard = env
    await guard.propose(ref(cfg, 12), TaskPatch(due=TODAY + timedelta(days=4)), META)
    token = token_from(notifier.sent[0].text)
    assert (await guard.decide(token, approve=False)).status == "declined"
    assert (await guard.decide(token, approve=False)).status == "already_declined"


async def test_tokens_expire_and_cannot_be_forged(env: Any) -> None:
    cfg, _, notifier, clock, guard = env
    await guard.propose(ref(cfg, 12), TaskPatch(due=TODAY + timedelta(days=4)), META)
    token = token_from(notifier.sent[0].text)
    body, sig = token.split(".")
    with pytest.raises(InvalidToken):
        guard.signer.verify(body + "." + sig[::-1])
    with pytest.raises(InvalidToken):
        Signer("other-key").verify(token)
    clock.t += 73 * 3600
    with pytest.raises(ExpiredToken):
        guard.signer.verify(token)


async def test_web_get_never_mutates_and_post_applies(env: Any) -> None:
    cfg, tracker, notifier, _, guard = env
    new_due = TODAY + timedelta(days=4)
    await guard.propose(ref(cfg, 12), TaskPatch(due=new_due), META)
    token = token_from(notifier.sent[0].text)
    client = TestClient(create_app(guard))
    page = client.get(f"/approve?t={token}")
    assert page.status_code == 200 and "Dein OK, bitte" in page.text and "Freigeben" in page.text
    assert page.headers["cache-control"] == "no-store"
    assert (await tracker.get_task(ref(cfg, 12))).due != new_due
    done = client.post("/approve", data={"t": token, "decision": "approve"})
    assert "Erledigt, danke Sam" in done.text
    assert (await tracker.get_task(ref(cfg, 12))).due == new_due
    assert client.get("/approve?t=nonsense").status_code == 400


def test_web_github_webhook_signature() -> None:
    cfg = load_team_config(EXAMPLE)
    tracker = demo_tracker(cfg.project.repo, TODAY)
    seen: list[tuple[str, str | None]] = []

    async def handler(event: str, payload: dict[str, Any], delivery: str | None) -> Any:
        seen.append((event, delivery))
        return object()

    guard = Guard(cfg, tracker, RecordingNotifier())
    client = TestClient(create_app(guard, webhook_secret="s3cret", on_github_webhook=handler))
    body = json.dumps({"action": "closed"}).encode()
    sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    headers = {"x-hub-signature-256": sig, "x-github-event": "issues", "x-github-delivery": "d1"}
    assert client.post("/webhooks/github", content=body, headers=headers).status_code == 202
    bad = {**headers, "x-hub-signature-256": "sha256=00"}
    assert client.post("/webhooks/github", content=body, headers=bad).status_code == 401
    assert seen == [("issues", "d1")]
