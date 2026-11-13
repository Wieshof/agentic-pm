import hashlib
import hmac
import json
from datetime import date
from typing import Any

import httpx
import pytest

from agentic_pm.adapters import AuditMeta, Channel, TaskRef, TaskStatus, TrackerAdapter
from agentic_pm.adapters._text import parse_due, parse_estimate, parse_issue_links
from agentic_pm.adapters.base import EdgeKind, ReadOnlyAdapterError, TaskNotFoundError, TaskPatch
from agentic_pm.adapters.github import GitHubAdapter, verify_signature

REPO = "acme/app"


def issue(n: int, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "number": n,
        "title": f"Issue {n}",
        "state": "open",
        "state_reason": None,
        "labels": [],
        "assignees": [{"login": "sam"}],
        "body": "",
        "milestone": None,
        "comments": 0,
        "html_url": f"https://github.com/{REPO}/issues/{n}",
        "repository_url": f"https://api.github.com/repos/{REPO}",
        "issue_dependencies_summary": {"total_blocked_by": 0, "total_blocking": 0},
        "sub_issues_summary": {"total": 0},
    }
    base.update(kw)
    return base


def adapter(routes: dict[str, Any], seen: list[str] | None = None) -> GitHubAdapter:
    def handler(req: httpx.Request) -> httpx.Response:
        key = req.url.path + (f"?page={req.url.params['page']}" if "page" in req.url.params else "")
        if seen is not None:
            seen.append(str(req.url))
        if key not in routes:
            return httpx.Response(404, json={"message": "Not Found"})
        value = routes[key]
        if isinstance(value, tuple):
            body, headers = value
            return httpx.Response(200, json=body, headers=headers)
        return httpx.Response(200, json=value)

    return GitHubAdapter(
        token="t", api_url="https://gh.test", transport=httpx.MockTransport(handler)
    )


def ref(n: int, project: str = REPO) -> TaskRef:
    return TaskRef(tracker="github", project=project, id=str(n))


def test_text_parsers() -> None:
    body = "Intro\nDue: 2026-12-01\nEstimate: 2d\nBlocked by #3, #4\nBlocks: #9\n"
    assert parse_due(body) == date(2026, 12, 1)
    assert parse_due("Due: 2026-13-45") is None
    assert parse_estimate(body) == 16
    assert parse_estimate("", ["estimate:3h"]) == 3
    assert parse_issue_links(body) == (["3", "4"], ["9"])


def test_satisfies_protocol() -> None:
    assert isinstance(adapter({}), TrackerAdapter)


async def test_get_task_maps_fields() -> None:
    a = adapter(
        {
            f"/repos/{REPO}/issues/5": issue(
                5,
                labels=[{"name": "status:in-progress"}, {"name": "client-facing"}],
                body="Estimate: 4h",
                milestone={"due_on": "2026-12-24T08:00:00Z"},
                comments=1,
            ),
            f"/repos/{REPO}/issues/5/comments": [
                {"user": {"login": "kim"}, "body": "hi", "created_at": "2026-11-01T10:00:00Z"}
            ],
        }
    )
    t = await a.get_task(ref(5))
    assert t.status is TaskStatus.IN_PROGRESS
    assert t.due == date(2026, 12, 24)  # from milestone
    assert t.estimate_hours == 4
    assert t.client_facing
    assert t.comments[0].author == "kim"


@pytest.mark.parametrize(
    ("state", "reason", "expected"),
    [("closed", "completed", TaskStatus.DONE), ("closed", "not_planned", TaskStatus.CLOSED)],
)
async def test_closed_states(state: str, reason: str, expected: TaskStatus) -> None:
    a = adapter({f"/repos/{REPO}/issues/1": issue(1, state=state, state_reason=reason)})
    assert (await a.get_task(ref(1))).status is expected


async def test_not_found() -> None:
    with pytest.raises(TaskNotFoundError):
        await adapter({}).get_task(ref(99))


async def test_list_tasks_paginates_and_skips_prs() -> None:
    page2 = f"https://gh.test/repos/{REPO}/issues?state=open&per_page=100&page=2"
    a = adapter(
        {
            f"/repos/{REPO}/issues": (
                [issue(1), issue(2, pull_request={})],
                {"link": f'<{page2}>; rel="next"'},
            ),
            f"/repos/{REPO}/issues?page=2": [issue(3)],
        }
    )
    tasks = await a.list_tasks(REPO)
    assert [t.ref.id for t in tasks] == ["1", "3"]


async def test_dependencies_native_sub_issues_and_body() -> None:
    other = issue(7, repository_url="https://api.github.com/repos/acme/lib")
    a = adapter(
        {
            f"/repos/{REPO}/issues/5": issue(
                5,
                body="Blocked by #2\nBlocks #8",
                issue_dependencies_summary={"total_blocked_by": 1, "total_blocking": 0},
                sub_issues_summary={"total": 1},
            ),
            f"/repos/{REPO}/issues/5/dependencies/blocked_by": [
                other,
            ],
            f"/repos/{REPO}/issues/5/sub_issues": [issue(6)],
        }
    )
    edges = await a.list_dependencies(ref(5))
    pairs = {(str(e.source), str(e.target), e.kind) for e in edges}
    assert ("github:acme/lib#7", f"github:{REPO}#5", EdgeKind.BLOCKS) in pairs  # cross-repo
    assert (f"github:{REPO}#2", f"github:{REPO}#5", EdgeKind.BLOCKS) in pairs
    assert (f"github:{REPO}#5", f"github:{REPO}#8", EdgeKind.BLOCKS) in pairs
    assert (f"github:{REPO}#5", f"github:{REPO}#6", EdgeKind.PARENT_OF) in pairs
    assert len(edges) == 4


