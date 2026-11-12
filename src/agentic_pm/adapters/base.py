"""Tracker-agnostic data model and the `TrackerAdapter` protocol.

Every repository connector (GitHub, OpenProject, Plane, ...) implements
`TrackerAdapter`. The reasoning engine and the MCP server only ever talk to
this interface, never to a tracker SDK directly. See docs/architecture.md.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskRef(_Model):
    """Stable reference to a task in a specific tracker."""

    tracker: str = Field(description="Adapter name, e.g. 'github'")
    project: str = Field(description="Repo / project key, e.g. 'org/repo'")
    id: str = Field(description="Tracker-native task id, e.g. '142'")

    def __str__(self) -> str:
        return f"{self.tracker}:{self.project}#{self.id}"


class TaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    BLOCKED = "blocked"
    DONE = "done"
    CLOSED = "closed"


class Comment(_Model):
    author: str
    body: str
    created_at: datetime


class Task(_Model):
    ref: TaskRef
    title: str
    status: TaskStatus
    assignees: list[str] = []
    due: date | None = None
    estimate_hours: float | None = None
    labels: list[str] = []
    client_facing: bool = Field(
        default=False, description="Due date is committed to an external client"
    )
    url: str | None = None
    comments: list[Comment] = []


class EdgeKind(StrEnum):
    BLOCKS = "blocks"  # source must finish before target can start
    RELATES = "relates"
    PARENT_OF = "parent_of"


class Edge(_Model):
    source: TaskRef
    target: TaskRef
    kind: EdgeKind = EdgeKind.BLOCKS


class TaskPatch(_Model):
    """Partial update. `None` means 'leave unchanged'."""

    status: TaskStatus | None = None
    due: date | None = None
    estimate_hours: float | None = None
    assignees: list[str] | None = None
    add_labels: list[str] = []
    remove_labels: list[str] = []


class Channel(StrEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    VOICE = "voice"
    CHAT = "chat"
    WEB = "web"
    SYSTEM = "system"


class AuditMeta(_Model):
    """Who caused a write, through which channel, and why. Rendered into the audit footer."""

    actor: str = Field(description="Person handle from team.yaml, or 'agent'")
    channel: Channel
    reason: str
    approved_by: str | None = None


class TrackerEventKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    COMMENTED = "commented"
    DELETED = "deleted"
    LINKED = "linked"


class TrackerEvent(_Model):
    kind: TrackerEventKind
    ref: TaskRef
    changed_fields: list[str] = []
    at: datetime


EventHandler = Callable[[TrackerEvent], Awaitable[None]]
Unsubscribe = Callable[[], None]


class TaskNotFoundError(LookupError):
    pass


@runtime_checkable
class TrackerAdapter(Protocol):
    """Bidirectional connector to one issue tracker.

    Adapters are stateless: they fetch live data on every call and never act
    as a source of truth themselves (ADR-0001, docs/data-model.md).
    """

    name: str

    async def get_task(self, ref: TaskRef) -> Task: ...

    async def list_dependencies(self, ref: TaskRef) -> list[Edge]:
        """All edges where `ref` is source or target."""
        ...

    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None: ...

    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task: ...

    def subscribe(self, handler: EventHandler) -> Unsubscribe: ...
