"""OpenProject adapter (read-only, Phase 1), API v3 (HAL+JSON).

| Task field      | Source                                                       |
|-----------------|--------------------------------------------------------------|
| status          | embedded `status.isClosed`, else status name heuristics      |
| assignees       | `_links.assignee.title` (display name)                       |
| due             | `dueDate`                                                    |
| estimate_hours  | `estimatedTime` (ISO-8601 duration, e.g. `PT4H`, `P1DT2H`)   |
| client_facing   | not mapped yet (planned: a custom field)                     |
| dependencies    | relations (blocks / blocked / precedes / follows / relates), |
|                 | parent / children links                                      |

Authentication: API key as HTTP basic auth with user `apikey`.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

import httpx

from agentic_pm.adapters.base import (
    AuditMeta,
    Edge,
    EdgeKind,
    EventHandler,
    ReadOnlyAdapterError,
    Task,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TaskStatus,
    Unsubscribe,
)

_WP_ID = re.compile(r"/work_packages/(\d+)$")
_DURATION = re.compile(r"^P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?)?$")


class OpenProjectError(RuntimeError):
    pass


def parse_duration_hours(value: str | None) -> float | None:
    """`PT4H` -> 4.0, `P1DT2H` -> 26.0 (OpenProject days are 24h in the API)."""
    if not value:
        return None
    m = _DURATION.match(value)
    if not m:
        return None
    days, hours, minutes = (float(g) if g else 0.0 for g in m.groups())
    return days * 24 + hours + minutes / 60


def _status_from(wp: dict[str, Any]) -> TaskStatus:
    embedded = (wp.get("_embedded") or {}).get("status") or {}
    name = (embedded.get("name") or wp["_links"].get("status", {}).get("title") or "").lower()
    if embedded.get("isClosed") is True:
        return TaskStatus.CLOSED if "reject" in name else TaskStatus.DONE
    if any(w in name for w in ("closed", "rejected", "done", "resolved")):
        return TaskStatus.DONE
    if any(w in name for w in ("hold", "blocked")):
        return TaskStatus.BLOCKED
    if any(w in name for w in ("test", "review")):
        return TaskStatus.IN_REVIEW
    if any(w in name for w in ("progress", "develop")):
        return TaskStatus.IN_PROGRESS
    return TaskStatus.OPEN


def _wp_id(href: str | None) -> str | None:
    m = _WP_ID.search(href or "")
    return m.group(1) if m else None


class OpenProjectAdapter:
    name = "openproject"

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        auth = httpx.BasicAuth("apikey", api_key) if api_key else None
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/api/v3",
            auth=auth,
            headers={"Accept": "application/hal+json"},
            timeout=30.0,
            transport=transport,
        )
        self._handlers: list[EventHandler] = []

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = await self._client.get(url, params=params)
        except httpx.HTTPError as e:
            raise OpenProjectError(f"OpenProject request failed: {e}") from e
        if resp.status_code == 404:
            raise TaskNotFoundError(url)
        if resp.status_code >= 400:
            raise OpenProjectError(f"OpenProject {resp.status_code} for {url}: {resp.text[:200]}")
        data: dict[str, Any] = resp.json()
        return data

    def _to_task(self, project: str, wp: dict[str, Any]) -> Task:
        links = wp.get("_links") or {}
        assignee = (links.get("assignee") or {}).get("title")
        due = date.fromisoformat(wp["dueDate"]) if wp.get("dueDate") else None
        return Task(
            ref=TaskRef(tracker=self.name, project=project, id=str(wp["id"])),
            title=wp["subject"],
            status=_status_from(wp),
            assignees=[assignee] if assignee else [],
            due=due,
            estimate_hours=parse_duration_hours(wp.get("estimatedTime")),
            url=f"{self.base_url}/work_packages/{wp['id']}",
        )

    async def get_task(self, ref: TaskRef) -> Task:
        return self._to_task(ref.project, await self._get(f"/work_packages/{ref.id}"))

    async def list_tasks(self, project: str, *, include_closed: bool = False) -> list[Task]:
        filters = [] if include_closed else [{"status": {"operator": "o", "values": []}}]
        tasks: list[Task] = []
        offset = 1
        while True:
            page = await self._get(
                f"/projects/{project}/work_packages",
                {"filters": json.dumps(filters), "pageSize": 100, "offset": offset},
            )
            elements = (page.get("_embedded") or {}).get("elements") or []
            tasks += [self._to_task(project, wp) for wp in elements]
            if not elements or len(tasks) >= int(page.get("total", 0)):
                return tasks
            offset += 1

    async def list_dependencies(self, ref: TaskRef) -> list[Edge]:
        def r(i: str) -> TaskRef:
            return TaskRef(tracker=self.name, project=ref.project, id=i)

        wp = await self._get(f"/work_packages/{ref.id}")
        links = wp.get("_links") or {}
        edges: list[Edge] = []
        if parent := _wp_id((links.get("parent") or {}).get("href")):
            edges.append(Edge(source=r(parent), target=ref, kind=EdgeKind.PARENT_OF))
        for child in links.get("children") or []:
            if cid := _wp_id(child.get("href")):
                edges.append(Edge(source=ref, target=r(cid), kind=EdgeKind.PARENT_OF))

        relations = await self._get(f"/work_packages/{ref.id}/relations")
        for rel in (relations.get("_embedded") or {}).get("elements") or []:
            rl = rel.get("_links") or {}
            frm = _wp_id((rl.get("from") or {}).get("href"))
            to = _wp_id((rl.get("to") or {}).get("href"))
            if not frm or not to:
                continue
            kind = rel.get("type")
            if kind in ("blocks", "precedes"):  # from must finish before to
                edges.append(Edge(source=r(frm), target=r(to)))
            elif kind in ("blocked", "follows"):  # to must finish before from
                edges.append(Edge(source=r(to), target=r(frm)))
            elif kind == "relates":
                edges.append(Edge(source=r(frm), target=r(to), kind=EdgeKind.RELATES))
        unique: dict[tuple[str, str, str], Edge] = {}
        for e in edges:
            unique.setdefault((str(e.source), str(e.target), e.kind), e)
        return list(unique.values())

    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None:
        raise ReadOnlyAdapterError("OpenProject adapter is read-only in Phase 1")

    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task:
        raise ReadOnlyAdapterError("OpenProject adapter is read-only in Phase 1")

    def subscribe(self, handler: EventHandler) -> Unsubscribe:
        self._handlers.append(handler)
        return lambda: self._handlers.remove(handler)

    async def aclose(self) -> None:
        await self._client.aclose()