async def test_skips_dependency_calls_when_summary_is_zero() -> None:
    seen: list[str] = []
    a = adapter({f"/repos/{REPO}/issues/5": issue(5)}, seen)
    assert await a.list_dependencies(ref(5)) == []
    assert len(seen) == 1


async def test_writes_are_blocked() -> None:
    meta = AuditMeta(actor="agent", channel=Channel.SYSTEM, reason="x")
    with pytest.raises(ReadOnlyAdapterError):
        await adapter({}).add_comment(ref(1), "hi", meta)


def test_verify_signature() -> None:
    body = json.dumps({"a": 1}).encode()
    sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_signature("s3cret", body, sig)
    assert not verify_signature("wrong", body, sig)
    assert not verify_signature("s3cret", body, None)


async def test_webhook_events() -> None:
    a = adapter({})
    got = []

    async def h(e: Any) -> None:
        got.append(e)

    a.subscribe(h)
    repo = {"full_name": REPO}
    e1 = await a.handle_webhook(
        "issues",
        {"action": "edited", "issue": issue(4), "repository": repo, "changes": {"body": {}}},
    )
    e2 = await a.handle_webhook(
        "issue_comment", {"action": "created", "issue": issue(4), "repository": repo}
    )
    e3 = await a.handle_webhook(
        "issues", {"action": "opened", "issue": issue(4, pull_request={}), "repository": repo}
    )
    assert e1 is not None and e1.changed_fields == ["body"]
    assert e2 is not None and e2.kind == "commented"
    assert e3 is None
    assert len(got) == 2


def writer(issue_data: dict[str, Any], sent: list[tuple[str, str, Any]]) -> GitHubAdapter:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            return httpx.Response(200, json=issue_data)
        payload = json.loads(req.content)
        sent.append((req.method, req.url.path, payload))
        if req.method == "PATCH":
            issue_data.update({k: v for k, v in payload.items() if k != "labels"})
            if "labels" in payload:
                issue_data["labels"] = [{"name": n} for n in payload["labels"]]
        return httpx.Response(200, json={})

    return GitHubAdapter(
        token="t",
        api_url="https://gh.test",
        transport=httpx.MockTransport(handler),
        allow_writes=True,
    )


async def test_writes_need_opt_in() -> None:
    a = adapter({f"/repos/{REPO}/issues/1": issue(1)})
    assert not a.capabilities.writes
    with pytest.raises(ReadOnlyAdapterError, match="allow_writes"):
        await a.update_fields(
            ref(1),
            TaskPatch(add_labels=["x"]),
            AuditMeta(actor="a", channel=Channel.SYSTEM, reason="r"),
        )


async def test_comment_carries_audit_footer() -> None:
    sent: list[tuple[str, str, Any]] = []
    a = writer(issue(1), sent)
    await a.add_comment(
        ref(1),
        "### How it was solved",
        AuditMeta(actor="sam", channel=Channel.EMAIL, reason="how-to"),
    )
    method, path, payload = sent[0]
    assert (method, path) == ("POST", f"/repos/{REPO}/issues/1/comments")
    assert "agent-pm-audit" in payload["body"]


async def test_update_fields_patch_and_comment() -> None:
    sent: list[tuple[str, str, Any]] = []
    data = issue(
        1,
        body="Context\nDue: 2026-12-01\n",
        labels=[{"name": "status:in-progress"}, {"name": "bug"}],
    )
    a = writer(data, sent)
    meta = AuditMeta(actor="agent", channel=Channel.SYSTEM, reason="slip detected")
    t = await a.update_fields(
        ref(1),
        TaskPatch(
            due=date(2026, 12, 3), estimate_hours=16, status=TaskStatus.BLOCKED, add_labels=["risk"]
        ),
        meta,
    )
    patch = next(p for m, _, p in sent if m == "PATCH")
    assert "Due: 2026-12-03" in patch["body"] and "Estimate: 2d" in patch["body"]
    assert patch["state"] == "open"
    assert set(patch["labels"]) == {"bug", "status:blocked", "risk"}
    comment = next(p for m, path, p in sent if m == "POST")
    assert "due 2026-12-01 → 2026-12-03" in comment["body"] and "slip detected" in comment["body"]
    assert t.due == date(2026, 12, 3) and t.status is TaskStatus.BLOCKED


async def test_done_closes_issue_and_noop_writes_nothing() -> None:
    sent: list[tuple[str, str, Any]] = []
    a = writer(issue(1), sent)
    meta = AuditMeta(actor="agent", channel=Channel.SYSTEM, reason="done")
    await a.update_fields(ref(1), TaskPatch(status=TaskStatus.DONE), meta)
    assert sent[0][2]["state"] == "closed" and sent[0][2]["state_reason"] == "completed"
    sent.clear()
    await a.update_fields(ref(1), TaskPatch(assignees=["sam"]), meta)  # unchanged
    assert sent == []


def test_body_field_helpers() -> None:
    from agentic_pm.adapters._text import format_hours, set_body_field

    assert set_body_field("a\nDue: 2026-01-01\nb", "Due", "2026-02-02") == "a\nDue: 2026-02-02\nb"
    assert set_body_field("a", "Due", "2026-02-02") == "a\nDue: 2026-02-02\n"
    assert set_body_field("", "Estimate", "4h") == "Estimate: 4h\n"
    assert [format_hours(h) for h in (4, 8, 12, 40, 0.5)] == ["4h", "1d", "12h", "1w", "0.5h"]
