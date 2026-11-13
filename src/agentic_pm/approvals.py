"""Signed approval tokens: approvals without a database.

A change that needs someone's OK is packed into a token signed with
`AGENT_PM_SIGNING_KEY` (HMAC-SHA256). The token carries the task, the patch,
who may approve it, when it expires and a snapshot of the fields it touches.
Approving re-checks that snapshot against the live task: if anything changed
in the meantime, the approval is "stale" and nothing is applied. That also
makes approving the same token twice harmless.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from agentic_pm.adapters.base import Channel, Task, TaskPatch, TaskRef

DEFAULT_TTL = 72 * 3600
PATCH_FIELDS = ("status", "due", "estimate_hours", "assignees")


class InvalidToken(ValueError):
    pass


class ExpiredToken(InvalidToken):
    pass


class ApprovalRequest(BaseModel):
    v: int = 1
    ref: TaskRef
    patch: TaskPatch
    before: dict[str, Any]
    tier: str
    reason: str
    actor: str
    channel: Channel
    approver: str  # team.yaml handle
    exp: int

    @property
    def request_id(self) -> str:
        raw = json.dumps(
            [str(self.ref), self.patch.model_dump(mode="json"), self.reason, self.exp],
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:12]


def snapshot(task: Task, patch: TaskPatch) -> dict[str, Any]:
    """Current values of exactly the fields the patch wants to change."""
    data = task.model_dump(mode="json")
    out: dict[str, Any] = {}
    for field in PATCH_FIELDS:
        if getattr(patch, field) is not None:
            value = data[field]
            out[field] = sorted(value) if isinstance(value, list) else value
    return out


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Signer:
    def __init__(self, key: str | bytes, clock: Any = time.time) -> None:
        if not key:
            raise ValueError("AGENT_PM_SIGNING_KEY is not set; approvals need it")
        self._key = key.encode() if isinstance(key, str) else key
        self._clock = clock

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Signer:
        env = dict(os.environ) if env is None else env
        return cls(env.get("AGENT_PM_SIGNING_KEY", ""))

    def now(self) -> int:
        return int(self._clock())

    def sign(self, request: ApprovalRequest) -> str:
        body = _b64(request.model_dump_json().encode())
        sig = _b64(hmac.new(self._key, body.encode(), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def verify(self, token: str) -> ApprovalRequest:
        try:
            body, sig = token.split(".", 1)
        except ValueError:
            raise InvalidToken("malformed token") from None
        expected = _b64(hmac.new(self._key, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise InvalidToken("signature mismatch")
        try:
            request = ApprovalRequest.model_validate_json(_unb64(body))
        except (ValidationError, ValueError) as e:
            raise InvalidToken("unreadable token") from e
        if request.exp < self.now():
            raise ExpiredToken("this approval link has expired")
        return request
