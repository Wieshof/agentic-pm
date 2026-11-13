"""Every built-in adapter runs the shared contract suite (agentic_pm.testing)."""

from pathlib import Path
from typing import Any

import httpx
import pytest

from agentic_pm.adapters import InMemoryTracker
from agentic_pm.adapters.base import TrackerAdapter
from agentic_pm.adapters.catalog import (
    MATRIX_END,
    MATRIX_START,
    load_catalog,
    render_matrix,
    replace_matrix,
)
from agentic_pm.adapters.github import GitHubAdapter
from agentic_pm.adapters.openproject import OpenProjectAdapter
from agentic_pm.adapters.registry import AdapterConfigError, build_adapter, register
from agentic_pm.config.team import Project
from agentic_pm.demo import demo_tracker
from agentic_pm.testing import AdapterContract

ROOT = Path(__file__).parents[1]


def routes_transport(routes: dict[str, Any]) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        key = req.url.path
        if "offset" in req.url.params:
            key += f"@{req.url.params['offset']}"
        if key in routes:
            return httpx.Response(200, json=routes[key])
        return httpx.Response(404, json={"message": "Not Found"})

    return httpx.MockTransport(handler)


GH_ISSUE = {
    "number": 1,
    "title": "Fix login",
    "state": "open",
    "labels": [],
    "assignees": [{"login": "sam"}],
    "body": "Due: 2026-12-01\nBlocked by #2",
    "comments": 0,
    "updated_at": "2026-11-10T09:00:00Z",
    "issue_dependencies_summary": {"total_blocked_by": 0, "total_blocking": 0},
    "sub_issues_summary": {"total": 0},
}


class TestGitHubContract(AdapterContract):
    project = "acme/app"
    existing_id = "1"
    missing_id = "999"

    async def make(self) -> TrackerAdapter:
        routes = {"/repos/acme/app/issues": [GH_ISSUE], "/repos/acme/app/issues/1": GH_ISSUE}
        return GitHubAdapter(token="t", transport=routes_transport(routes))


OP_WP = {
    "id": 1,
    "subject": "Fix login",
    "dueDate": "2026-12-01",
    "updatedAt": "2026-11-10T09:00:00Z",
    "_links": {"status": {"title": "New"}},
    "_embedded": {"status": {"name": "New", "isClosed": False}},
}


class TestOpenProjectContract(AdapterContract):
    project = "app"
    existing_id = "1"
    missing_id = "999"

    async def make(self) -> TrackerAdapter:
        routes = {
            "/api/v3/projects/app/work_packages@1": {
                "total": 1,
                "_embedded": {"elements": [OP_WP]},
            },
            "/api/v3/work_packages/1": OP_WP,
            "/api/v3/work_packages/1/relations": {"_embedded": {"elements": []}},
        }
        return OpenProjectAdapter("https://op.test", "k", transport=routes_transport(routes))


class TestInMemoryContract(AdapterContract):
    project = "demo/app"
    existing_id = "11"
    missing_id = "999"

    async def make(self) -> TrackerAdapter:
        from datetime import date

        return demo_tracker(self.project, date(2026, 11, 13))


async def test_updated_at_is_mapped() -> None:
    gh = await TestGitHubContract().make()
    t = await gh.get_task(TestGitHubContract().ref(gh, "1"))
    assert t.updated_at is not None and t.updated_at.year == 2026


def test_catalog_is_consistent() -> None:
    cat = load_catalog()
    assert {"github", "openproject", "jira", "trello", "planner"} <= set(cat)
    available = {k for k, e in cat.items() if e.status == "available"}
    assert available == {"github", "openproject", "gitea", "spreadsheet"}  # update on release
    for e in cat.values():
        assert e.notes_en and e.notes_de


@pytest.mark.parametrize(
    ("lang", "path"), [("en", "docs/trackers.md"), ("de", "docs/de/trackers.md")]
)
def test_docs_matrix_is_up_to_date(lang: str, path: str) -> None:
    doc = (ROOT / path).read_text(encoding="utf-8")
    assert MATRIX_START in doc and MATRIX_END in doc
    expected = replace_matrix(doc, render_matrix(lang, "https://github.com/Wieshof/agentic-pm"))  # type: ignore[arg-type]
    assert doc == expected, "run: uv run agent-pm trackers --write-docs"


def test_registry_planned_tracker_gives_friendly_error() -> None:
    project = Project(tracker="jira", repo="APP", leads=["a"])
    with pytest.raises(AdapterConfigError, match="planned but not built yet"):
        build_adapter(project, env={})


def test_registry_runtime_registration() -> None:
    register("memory-test", lambda project, env: InMemoryTracker())
    adapter = build_adapter(Project(tracker="memory-test", repo="x", leads=["a"]), env={})
    assert adapter.name == "memory"
