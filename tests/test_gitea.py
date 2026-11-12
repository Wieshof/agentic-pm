"""Offline Gitea/Forgejo contract and API mapping tests.

The fixture is a reduced, anonymized response captured from the public
codeberg.org/api/v1/repos/forgejo/forgejo/issues endpoint on 2026-11-13.
"""

import hashlib
import hmac
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from agentic_pm.adapters.base import TaskRef, TaskStatus, TrackerAdapter, TrackerEventKind
from agentic_pm.adapters.gitea import GiteaAdapter, GiteaError, verify_signature
from agentic_pm.adapters.registry import AdapterConfigError, build_adapter
from agentic_pm.config.team import Project
from agentic_pm.ingress import WebhookGate
from agentic_pm.testing import AdapterContract

ISSUE = json.loads(
    (Path(__file__).parent / "fixtures/gitea_issue.json").read_text(encoding="utf-8")
)
BASE = "/api/v1/repos/acme/app/issues"


def make_adapter(routes: dict[str, Any], seen: list[httpx.Request] | None = None) -> GiteaAdapter:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        key = request.url.path
        if request.url.params.get("page", "1") != "1":
            key += "?page=" + request.url.params["page"]
        value = routes.get(key)
        if value is None:
            return httpx.Response(404)
        if isinstance(value, httpx.Response):
            return value
        return httpx.Response(200, json=value)

    return GiteaAdapter("https://forge.test", "test-token", transport=httpx.MockTransport(handle))


class TestGiteaContract(AdapterContract):
    project, existing_id, missing_id = "acme/app", "1", "999"

    async def make(self) -> TrackerAdapter:
        return make_adapter(
            {
                BASE: [ISSUE],
                f"{BASE}/1": ISSUE,
                f"{BASE}/1/dependencies": [],
                f"{BASE}/1/blocks": [],
            }
        )


async def test_native_fields_and_comments() -> None:
    issue = {
        **ISSUE,
        "comments": 1,
        "labels": [{"name": "status:in-review"}, {"name": "client-facing"}],
        "assignees": [{"login": "sam"}, {"login": "kim"}],
        "body": "Estimate: 9h",
    }
    seen: list[httpx.Request] = []
    adapter = make_adapter(
        {
            f"{BASE}/1": issue,
            f"{BASE}/1/comments": [
                {"user": {"login": "lee"}, "body": "Reviewed", "created_at": "2026-11-13T09:30:00Z"}
            ],
        },
        seen,
    )
    task = await adapter.get_task(TaskRef(tracker="gitea", project="acme/app", id="1"))
    assert task.status is TaskStatus.IN_REVIEW
    assert task.assignees == ["sam", "kim"]
    assert task.due == date(2026, 12, 1)
    assert task.estimate_hours is None
    assert task.client_facing
    assert task.updated_at is not None
    assert task.comments[0].author == "lee"
    assert task.comments[0].body == "Reviewed"
    assert all(request.method == "GET" for request in seen)
    assert all(request.headers["Authorization"] == "token test-token" for request in seen)
    await adapter.aclose()


@pytest.mark.parametrize(
    "label,status",
    [
        ("status:blocked", TaskStatus.BLOCKED),
        ("status:in-progress", TaskStatus.IN_PROGRESS),
        ("unrecognized", TaskStatus.OPEN),
    ],
)
async def test_open_status_labels(label: str, status: TaskStatus) -> None:
    adapter = make_adapter({f"{BASE}/1": {**ISSUE, "labels": [{"name": label}]}})
    assert (
        await adapter.get_task(TaskRef(tracker="gitea", project="acme/app", id="1"))
    ).status is status
    await adapter.aclose()


