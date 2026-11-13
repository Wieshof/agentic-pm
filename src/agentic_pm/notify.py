"""Sending messages to people through their channel (email in Phase 2)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

from agentic_pm.adapters.base import TaskRef
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import make_message_id, task_address


class Notifier(Protocol):
    async def notify(
        self,
        handle: str,
        subject: str,
        text: str,
        *,
        ref: TaskRef | None = None,
        in_reply_to: str | None = None,
    ) -> bool:
        """Deliver a message; False if the person has no usable channel."""
        ...


@dataclass
class Sent:
    handle: str
    subject: str
    text: str
    ref: TaskRef | None
    in_reply_to: str | None


@dataclass
class RecordingNotifier:
    """Collects messages instead of sending them (tests, `--dry-run`)."""

    sent: list[Sent] = field(default_factory=list)

    async def notify(
        self,
        handle: str,
        subject: str,
        text: str,
        *,
        ref: TaskRef | None = None,
        in_reply_to: str | None = None,
    ) -> bool:
        self.sent.append(Sent(handle, subject, text, ref, in_reply_to))
        return True


class EmailNotifier:
    def __init__(
        self,
        cfg: TeamConfig,
        send: Callable[[EmailMessage], None] | None = None,
        sender: str | None = None,
    ) -> None:
        from agentic_pm.briefs import smtp

        self.cfg = cfg
        self._send = send or smtp.send
        self.sender = sender or cfg.project.agent_email or smtp.sender_address()

    def build(
        self,
        handle: str,
        subject: str,
        text: str,
        *,
        ref: TaskRef | None = None,
        in_reply_to: str | None = None,
    ) -> EmailMessage | None:
        to = self.cfg.people[handle].channels.email
        if not to:
            return None
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to
        agent = self.cfg.project.agent_email
        if ref is not None and agent:
            msg["Message-ID"] = make_message_id(ref, agent)
            if reply_to := task_address(agent, ref):
                msg["Reply-To"] = reply_to
        else:
            msg["Message-ID"] = make_msgid(domain=(agent or self.sender).rsplit("@", 1)[-1])
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        msg.set_content(text)
        return msg

    async def notify(
        self,
        handle: str,
        subject: str,
        text: str,
        *,
        ref: TaskRef | None = None,
        in_reply_to: str | None = None,
    ) -> bool:
        msg = self.build(handle, subject, text, ref=ref, in_reply_to=in_reply_to)
        if msg is None:
            return False
        await asyncio.to_thread(self._send, msg)
        return True
