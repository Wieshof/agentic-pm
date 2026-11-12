"""GitHub Issues adapter (read-only, Phase 1).

Maps GitHub issues to the tracker-agnostic `Task` model:

| Task field      | Source                                                          |
|-----------------|-----------------------------------------------------------------|
| status          | closed -> done / closed (not planned); open + `status:*` label  |
| due             | `Due: YYYY-MM-DD` line in body, else milestone due date         |
| estimate_hours  | `Estimate: 4h/2d/1w` line in body, or `estimate:4h` label       |
| client_facing   | `client-facing` label                                           |
| dependencies    | native blocked-by / blocking, sub-issues, `Blocked by #N` lines |

Webhooks: pass deliveries to `handle_webhook()`; verify them first with
`verify_signature()`.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from agentic_pm.adapters._text import parse_due, parse_estimate, parse_issue_links
from agentic_pm.adapters.base import (
    AuditMeta,
    Comment,
    Edge,
    EdgeKind,
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

_STATUS_LABELS: dict[str, TaskStatus] = {
    "status:blocked": TaskStatus.BLOCKED,
    "blocked": TaskStatus.BLOCKED,
    "status:in-review": TaskStatus.IN_REVIEW,
    "in review": TaskStatus.IN_REVIEW,
    "status:in-progress": TaskStatus.IN_PROGRESS,
    "in progress": TaskStatus.IN_PROGRESS,
}
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
_REPO_FROM_URL = re.compile(r"/repos/([^/]+/[^/]+)$")


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


class GitHubError(RuntimeError):
    pass


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Check the `X-Hub-Signature-256` header of a webhook delivery."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


class GitHubAdapter:
    name = "github"
    capabilities = load_catalog()["github"].capabilities(writes=False)

    def __init__(
        self,
        token: str | None,
        api_url: str = "https://api.github.com",
        transport: httpx.AsyncBaseTransport | None = None,
        gate: WebhookGate | None = None,
    ) -> None:
        # Self-trigger protection + de-duplication for incoming webhooks.
        self.gate = gate or WebhookGate()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "agentic-pm",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=api_url.rstrip("/"), headers=headers, timeout=30.0, transport=transport
        )
        self._handlers: list[EventHandler] = []
        self.last_decision: Decision | None = None

    # ---------------------------------------------------------------- HTTP

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            resp = await self._client.get(url, params=params)
        except httpx.HTTPError as e:
            raise GitHubError(f"GitHub request failed: {e}") from e
        if resp.status_code == 404:
            raise TaskNotFoundError(url)
        if resp.status_code >= 400:
            raise GitHubError(f"GitHub {resp.status_code} for {url}: {resp.text[:200]}")
        return resp

    async def _get_all(self, url: str, params: dict[str, Any] | None = None) -> list[Any]:
        items: list[Any] = []
        next_url: str | None = url
        first = True
        while next_url:
            resp = await self._get(next_url, params if first else None)
            first = False
            items.extend(resp.json())
            m = _NEXT_LINK.search(resp.headers.get("link", ""))
            next_url = m.group(1) if m else None
        return items

    # ------------------------------------------------------------- mapping

    def _ref(self, project: str, number: int | str) -> TaskRef:
        return TaskRef(tracker=self.name, project=project, id=str(number))

    @staticmethod
    def _project_of(issue: dict[str, Any], default: str) -> str:
        m = _REPO_FROM_URL.search(issue.get("repository_url", ""))
        return m.group(1) if m else default

    def _to_task(self, project: str, issue: dict[str, Any], comments: list[Any]) -> Task:
        labels = [lbl["name"] if isinstance(lbl, dict) else str(lbl) for lbl in issue["labels"]]
        body = issue.get("body") or ""
        if issue["state"] == "closed":
            status = (
                TaskStatus.CLOSED if issue.get("state_reason") == "not_planned" else TaskStatus.DONE
            )
        else:
            status = next(
                (s for lbl in labels if (s := _STATUS_LABELS.get(lbl.lower()))), TaskStatus.OPEN
            )
        due = parse_due(body)
        milestone = issue.get("milestone") or {}
        if due is None and milestone.get("due_on"):
            due = datetime.fromisoformat(milestone["due_on"].replace("Z", "+00:00")).date()
        return Task(
            ref=self._ref(project, issue["number"]),
            title=issue["title"],
            status=status,
            assignees=[a["login"] for a in issue.get("assignees") or []],
            due=due,
            estimate_hours=parse_estimate(body, labels),
            labels=labels,
            client_facing="client-facing" in (lbl.lower() for lbl in labels),
            url=issue.get("html_url"),
            updated_at=_ts(issue.get("updated_at")),
            comments=[
                Comment(
                    author=(c.get("user") or {}).get("login", "ghost"),
                    body=c.get("body") or "",
                    created_at=datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")),
                )
                for c in comments
            ],
        )

    # ------------------------------------------------------------ protocol

    async def get_task(self, ref: TaskRef) -> Task:
        base = f"/repos/{ref.project}/issues/{ref.id}"
        issue = (await self._get(base)).json()
        comments = await self._get_all(f"{base}/comments") if issue.get("comments") else []
        return self._to_task(ref.project, issue, comments)

    async def list_tasks(self, project: str, *, include_closed: bool = False) -> list[Task]:
        issues = await self._get_all(
            f"/repos/{project}/issues",
            {"state": "all" if include_closed else "open", "per_page": 100},
        )
        return [self._to_task(project, i, []) for i in issues if "pull_request" not in i]

    async def list_dependencies(self, ref: TaskRef) -> list[Edge]:
        base = f"/repos/{ref.project}/issues/{ref.id}"
        issue = (await self._get(base)).json()
        edges: list[Edge] = []
        deps = issue.get("issue_dependencies_summary") or {}
        if deps.get("total_blocked_by", deps.get("blocked_by", 0)):
            for other in await self._get_all(f"{base}/dependencies/blocked_by"):
                src = self._ref(self._project_of(other, ref.project), other["number"])
                edges.append(Edge(source=src, target=ref))
        if deps.get("total_blocking", deps.get("blocking", 0)):
            for other in await self._get_all(f"{base}/dependencies/blocking"):
                tgt = self._ref(self._project_of(other, ref.project), other["number"])
                edges.append(Edge(source=ref, target=tgt))
        if (issue.get("sub_issues_summary") or {}).get("total"):
            for child in await self._get_all(f"{base}/sub_issues"):
                tgt = self._ref(self._project_of(child, ref.project), child["number"])
                edges.append(Edge(source=ref, target=tgt, kind=EdgeKind.PARENT_OF))
        blocked_by, blocks = parse_issue_links(issue.get("body"))
        edges += [Edge(source=self._ref(ref.project, n), target=ref) for n in blocked_by]
        edges += [Edge(source=ref, target=self._ref(ref.project, n)) for n in blocks]
        unique: dict[tuple[str, str, str], Edge] = {}
        for e in edges:
            unique.setdefault((str(e.source), str(e.target), e.kind), e)
        return list(unique.values())

    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None:
        raise ReadOnlyAdapterError("GitHub adapter is read-only in Phase 1")

    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task:
        raise ReadOnlyAdapterError("GitHub adapter is read-only in Phase 1")

    def subscribe(self, handler: EventHandler) -> Unsubscribe:
        self._handlers.append(handler)
        return lambda: self._handlers.remove(handler)

    # ------------------------------------------------------------- webhooks

    async def handle_webhook(
        self, event: str, payload: dict[str, Any], delivery_id: str | None = None
    ) -> TrackerEvent | None:
        """Translate a GitHub webhook delivery into a `TrackerEvent` and notify subscribers.

        `delivery_id` is the `X-GitHub-Delivery` header. Returns None when the
        delivery is ignored: not an issue event, a duplicate, the agent's own
        change, or part of a burst (see `agentic_pm.ingress`). The reason is
        kept in `self.last_decision`.
        """
        issue = payload.get("issue")
        repo = (payload.get("repository") or {}).get("full_name")
        if not issue or not repo or "pull_request" in issue:
            return None
        action = payload.get("action", "")
        if event == "issues":
            kind = {
                "opened": TrackerEventKind.CREATED,
                "deleted": TrackerEventKind.DELETED,
            }.get(action, TrackerEventKind.UPDATED)
            changed = sorted((payload.get("changes") or {}).keys()) or [action]
        elif event == "issue_comment":
            kind, changed = TrackerEventKind.COMMENTED, ["comments"]
        elif event in ("issue_dependencies", "sub_issues"):
            kind, changed = TrackerEventKind.LINKED, [event]
        else:
            return None
        ref = self._ref(repo, issue["number"])
        actor = (payload.get("sender") or {}).get("login")
        text = (payload.get("comment") or {}).get("body") if event == "issue_comment" else None
        self.last_decision = self.gate.admit(
            ticket=str(ref), kind=kind, delivery_id=delivery_id, actor=actor, text=text
        )
        if not self.last_decision.admitted:
            return None
        evt = TrackerEvent(
            kind=kind,
            ref=ref,
            changed_fields=changed,
            at=datetime.now(UTC),
            actor=actor,
        )
        for h in list(self._handlers):
            await h(evt)
        return evt

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = ["GitHubAdapter", "GitHubError", "verify_signature"]