async def test_pagination_and_closed_tasks_exclude_pull_requests() -> None:
    seen: list[httpx.Request] = []
    adapter = make_adapter(
        {
            BASE: httpx.Response(
                200,
                json=[ISSUE],
                headers={
                    "Link": '<https://forge.test/api/v1/repos/acme/app/issues?page=2>; rel="next"'
                },
            ),
            BASE + "?page=2": [
                {**ISSUE, "number": 2, "state": "closed"},
                {**ISSUE, "number": 3, "pull_request": {"merged": False}},
            ],
        },
        seen,
    )
    tasks = await adapter.list_tasks("acme/app", include_closed=True)
    assert [task.ref.id for task in tasks] == ["1", "2"]
    assert tasks[1].status is TaskStatus.DONE
    assert [request.url.params["page"] for request in seen] == ["1", "2"]
    assert all(request.url.params["state"] == "all" for request in seen)
    assert all(request.url.params["type"] == "issues" for request in seen)
    await adapter.aclose()


async def test_native_dependency_directions_and_cross_repository() -> None:
    adapter = make_adapter(
        {
            f"{BASE}/1/dependencies": [{**ISSUE, "number": 2}],
            f"{BASE}/1/blocks": [{**ISSUE, "number": 3, "repository": {"full_name": "other/repo"}}],
        }
    )
    ref = TaskRef(tracker="gitea", project="acme/app", id="1")
    edges = await adapter.list_dependencies(ref)
    assert [(str(edge.source), str(edge.target)) for edge in edges] == [
        ("gitea:acme/app#2", str(ref)),
        (str(ref), "gitea:other/repo#3"),
    ]
    await adapter.aclose()


@pytest.mark.parametrize("status", [401, 403, 500])
async def test_http_errors(status: int) -> None:
    adapter = make_adapter({BASE: httpx.Response(status)})
    with pytest.raises(GiteaError, match=str(status)):
        await adapter.list_tasks("acme/app")
    await adapter.aclose()


async def test_webhook_delivery_gate_and_unsubscribe() -> None:
    adapter = make_adapter({})
    adapter.gate = WebhookGate(agent_accounts=["agent-bot"])
    events = []

    async def on_event(event: Any) -> None:
        events.append(event)

    unsubscribe = adapter.subscribe(on_event)
    payload = {
        "action": "created",
        "issue": ISSUE,
        "repository": {"full_name": "acme/app"},
        "sender": {"login": "sam"},
        "comment": {"body": "hello"},
    }
    result = await adapter.handle_webhook("issue_comment", payload, "delivery-1")
    assert result is not None and result.kind is TrackerEventKind.COMMENTED
    assert str(result.ref) == "gitea:acme/app#1"
    assert len(events) == 1
    assert await adapter.handle_webhook("issue_comment", payload, "delivery-1") is None
    assert (
        await adapter.handle_webhook("issues", {**payload, "sender": {"login": "agent-bot"}}, "2")
        is None
    )
    unsubscribe()
    assert await adapter.handle_webhook("push", payload, "3") is None
    assert await adapter.handle_webhook("issues", {**payload, "action": "opened"}, "4") is not None
    assert len(events) == 1
    await adapter.aclose()


def test_signature() -> None:
    body = b'{"action":"opened"}'
    signature = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature("secret", body, signature)
    assert not verify_signature("secret", body + b" ", signature)
    assert not verify_signature("secret", body, None)
    assert not verify_signature("secret", body, "invalid")
    assert not verify_signature("secret", body, "\u00e9")


async def test_registry_requires_server_and_uses_environment_token() -> None:
    with pytest.raises(AdapterConfigError, match="base_url"):
        build_adapter(Project(tracker="gitea", repo="acme/app", leads=["sam"]), {})
    adapter = build_adapter(
        Project(tracker="gitea", repo="acme/app", leads=["sam"], base_url="https://forge.test"),
        {"AGENT_PM_GITEA_TOKEN": "test-token"},
    )
    assert isinstance(adapter, GiteaAdapter)
    assert adapter._client.headers["Authorization"] == "token test-token"
    assert str(adapter._client.base_url) == "https://forge.test/api/v1/"
    await adapter.aclose()
