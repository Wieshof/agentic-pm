"""The last line of every agent chat message about a task, e.g. ``— #12``.

Chat has no Reply-To or Message-ID, so the agent's own message carries what a
reply needs, the same stateless trick as for email (docs/data-model.md):

    — #12                                  the task
    — #12 · due?                           a question whose answer is a date
    — #12 · estimate?                      … or an estimate
    — #12 · set status done · 3f9a0c21d4   a proposed change, waiting for "yes"

A proposal is HMAC-signed with AGENT_PM_SIGNING_KEY. Signal lets the sender's
app supply the quoted text, so without the signature someone could quote a
"proposal" the agent never made. Matrix quotes are fetched from the server,
but are checked the same way.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel

from agentic_pm.adapters.base import TaskPatch, TaskStatus

Ask = Literal["due", "estimate"]
Field = Literal["due", "estimate", "status"]

_TAG = re.compile(
    r"^— #(?P<id>[A-Za-z0-9][A-Za-z0-9_-]*)"
    r"(?: · (?P<ask>due|estimate)\?"
    r"| · set (?P<field>due|estimate|status) (?P<value>[A-Za-z0-9_.-]+) · (?P<sig>[0-9a-f]{10}))?"
    r"\s*$"
)


class Tag(BaseModel):
    id: str
    ask: Ask | None = None
    field: Field | None = None
    value: str | None = None
    sig: str | None = None

    def render(self) -> str:
        if self.field and self.value and self.sig:
            return f"— #{self.id} · set {self.field} {self.value} · {self.sig}"
        if self.ask:
            return f"— #{self.id} · {self.ask}?"
        return f"— #{self.id}"


def _sig(key: str | bytes, task_id: str, field: str, value: str) -> str:
    msg = f"agent-pm-chat|{task_id}|{field}|{value}".encode()
    k = key.encode() if isinstance(key, str) else key
    return hmac.new(k, msg, hashlib.sha256).hexdigest()[:10]


def proposal(key: str | bytes, task_id: str, field: Field, value: str) -> Tag:
    return Tag(id=task_id, field=field, value=value, sig=_sig(key, task_id, field, value))


def parse(text: str | None) -> Tag | None:
    """The tag on the last tagged line of an agent message, if any."""
    for line in reversed((text or "").strip().splitlines()):
        m = _TAG.match(line.strip())
        if m:
            return Tag(**{k: v for k, v in m.groupdict().items() if v is not None})
    return None


def verified_patch(tag: Tag, key: str | bytes | None) -> TaskPatch | None:
    """The change a proposal tag stands for, only if its signature is valid."""
    if not (key and tag.field and tag.value and tag.sig):
        return None
    if not hmac.compare_digest(tag.sig, _sig(key, tag.id, tag.field, tag.value)):
        return None
    try:
        if tag.field == "due":
            return TaskPatch(due=date.fromisoformat(tag.value))
        if tag.field == "estimate":
            return TaskPatch(estimate_hours=float(tag.value))
        return TaskPatch(status=TaskStatus(tag.value))
    except ValueError:
        return None
