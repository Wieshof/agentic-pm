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

The same router serves email and chat (`msg.channel`); replies go back on the
channel the message came from. After filing the message, a status claim
that contradicts the tracker ("#12 is done" while it's open) becomes one
question to the person who can settle it (inconsistency triangulation, #15):

* chat, from the task owner: "Should I set it to done?" (reply yes/no)
* otherwise: a normal approval request to the owner (email can be forged,
  so an email claim never counts as the owner's confirmation)

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
    Task,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TaskStatus,
    TrackerEvent,
    TrackerEventKind,
)
from agentic_pm.audit import RiskTier, audit_meta_in
from agentic_pm.chat import tags
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import InboundMessage
from agentic_pm.engine.triangulation import conflict, detect_claim
from agentic_pm.knowledge import HOWTO_MARKERS, analyze, render_howto, render_note
from agentic_pm.llm.base import LLMProvider
from agentic_pm.messages import language_name, render, status_name, tracker_name
from agentic_pm.notify import Notifier

HOWTO_REQUEST = "howto-request"
CHANNEL_NAMES = {
    "en": {"email": "email", "matrix": "Matrix", "signal": "Signal"},
    "de": {"email": "E-Mail", "matrix": "Matrix", "signal": "Signal"},
}
CHAT_CHANNELS = (Channel.MATRIX, Channel.SIGNAL)


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
        if msg.channel is not Channel.EMAIL:
            subject = ""  # chat has no subject line
        await self.notifier.notify(
            handle,
            subject,
            render(lang, key, name=self.cfg.display_name(handle), **kw),
            ref=ref,
            in_reply_to=msg.message_id,
            channel=msg.channel.value,
        )

    async def handle(self, msg: InboundMessage) -> str:
        agent = (self.cfg.project.agent_email or "").lower()
        if agent and msg.sender == agent:
            return "ignored_self"
        if msg.handle is None:
            return "ignored_unknown_sender"
        handle = msg.handle
        unknown = "ack_unknown_task" if msg.channel is Channel.EMAIL else "chat_unknown_task"
        if msg.ref is None:
            await self._reply(handle, msg, None, unknown)
            return "asked_for_task"
        try:
            task = await self.adapter.get_task(msg.ref)
        except TaskNotFoundError:
            await self._reply(handle, msg, None, unknown)
            return "asked_for_task"
        if not msg.text.strip():
            return "ignored_empty"

        ticket_lang = self.cfg.project.ticket_language
        name = self.cfg.display_name(handle)
        labels = CHANNEL_NAMES.get(ticket_lang.split("-")[0], CHANNEL_NAMES["en"])
        channel = labels.get(msg.channel.value, msg.channel.value)
        if msg.voice:
            channel += " (Sprachnachricht)" if ticket_lang.startswith("de") else " (voice note)"
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
                meta = AuditMeta(
                    actor=handle, channel=msg.channel, reason=f"how-to from {msg.channel.value}"
                )
                await self.guard.comment(msg.ref, md, meta)
                await self._reply(handle, msg, msg.ref, "ack_howto", id=task.ref.id, url=url)
                checked = await self.triangulate(msg, task, handle)
                return f"howto+{checked}" if checked else "howto"
            note = render_note(msg.text, ticket_language=ticket_lang, author=name, channel=channel)
            meta = AuditMeta(
                actor=handle, channel=msg.channel, reason=f"note from {msg.channel.value}"
            )
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
        checked = await self.triangulate(msg, task, handle)
        return f"note+{checked}" if checked else "note"

    async def triangulate(self, msg: InboundMessage, task: Task, handle: str) -> str | None:
        """Ask once when a status claim in `msg` contradicts the tracker (#15)."""
        claim = detect_claim(msg.text)
        found = conflict(task, claim) if claim else None
        signer = self.guard.signer
        if found is None or signer is None or not self.adapter.capabilities.writes:
            return None
        lang = self.cfg.language_of(handle)
        common = {
            "id": task.ref.id,
            "title": task.title,
            "status": status_name(task.status, lang),
            "new": status_name(found.proposed, lang),
            "tracker": tracker_name(self.cfg.project.tracker),
        }
        approvers = self.guard._approvers(task, RiskTier.MEDIUM)
        if msg.channel in CHAT_CHANNELS and handle in approvers:
            tag = tags.proposal(signer.key, task.ref.id, "status", found.proposed.value)
            text = render(lang, "confirm_status_self", evidence=found.claim.evidence, **common)
            await self.notifier.notify(
                handle, "", f"{text}\n\n{tag.render()}", channel=msg.channel.value
            )
            return "status_confirm_asked"
        meta = AuditMeta(
            actor=handle,
            channel=msg.channel,
            reason=f"{self.cfg.display_name(handle)}: “{found.claim.evidence}”",
        )
        outcome = await self.guard.propose(task.ref, TaskPatch(status=found.proposed), meta)
        if outcome.status != "pending":
            return None
        names = ", ".join(self.cfg.display_name(h) for h in outcome.waiting_for or [])
        await self._reply(handle, msg, msg.ref, "status_check_asked", names=names, **common)
        return "status_check_requested"


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
            if any(m in c.body for m in HOWTO_MARKERS):
                return []
            if (meta := audit_meta_in(c.body)) is not None and meta.reason == HOWTO_REQUEST:
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
