"""Incoming chat messages: voice notes, confirmations, answers, and everything else.

Order of handling for one message from a known person:

1. Encrypted (Matrix E2EE) → friendly note, nothing else.
2. Voice note → transcribed locally (agentic_pm.speech), then treated as text.
3. Reply to a signed proposal ("Should I set … to done?") + yes/no
   → `Guard.propose(owner_confirmed=True)`: applied if they're the owner,
   otherwise it becomes a normal approval request.
4. Reply to a "due?" / "estimate?" question + a readable date or estimate
   → one confirmation question back (never applied directly).
5. Everything else → the shared `Router` (note, how-to, scope, triangulation),
   with the task taken from the replied-to message or a single "#12".

Senders not in team.yaml are ignored.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from agentic_pm.adapters._text import format_hours
from agentic_pm.adapters.base import (
    AuditMeta,
    Channel,
    ReadOnlyAdapterError,
    TaskNotFoundError,
    TaskRef,
)
from agentic_pm.audit import RiskTier, classify_patch
from agentic_pm.chat import tags
from agentic_pm.chat.answers import parse_date, parse_estimate, yes_no
from agentic_pm.chat.base import ChatEvent, ChatTransport
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import InboundMessage
from agentic_pm.inbound import Router
from agentic_pm.knowledge import _ID
from agentic_pm.messages import describe_patch, friendly_date, render
from agentic_pm.speech import Transcriber

log = logging.getLogger("agentic_pm.chat")


class ChatRouter:
    def __init__(
        self,
        cfg: TeamConfig,
        router: Router,
        transcriber: Transcriber | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.cfg = cfg
        self.router = router
        self.guard = router.guard
        self.transcriber = transcriber
        self.today = today

    def _ref(self, task_id: str) -> TaskRef:
        return TaskRef(tracker=self.cfg.project.tracker, project=self.cfg.project.repo, id=task_id)

    async def _say(
        self, transport: ChatTransport, evt: ChatEvent, handle: str, key: str, **kw: str
    ) -> None:
        lang = self.cfg.language_of(handle)
        await transport.reply(evt, render(lang, key, name=self.cfg.display_name(handle), **kw))

    async def handle(self, transport: ChatTransport, evt: ChatEvent) -> str:
        handle = self.cfg.handle_for_chat(evt.platform, evt.sender)
        if handle is None:
            return "ignored_unknown_sender"
        if evt.encrypted:
            await self._say(transport, evt, handle, "chat_encrypted")
            return "encrypted"

        text, voice = evt.text, False
        if evt.audio:
            if self.transcriber is None:
                await self._say(transport, evt, handle, "chat_voice_off")
                return "voice_off"
            try:
                audio = await transport.fetch_audio(evt, evt.audio[0])
                lang = self.cfg.language_of(handle).split("-")[0]
                text = await self.transcriber.transcribe(audio, language=lang)
                del audio  # RAM only, and not a moment longer than needed
            except Exception:
                log.exception("voice note could not be transcribed")
                text = ""
            if not text.strip():
                await self._say(transport, evt, handle, "chat_voice_failed")
                return "voice_failed"
            voice = True

        tag = tags.parse(evt.reply_to_text)
        if tag is not None and tag.field:
            done = await self._confirm(transport, evt, handle, tag, text)
            if done is not None:
                return done
        if tag is not None and tag.ask:
            asked = await self._answer(transport, evt, handle, tag, text)
            if asked is not None:
                return asked

        ref = self._ref(tag.id) if tag is not None else None
        if ref is None:
            ids = {m.group(1) for m in _ID.finditer(text)}
            if len(ids) == 1:
                ref = self._ref(ids.pop())
        msg = InboundMessage(
            sender=evt.sender,
            handle=handle,
            ref=ref,
            subject="",
            text=text,
            message_id=None,
            channel=Channel(evt.platform),
            voice=voice,
        )
        return await self.router.handle(msg)

    async def _confirm(
        self, transport: ChatTransport, evt: ChatEvent, handle: str, tag: tags.Tag, text: str
    ) -> str | None:
        answer = yes_no(text)
        if answer is None:
            return None  # not a yes/no: treat it as a normal message
        signer = self.guard.signer
        patch = tags.verified_patch(tag, signer.key if signer else None)
        if patch is None:
            await self._say(transport, evt, handle, "confirm_unverified", id=tag.id)
            return "confirm_unverified"
        if not answer:
            await self._say(transport, evt, handle, "confirm_declined", id=tag.id)
            return "confirm_declined"
        ref = self._ref(tag.id)
        try:
            task = await self.guard.adapter.get_task(ref)
        except TaskNotFoundError:
            await self._say(transport, evt, handle, "chat_unknown_task")
            return "asked_for_task"
        if classify_patch(task, patch) is RiskTier.LOW:  # already like that
            await self._say(transport, evt, handle, "confirm_stale", id=tag.id)
            return "confirm_stale"
        lang = self.cfg.language_of(handle)
        change, _ = describe_patch(task, patch, lang)
        meta = AuditMeta(actor=handle, channel=Channel(evt.platform), reason="confirmed in chat")
        try:
            outcome = await self.guard.propose(ref, patch, meta, owner_confirmed=True)
        except ReadOnlyAdapterError:
            return "writes_disabled"
        if outcome.applied:
            await self._say(transport, evt, handle, "confirm_applied", id=tag.id, change=change)
            return "confirm_applied"
        names = ", ".join(self.cfg.display_name(h) for h in outcome.waiting_for)
        await self._say(transport, evt, handle, "confirm_pending", names=names)
        return "confirm_pending"

    async def _answer(
        self, transport: ChatTransport, evt: ChatEvent, handle: str, tag: tags.Tag, text: str
    ) -> str | None:
        signer = self.guard.signer
        if signer is None or not self.guard.adapter.capabilities.writes:
            return None  # can't propose a change: keep the answer as a note
        lang = self.cfg.language_of(handle)
        try:
            task = await self.guard.adapter.get_task(self._ref(tag.id))
        except TaskNotFoundError:
            return None
        common = {"id": task.ref.id, "title": task.title}
        if tag.ask == "due" and (d := parse_date(text, self.today())):
            question = render(lang, "confirm_due", date=friendly_date(d, lang), **common)
            proposal = tags.proposal(signer.key, task.ref.id, "due", d.isoformat())
        elif tag.ask == "estimate" and (h := parse_estimate(text)):
            question = render(lang, "confirm_estimate", hours=format_hours(h), **common)
            proposal = tags.proposal(signer.key, task.ref.id, "estimate", f"{h:g}")
        else:
            return None
        await transport.reply(evt, f"{question}\n\n{proposal.render()}")
        return f"{tag.ask}_confirm_asked"


async def poll_chat(transport: ChatTransport, chat_router: ChatRouter) -> list[str]:
    """Handle everything new on one transport; each message is acknowledged once."""
    outcomes: list[str] = []
    for evt in await transport.receive():
        try:
            outcomes.append(await chat_router.handle(transport, evt))
        except Exception:
            log.exception("chat message from %s could not be handled", evt.platform)
            outcomes.append("failed")
        finally:
            await transport.ack(evt)
    return outcomes
