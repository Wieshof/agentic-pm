"""Read-only Gitea / Forgejo issues, native dependencies and issue webhooks."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any

import httpx

from agentic_pm.adapters.base import (
    AuditMeta,
    Comment,
    Edge,
    EventHandler,
    ReadOnlyAdapterError,
    Task,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TaskStatus,
    TrackerEvent,
    TrackerEventKind,
    Unsubscribe,
)
from agentic_pm.adapters.catalog import load_catalog
from agentic_pm.ingress import Decision, WebhookGate


class GiteaError(RuntimeError):
    pass


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Verify the hex HMAC in X-Gitea-Signature or X-Forgejo-Signature."""
    if not signature_header or not signature_header.isascii():
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


class GiteaAdapter:
    name = "gitea"
    capabilities = load_catalog()["gitea"].capabilities(writes=False)

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        gate: WebhookGate | None = None,
    ) -> None:
        headers = {"Accept": "application/json", "User-Agent": "agentic-pm"}
        if token:
            headers["Authorization"] = f"token {token}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/api/v1/",
            headers=headers,
            timeout=30.0,
            transport=transport,
        )
        self.gate = gate or WebhookGate()
        self._handlers: list[EventHandler] = []
        self.last_decision: Decision | None = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise GiteaError(f"Gitea request failed: {exc}") from exc
        if response.status_code == 404:
            raise TaskNotFoundError(path)
        if response.status_code >= 400:
            raise GiteaError(f"Gitea {response.status_code} for {path}")
        return response

    async def _all(self, path: str, **params: Any) -> list[Any]:
        items: list[Any] = []
        page = 1
        while True:
            response = await self._get(path, {**params, "page": page, "limit": 50})
            batch = response.json()
            items.extend(batch)
            if "next" not in response.links:
                return items
            page += 1

    def _ref(self, project: str, number: int | str) -> TaskRef:
        return TaskRef(tracker=self.name, project=project, id=str(number))

    def _task(self, project: str, issue: dict[str, Any], comments: list[Any]) -> Task:
        labels = [label["name"] for label in issue.get("labels") or []]
        status = TaskStatus.DONE if issue["state"] == "closed" else TaskStatus.OPEN
        if status is TaskStatus.OPEN:
            statuses = {
                "status:blocked": TaskStatus.BLOCKED,
                "status:in-review": TaskStatus.IN_REVIEW,
                "status:in-progress": TaskStatus.IN_PROGRESS,
            }
            status = next(
                (statuses[label.lower()] for label in labels if label.lower() in statuses), status
            )
        due = issue.get("due_date")
        updated = issue.get("updated_at")
        return Task(
            ref=self._ref(project, issue["number"]),
            title=issue["title"],
            status=status,
            assignees=[user["login"] for user in issue.get("assignees") or []],
            due=datetime.fromisoformat(due.replace("Z", "+00:00")).date() if due else None,
            labels=labels,
            client_facing=any(label.lower() == "client-facing" for label in labels),
            url=issue.get("html_url"),
            description=issue.get("body") or None,
            updated_at=datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else None,
            comments=[
                Comment(
                    author=(comment.get("user") or {}).get("login", "ghost"),
                    body=comment.get("body") or "",
                    created_at=datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00")),
                )
                for comment in comments
            ],
        )

    async def get_task(self, ref: TaskRef) -> Task:
        path = f"repos/{ref.project}/issues/{ref.id}"
        issue = (await self._get(path)).json()
        comments = await self._all(f"{path}/comments") if issue.get("comments") else []
        return self._task(ref.project, issue, comments)

    async def list_tasks(self, project: str, *, include_closed: bool = False) -> list[Task]:
        issues = await self._all(
            f"repos/{project}/issues", state="all" if include_closed else "open", type="issues"
        )
        return [self._task(project, issue, []) for issue in issues if not issue.get("pull_request")]

    async def list_dependencies(self, ref: TaskRef) -> list[Edge]:
        path = f"repos/{ref.project}/issues/{ref.id}"
        edges = []
        for relation in ("dependencies", "blocks"):
            for issue in await self._all(f"{path}/{relation}"):
                project = (issue.get("repository") or {}).get("full_name", ref.project)
                other = self._ref(project, issue["number"])
                edges.append(
                    Edge(source=other, target=ref)
                    if relation == "dependencies"
                    else Edge(source=ref, target=other)
                )
        return edges

    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None:
        raise ReadOnlyAdapterError("Gitea adapter is read-only")

    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task:
        raise ReadOnlyAdapterError("Gitea adapter is read-only")

    def subscribe(self, handler: EventHandler) -> Unsubscribe:
        self._handlers.append(handler)
        return lambda: self._handlers.remove(handler)

    async def handle_webhook(
        self,
        event: str,
        payload: dict[str, Any],
        delivery_id: str | None = None,
    ) -> TrackerEvent | None:
        """Handle a verified delivery; callers must verify its HMAC before dispatch."""
        issue = payload.get("issue")
        project = (payload.get("repository") or {}).get("full_name")
        if not issue or not project or issue.get("pull_request"):
            return None
        action = payload.get("action", "")
        if event == "issues":
            kind = {"opened": TrackerEventKind.CREATED, "deleted": TrackerEventKind.DELETED}.get(
                action, TrackerEventKind.UPDATED
            )
            changed = sorted((payload.get("changes") or {}).keys()) or [action]
        elif event == "issue_comment":
            kind, changed = TrackerEventKind.COMMENTED, ["comments"]
        else:
            return None
        ref = self._ref(project, issue["number"])
        actor = (payload.get("sender") or {}).get("login")
        self.last_decision = self.gate.admit(
            ticket=str(ref),
            kind=kind,
            delivery_id=delivery_id,
            actor=actor,
            text=(payload.get("comment") or {}).get("body") if event == "issue_comment" else None,
        )
        if not self.last_decision.admitted:
            return None
        result = TrackerEvent(
            kind=kind, ref=ref, changed_fields=changed, at=datetime.now(UTC), actor=actor
        )
        for handler in list(self._handlers):
            await handler(result)
        return result

    async def aclose(self) -> None:
        await self._client.aclose()
