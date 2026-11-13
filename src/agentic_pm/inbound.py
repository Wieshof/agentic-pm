"""Inbound messages and the how-to loop.

`Router.handle()` decides what an inbound message means for its task:

| Message kind (Knowledge Extractor) | What happens                                        |
|------------------------------------|-----------------------------------------------------|
| solution                           | how-to section on the ticket, in ticket_language    |
| status / question / no LLM         | the note is added to the ticket as-is               |
| scope_change                       | leads are told; **no** work is created (#50 later)  |
| other (thanks, greetings)          | nothing is written                                  |

Every write is a low-risk comment with the audit footer. Messages from
senders who are not in team.yaml are never acted on.

`HowToLoop` asks whoever closed a task for a short explanation. Whether it has
already asked is read from its own audited comment on the ticket, so no state
is kept anywhere else.
"""

from __future__ import annotations

import contextlib

from agentic_pm.actions import Guard
from agentic_pm.adapters.base import (
    AuditMeta,
    Channel,
    ReadOnlyAdapterError,
    TaskNotFoundError,
    TaskRef,
    TaskStatus,
    TrackerEvent,
    TrackerEventKind,
)
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import InboundMessage
from agentic_pm.knowledge import HOWTO_MARKERS, analyze, render_howto, render_note
from agentic_pm.llm.base import LLMProvider
from agentic_pm.messages import language_name, render
from agentic_pm.notify import Notifier

HOWTO_REQUEST = "howto-request"
CHANNEL_NAMES = {"en": {"email": "email"}, "de": {"email": "E-Mail"}}


class Router:
    def __init__(
        self,
        cfg: TeamConfig,
        guard: Guard,
        notifier: Notifier,
        provider: LLMProvider | None = None,
    ) -> None:
        self.cfg = cfg
        self.guard = guard
        self.adapter = guard.adapter
        self.notifier = notifier
        self.provider = provider

    async def _reply(
        self, handle: str, msg: InboundMessage, ref: TaskRef | None, key: str, **kw: str
    ) -> None:
        lang = self.cfg.language_of(handle)
        subject = msg.subject if msg.subject.lower().startswith("re:") else f"Re: {msg.subject}"
        await self.notifier.notify(
            handle,
            subject,
            render(lang, key, name=self.cfg.display_name(handle), **kw),
            ref=ref,
            in_reply_to=msg.message_id,
        )

    async def handle(self, msg: InboundMessage) -> str:
        agent = (self.cfg.project.agent_email or "").lower()
        if agent and msg.sender == agent:
            return "ignored_self"
        if msg.handle is None:
            return "ignored_unknown_sender"
        handle = msg.handle
        if msg.ref is None:
            await self._reply(handle, msg, None, "ack_unknown_task")
            return "asked_for_task"
        try:
            task = await self.adapter.get_task(msg.ref)
        except TaskNotFoundError:
            await self._reply(handle, msg, None, "ack_unknown_task")
            return "asked_for_task"
        if not msg.text.strip():
            return "ignored_empty"

        ticket_lang = self.cfg.project.ticket_language
        name = self.cfg.display_name(handle)
        channel = CHANNEL_NAMES.get(ticket_lang.split("-")[0], CHANNEL_NAMES["en"])["email"]
        analysis, problems = (None, ["no llm"])
        if self.provider is not None:
            analysis, problems = await analyze(
                self.provider,
                msg.text,
                task_title=task.title,
                author=name,
                ticket_language=ticket_lang,
            )
        ok = analysis is not None and not problems
        url = task.url or f"#{task.ref.id}"
        try:
            if ok and analysis is not None and analysis.kind == "other":
                return "ignored_other"
            if ok and analysis is not None and analysis.kind == "solution":
                md = render_howto(
                    analysis,
                    ticket_language=ticket_lang,
                    author=name,
                    channel=channel,
                    source_language=self.cfg.language_of(handle),
                )
                meta = AuditMeta(actor=handle, channel=Channel.EMAIL, reason="how-to from email")
                await self.guard.comment(msg.ref, md, meta)
                await self._reply(handle, msg, msg.ref, "ack_howto", id=task.ref.id, url=url)
                return "howto"
            note = render_note(msg.text, ticket_language=ticket_lang, author=name, channel=channel)
            meta = AuditMeta(actor=handle, channel=Channel.EMAIL, reason="note from email")
            await self.guard.comment(msg.ref, note, meta)
        except ReadOnlyAdapterError:
            return "writes_disabled"
        if ok and analysis is not None and analysis.kind == "scope_change":
            leads = self.cfg.project.leads
            for lead in leads:
                lang = self.cfg.language_of(lead)
                await self.notifier.notify(
                    lead,
                    render(lang, "scope_lead_subject", requester=name),
                    render(
                        lang,
                        "scope_lead_body",
                        name=self.cfg.display_name(lead),
                        requester=name,
                        id=task.ref.id,
                        title=task.title,
                        quote=msg.text.strip().replace("\n", "\n> "),
                    ),
                    ref=msg.ref,
                )
            names = ", ".join(self.cfg.display_name(lead) for lead in leads)
            await self._reply(handle, msg, msg.ref, "ack_scope", leads=names)
            return "scope_flagged"
        await self._reply(handle, msg, msg.ref, "ack_note", id=task.ref.id, url=url)
        return "note"


class HowToLoop:
    """Ask for a short how-to when a task is closed (KPI: ≥ 50 % of closed tickets)."""

    def __init__(self, cfg: TeamConfig, guard: Guard, notifier: Notifier) -> None:
        self.cfg = cfg
        self.guard = guard
        self.adapter = guard.adapter
        self.notifier = notifier

    async def on_event(self, evt: TrackerEvent) -> None:
        if evt.kind is TrackerEventKind.UPDATED and "closed" in evt.changed_fields:
            await self.ask(evt.ref)

    async def ask(self, ref: TaskRef) -> list[str]:
        task = await self.adapter.get_task(ref)
        if task.status is not TaskStatus.DONE:
            return []
        for c in task.comments:
            if any(m in c.body for m in HOWTO_MARKERS) or f'"reason": "{HOWTO_REQUEST}"' in c.body:
                return []
        handles = [
            h
            for login in task.assignees
            if (h := self.cfg.handle_for_login(login)) and self.cfg.people[h].channels.email
        ]
        ticket_lang = self.cfg.project.ticket_language
        for h in handles:
            lang = self.cfg.language_of(h)
            await self.notifier.notify(
                h,
                render(lang, "howto_subject", id=task.ref.id),
                render(
                    lang,
                    "howto_body",
                    name=self.cfg.display_name(h),
                    id=task.ref.id,
                    title=task.title,
                    ticket_language=language_name(ticket_lang, lang),
                ),
                ref=ref,
            )
        if handles:
            names = ", ".join(self.cfg.display_name(h) for h in handles)
            meta = AuditMeta(actor="agent", channel=Channel.SYSTEM, reason=HOWTO_REQUEST)
            with contextlib.suppress(ReadOnlyAdapterError):  # read-only: ask anyway
                await self.guard.comment(
                    ref, render(ticket_lang, "howto_asked_comment", names=names), meta
                )
        return handles
