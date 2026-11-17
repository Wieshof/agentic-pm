"""Sending messages to people through their channels: email, Matrix, Signal.

`MultiNotifier` picks the person's channel (`TeamConfig.reach_order`, or the
channel a reply should go back to) and falls back to the next one.
"""

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
        channel: str | None = None,
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
    channel: str | None = None


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
        channel: str | None = None,
    ) -> bool:
        self.sent.append(Sent(handle, subject, text, ref, in_reply_to, channel))
        return True


def header_safe(value: str) -> str:
    """One line: a task title with a line break must not break (or inject) mail headers."""
    return " ".join(value.split())


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
        msg["Subject"] = header_safe(subject)
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
        channel: str | None = None,
    ) -> bool:
        if channel not in (None, "email"):
            return False
        msg = self.build(handle, subject, text, ref=ref, in_reply_to=in_reply_to)
        if msg is None:
            return False
        await asyncio.to_thread(self._send, msg)
        return True


class ChatSender(Protocol):
    """The sending half of a chat transport (agentic_pm.chat)."""

    name: str

    async def send(self, to: str, text: str) -> None: ...


def chat_text(subject: str, text: str, ref: TaskRef | None = None) -> str:
    """Chat has no subject line: put it on top, and tag the task so a reply finds it."""
    from agentic_pm.chat.tags import Tag

    body = f"{subject}\n\n{text}" if subject else text
    return f"{body}\n\n{Tag(id=ref.id).render()}" if ref is not None else body


class ChatNotifier:
    """Sends to one chat platform (`matrix` or `signal`)."""

    def __init__(self, cfg: TeamConfig, sender: ChatSender) -> None:
        self.cfg = cfg
        self.sender = sender

    async def notify(
        self,
        handle: str,
        subject: str,
        text: str,
        *,
        ref: TaskRef | None = None,
        in_reply_to: str | None = None,
        channel: str | None = None,
    ) -> bool:
        if channel not in (None, self.sender.name):
            return False
        address = getattr(self.cfg.people[handle].channels, self.sender.name, None)
        if not address:
            return False
        await self.sender.send(address, chat_text(subject, text, ref))
        return True


class MultiNotifier:
    """Tries the person's channels in order (or exactly `channel`, for replies)."""

    def __init__(self, cfg: TeamConfig, by_channel: dict[str, Notifier]) -> None:
        self.cfg = cfg
        self.by_channel = by_channel

    async def notify(
        self,
        handle: str,
        subject: str,
        text: str,
        *,
        ref: TaskRef | None = None,
        in_reply_to: str | None = None,
        channel: str | None = None,
    ) -> bool:
        order = [channel] if channel else self.cfg.reach_order(handle)
        for name in order:
            notifier = self.by_channel.get(name)
            if notifier is not None and await notifier.notify(
                handle, subject, text, ref=ref, in_reply_to=in_reply_to, channel=name
            ):
                return True
        return False
