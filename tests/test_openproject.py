import json
from datetime import date
from typing import Any

import httpx
import pytest

from agentic_pm.adapters import TaskRef, TaskStatus, TrackerAdapter
from agentic_pm.adapters.base import EdgeKind
from agentic_pm.adapters.openproject import OpenProjectAdapter, parse_duration_hours

BASE = "https://op.test"


def wp(i: int, status: str = "New", closed: bool = False, **kw: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": i,
        "subject": f"WP {i}",
        "dueDate": "2026-12-01",
        "estimatedTime": "PT6H",
        "_links": {
            "status": {"title": status},
            "assignee": {"href": "/api/v3/users/5", "title": "Kim Doe"},
        },
        "_embedded": {"status": {"name": status, "isClosed": closed}},
    }
    data.update(kw)
    return data


def make(routes: dict[str, Any], seen: list[httpx.Request] | None = None) -> OpenProjectAdapter:
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        key = req.url.path
        if "offset" in req.url.params:
            key += f"@{req.url.params['offset']}"
        if key not in routes:
            return httpx.Response(404, json={"message": "nope"})
        return httpx.Response(200, json=routes[key])

    return OpenProjectAdapter(BASE, api_key="k", transport=httpx.MockTransport(handler))


def r(i: int) -> TaskRef:
    return TaskRef(tracker="openproject", project="app", id=str(i))


@pytest.mark.parametrize(
    ("value", "hours"),
    [("PT4H", 4), ("P1DT2H", 26), ("PT30M", 0.5), ("P2D", 48), (None, None), ("junk", None)],
)
def test_parse_duration(value: str | None, hours: float | None) -> None:
    assert parse_duration_hours(value) == hours


def test_protocol() -> None:
    assert isinstance(make({}), TrackerAdapter)


async def test_get_task_and_auth() -> None:
    seen: list[httpx.Request] = []
    a = make({"/api/v3/work_packages/3": wp(3, "In progress")}, seen)
    t = await a.get_task(r(3))
    assert t.status is TaskStatus.IN_PROGRESS
    assert t.assignees == ["Kim Doe"]
    assert t.due == date(2026, 12, 1)
    assert t.estimate_hours == 6
    assert t.url == f"{BASE}/work_packages/3"
    assert seen[0].headers["authorization"].startswith("Basic ")


@pytest.mark.parametrize(
    ("status", "closed", "expected"),
    [
        ("Closed", True, TaskStatus.DONE),
        ("Rejected", True, TaskStatus.CLOSED),
        ("On hold", False, TaskStatus.BLOCKED),
        ("In testing", False, TaskStatus.IN_REVIEW),
        ("New", False, TaskStatus.OPEN),
    ],
)
async def test_status_mapping(status: str, closed: bool, expected: TaskStatus) -> None:
    a = make({"/api/v3/work_packages/1": wp(1, status, closed)})
    assert (await a.get_task(r(1))).status is expected


async def test_list_tasks_pages_and_filters() -> None:
    seen: list[httpx.Request] = []
    path = "/api/v3/projects/app/work_packages"
    a = make(
        {
            f"{path}@1": {"total": 3, "_embedded": {"elements": [wp(1), wp(2)]}},
            f"{path}@2": {"total": 3, "_embedded": {"elements": [wp(3)]}},
        },
        seen,
    )
    tasks = await a.list_tasks("app")
    assert [t.ref.id for t in tasks] == ["1", "2", "3"]
    assert json.loads(seen[0].url.params["filters"]) == [
        {"status": {"operator": "o", "values": []}}
    ]


async def test_relations_and_hierarchy() -> None:
    def rel(kind: str, frm: int, to: int) -> dict[str, Any]:
        return {
            "type": kind,
            "_links": {
                "from": {"href": f"/api/v3/work_packages/{frm}"},
                "to": {"href": f"/api/v3/work_packages/{to}"},
            },
        }

    me = wp(5)
    me["_links"]["parent"] = {"href": "/api/v3/work_packages/1"}
    me["_links"]["children"] = [{"href": "/api/v3/work_packages/9"}]
    a = make(
        {
            "/api/v3/work_packages/5": me,
            "/api/v3/work_packages/5/relations": {
                "_embedded": {
                    "elements": [
                        rel("follows", 5, 2),  # 2 must finish before 5
                        rel("blocks", 5, 6),
                        rel("blocked", 5, 3),  # 3 blocks 5
                        rel("precedes", 5, 7),
                        rel("relates", 5, 8),
                    ]
                }
            },
        }
    )
    pairs = {(e.source.id, e.target.id, e.kind) for e in await a.list_dependencies(r(5))}
    assert pairs == {
        ("1", "5", EdgeKind.PARENT_OF),
        ("5", "9", EdgeKind.PARENT_OF),
        ("2", "5", EdgeKind.BLOCKS),
        ("5", "6", EdgeKind.BLOCKS),
        ("3", "5", EdgeKind.BLOCKS),
        ("5", "7", EdgeKind.BLOCKS),
        ("5", "8", EdgeKind.RELATES),
    }
