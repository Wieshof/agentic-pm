"""`agent-pm run`: scheduler + web control plane + inbox + how-to loop in one process.

Everything is optional and switched on by configuration:

| Piece            | Needs                                                      |
|------------------|------------------------------------------------------------|
| Briefs, digests  | `cadence:` / `brief.when` in team.yaml, SMTP env vars      |
| Approvals        | AGENT_PM_SIGNING_KEY, project.control_plane_url            |
| GitHub webhooks  | AGENT_PM_GITHUB_WEBHOOK_SECRET (+ webhook in GitHub)       |
| Inbox (replies)  | AGENT_PM_IMAP_* env vars, project.agent_email              |
| Matrix chat      | AGENT_PM_MATRIX_HOMESERVER / _USER / _TOKEN                |
| Signal chat      | AGENT_PM_SIGNAL_API_URL / _NUMBER (signal-cli-rest-api)    |
| Voice notes      | `speech.engine` in team.yaml (local Whisper)               |
| Writes           | project.allow_writes: true                                 |
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from agentic_pm.actions import Guard
from agentic_pm.adapters.base import AuditMeta, Channel, ReadOnlyAdapterError, TrackerAdapter
from agentic_pm.approvals import Signer
from agentic_pm.briefs.digest import end_of_day, weekly_digest
from agentic_pm.briefs.morning import build_email, collect, render_text
from agentic_pm.cadence import Job, run_scheduler
from agentic_pm.chat.tags import Tag
from agentic_pm.config.team import BriefFormat, Interruptions, TeamConfig
from agentic_pm.engine.completeness import Gap
from agentic_pm.engine.dependencies import DependencyGraph
from agentic_pm.engine.followup import FollowUp
from agentic_pm.inbound import HowToLoop, Router
from agentic_pm.llm.base import LLMProvider
from agentic_pm.notify import (
    ChatNotifier,
    EmailNotifier,
    MultiNotifier,
    Notifier,
    RecordingNotifier,
)

if TYPE_CHECKING:
    from agentic_pm.chat.base import ChatTransport
    from agentic_pm.chat.inbound import ChatRouter

log = logging.getLogger("agentic_pm.runtime")
JOB_NAMES = ("briefs", "end_of_day", "weekly_digest", "monthly_health_check", "inbox", "chat")
CHAT_FORMATS = (BriefFormat.EMAIL, BriefFormat.CHAT)


@dataclass
class Runtime:
    cfg: TeamConfig
    adapter: TrackerAdapter
    notifier: Notifier
    guard: Guard
    router: Router
    howto: HowToLoop
    provider: LLMProvider | None
    env: dict[str, str]
    send_email: Callable[[Any], None] | None = None
    chats: list[ChatTransport] = field(default_factory=list)
    chat_router: ChatRouter | None = None
    dry_run: bool = False
    log_lines: list[str] = field(default_factory=list)
    _asked: set[str] = field(default_factory=set)  # this run only: don't note twice

    def today(self) -> date:
        return datetime.now(ZoneInfo(self.cfg.project.timezone)).date()

    def say(self, line: str) -> None:
        self.log_lines.append(line)
        log.info(line)

    # ------------------------------------------------------------------ jobs

    async def briefs(self, handles: list[str] | None = None) -> int:
        from agentic_pm.briefs import smtp
        from agentic_pm.briefs.summary import generate_summary, summary_facts

        today = self.today()
        graph = await DependencyGraph.build(self.adapter, self.cfg.scope)
        sent = 0
        for handle in handles or self.brief_handles():
            person = self.cfg.people[handle]
            if person.brief and person.brief.format is BriefFormat.CHAT:
                sent += await self._chat_brief(handle, today, graph)
                continue
            if not person.channels.email:
                continue
            data = await collect(self.cfg, handle, self.adapter, today, graph)
            summary = None
            if self.provider is not None:
                raw, problems = await generate_summary(
                    self.provider, summary_facts(data), data.language
                )
                summary = None if problems else raw
            sender = self.cfg.project.agent_email or smtp.sender_address(self.env)
            msg = build_email(data, to=person.channels.email, sender=sender, summary=summary)
            if isinstance(self.notifier, RecordingNotifier):
                await self.notifier.notify(handle, str(msg["Subject"]), render_text(data, summary))
            else:
                await asyncio.to_thread(self.send_email or (lambda m: smtp.send(m, self.env)), msg)
            sent += 1
            due = [f for f in data.followups if f.due_today][: data.gap_limit]
            await self._switch(handle, [f for f in due if f.switch], "email")
            await self._record_asked(due)
        self.say(f"briefs: sent {sent}")
        return sent

    async def _chat_brief(self, handle: str, today: date, graph: DependencyGraph) -> int:
        """Short brief in chat; urgent questions one by one, the rest bundled in.

        A question carries a tag (agentic_pm.chat.tags) so the person can just
        reply: "Friday" to "when should it be done?", "yes" to a proposal.
        Adaptive follow-up (agentic_pm.engine.followup) decides what's asked
        today and when to try another channel.
        """
        from agentic_pm.chat import tags
        from agentic_pm.messages import render, status_name, tracker_name

        ch = next((c for c in self.cfg.reach_order(handle) if c in ("matrix", "signal")), None)
        if ch is None:
            return 0
        data = await collect(self.cfg, handle, self.adapter, today, graph)
        lang = data.language
        if data.is_quiet:
            return 0
        due = [f for f in data.followups if f.due_today][: data.gap_limit]
        own_message = self.cfg.people[handle].interruptions is not Interruptions.NONE
        separate = [f for f in due if f.urgent and own_message]
        keys = {f.key for f in separate}
        inline = [f.gap for f in due if f.key not in keys]
        brief = render_text(data.model_copy(update={"gaps": inline, "conflicts": []}))
        if not await self.notifier.notify(handle, "", brief, channel=ch):
            return 0
        stay = [f for f in separate if not f.switch]
        moved = [f for f in separate if f.switch]
        if not await self._switch(handle, moved, ch):
            stay += moved
        for f in stay:
            await self.notifier.notify(handle, "", self._question(f.gap, lang), channel=ch)
        signer = self.guard.signer
        if signer is not None and self.adapter.capabilities.writes:
            for c in data.conflicts:
                text = render(
                    lang,
                    "confirm_status_owner",
                    who=data.names.get((c.by or "").lower()) or c.by or render(lang, "someone"),
                    evidence=c.claim.evidence,
                    id=c.task.ref.id,
                    title=c.task.title,
                    status=status_name(c.task.status, lang),
                    new=status_name(c.proposed, lang),
                    tracker=tracker_name(self.cfg.tracker_of(c.task.ref.source)),
                )
                tag = tags.proposal(
                    signer.key, c.task.ref.id, "status", c.proposed.value, c.task.ref.source
                )
                await self.notifier.notify(handle, "", f"{text}\n\n{tag.render()}", channel=ch)
        await self._record_asked(due)
        return 1

    def _question(self, gap: Gap, lang: str) -> str:
        """One gap as a chat question, tagged so a plain reply finds its task."""
        from agentic_pm.briefs.gap_text import render_gap

        can_propose = self.guard.signer is not None and self.adapter.capabilities.writes
        asks = {"MISSING_DUE": "due", "IMPLICIT_DUE": "due", "MISSING_ESTIMATE": "estimate"}
        ask = asks.get(gap.code) if can_propose else None
        tag = Tag(id=gap.task.ref.id, source=gap.task.ref.source, ask=ask)
        return f"{render_gap(gap, lang)}\n\n{tag.render()}"

    async def _switch(self, handle: str, items: list[FollowUp], current: str) -> bool:
        """Ask `items` on the person's next channel; False if there is none."""
        from agentic_pm.briefs.gap_text import gap_text, render_gap
        from agentic_pm.messages import channel_label

        if not items:
            return True
        nxt = next((c for c in self.cfg.reach_order(handle) if c != current), None)
        if nxt is None:
            return False
        lang = self.cfg.language_of(handle)
        intro = gap_text(lang, "switch_intro", channel=channel_label(current, lang))
        if nxt == "email":
            body = "\n\n".join([intro, *(f"• {render_gap(f.gap, lang)}" for f in items)])
            subject = gap_text(lang, "switch_subject")
            return await self.notifier.notify(handle, subject, body, channel=nxt)
        if not await self.notifier.notify(handle, "", intro, channel=nxt):
            return False
        for f in items:
            await self.notifier.notify(handle, "", self._question(f.gap, lang), channel=nxt)
        return True

    async def _record_asked(self, items: list[FollowUp]) -> None:
        """First time a question is asked: one audited note on the ticket.

        That note is the follow-up's only memory (agentic_pm.engine.followup).
        """
        from agentic_pm.briefs.gap_text import gap_label, gap_text
        from agentic_pm.engine.followup import REASON_PREFIX

        if self.dry_run or not self.adapter.capabilities.writes:
            return
        for f in items:
            if f.asked_on is not None or f.key in self._asked:
                continue
            lang = self.cfg.ticket_language_of(f.gap.task.ref.source)
            self._asked.add(f.key)
            names = ", ".join(self.cfg.display_name(h) for h in f.gap.recipients)
            meta = AuditMeta(
                actor="agent-pm",
                channel=Channel.SYSTEM,
                reason=f"{REASON_PREFIX}{f.gap.code}",
                source=f.gap.task.ref.source,
            )
            text = gap_text(lang, "asked_note", names=names, what=gap_label(f.gap, lang))
            try:
                await self.guard.comment(f.gap.task.ref, text, meta)
            except ReadOnlyAdapterError:
                return

    def brief_handles(self, at: str | None = None) -> list[str]:
        """People whose email or chat brief runs at `at` (None = all of them)."""
        default = self.cfg.cadence.morning_triage
        out = []
        for h, p in self.cfg.people.items():
            if not p.brief or p.brief.format not in CHAT_FORMATS:
                continue
            when = p.brief.when or default
            if at is None or when == at:
                out.append(h)
        return out

    async def end_of_day(self) -> int:
        today = self.today()
        graph = await DependencyGraph.build(self.adapter, self.cfg.scope)
        sent = 0
        for lead in self.cfg.all_leads():
            note = await end_of_day(self.cfg, self.adapter, graph, today, lead)
            if note and await self.notifier.notify(lead, note[0], note[1]):
                sent += 1
        self.say(f"end_of_day: sent {sent}")
        return sent

    async def weekly_digest(self) -> int:
        today = self.today()
        graph = await DependencyGraph.build(self.adapter, self.cfg.scope)
        sent = 0
        for lead in self.cfg.all_leads():
            subject, text = await weekly_digest(self.cfg, self.adapter, graph, today, lead)
            if await self.notifier.notify(lead, subject, text):
                sent += 1
        self.say(f"weekly_digest: sent {sent}")
        return sent

    async def monthly_health_check(self) -> int:
        self.say("monthly_health_check: planned (issue #54), nothing sent yet")
        return 0

    async def inbox(self) -> list[str]:
        from agentic_pm.inbox import ImapInbox, poll_once

        outcomes = await poll_once(ImapInbox(self.env), self.router, self.cfg)
        if outcomes:
            self.say(f"inbox: {', '.join(outcomes)}")
        return outcomes

    async def chat(self) -> list[str]:
        from agentic_pm.chat.inbound import poll_chat

        outcomes: list[str] = []
        if self.chat_router is None:
            return outcomes
        for transport in self.chats:
            outcomes += await poll_chat(transport, self.chat_router)
        if outcomes:
            self.say(f"chat: {', '.join(outcomes)}")
        return outcomes

    async def run_once(self, name: str) -> Any:
        if name == "briefs":
            return await self.briefs()
        if name not in JOB_NAMES:
            raise ValueError(f"unknown job {name!r} (one of {', '.join(JOB_NAMES)})")
        job: Callable[[], Awaitable[Any]] = getattr(self, name)
        return await job()

    # --------------------------------------------------------------- forever

    def jobs(self) -> list[Job]:
        jobs: list[Job] = []
        specs = {
            p.brief.when or self.cfg.cadence.morning_triage
            for p in self.cfg.people.values()
            if p.brief and p.brief.format in CHAT_FORMATS
        }
        for spec in sorted(s for s in specs if s):

            async def run_briefs(_: datetime, spec: str = spec) -> object:
                return await self.briefs(self.brief_handles(spec))

            jobs.append(Job(f"briefs {spec}", spec, run_briefs))
        c = self.cfg.cadence
        for name in ("end_of_day", "weekly_digest", "monthly_health_check"):
            spec = getattr(c, name)
            if spec:
                method: Callable[[], Awaitable[object]] = getattr(self, name)

                async def run_job(
                    _: datetime, m: Callable[[], Awaitable[object]] = method
                ) -> object:
                    return await m()

                jobs.append(Job(name, spec, run_job))
        return jobs

    async def serve(self, host: str = "127.0.0.1", port: int = 8787) -> None:
        import uvicorn

        from agentic_pm.adapters.multi import MultiTracker
        from agentic_pm.web import create_app

        handler = None
        if hasattr(self.adapter, "handle_webhook"):
            handler = self.adapter.handle_webhook
        gitea = self.adapter.name == "gitea"
        per_source = {}
        if isinstance(self.adapter, MultiTracker):  # one endpoint per source (ADR-0006)
            for key, sub in self.adapter.adapters.items():
                if hasattr(sub, "handle_webhook"):
                    prefix = self.cfg.sources[key].env_prefix(key)
                    secret = self.env.get(f"{prefix}WEBHOOK_SECRET")
                    per_source[key] = (sub.name, secret, sub.handle_webhook)
        if handler is not None or per_source:
            self.adapter.subscribe(self.howto.on_event)
        app = create_app(
            self.guard,
            webhook_secret=self.env.get("AGENT_PM_GITHUB_WEBHOOK_SECRET"),
            on_github_webhook=None if gitea else handler,
            gitea_webhook_secret=self.env.get("AGENT_PM_GITEA_WEBHOOK_SECRET"),
            on_gitea_webhook=handler if gitea else None,
            source_webhooks=per_source,
        )
        tasks: list[Awaitable[Any]] = [
            uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info")).serve(),
            run_scheduler(self.jobs(), self.cfg.project.timezone),
        ]
        if self.env.get("AGENT_PM_IMAP_HOST"):
            tasks.append(self._poll_inbox_forever())
        if self.chats:
            tasks.append(self._poll_chat_forever())
        await asyncio.gather(*tasks)

    async def _poll_chat_forever(self) -> None:
        while True:
            try:
                await self.chat()
            except Exception:
                log.exception("chat poll failed")
            await asyncio.sleep(self.cfg.cadence.chat_poll_seconds)

    async def _poll_inbox_forever(self) -> None:
        while True:
            try:
                await self.inbox()
            except Exception:
                log.exception("inbox poll failed")
            await asyncio.sleep(self.cfg.cadence.inbox_poll_minutes * 60)


def build_runtime(
    cfg: TeamConfig,
    adapter: TrackerAdapter,
    *,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    use_llm: bool = True,
) -> Runtime:
    env = dict(os.environ) if env is None else env
    chats = chat_transports(cfg, env)
    notifier: Notifier
    if dry_run:
        notifier = RecordingNotifier()
    else:
        by_channel: dict[str, Notifier] = {"email": EmailNotifier(cfg)}
        for t in chats:
            by_channel[t.name] = ChatNotifier(cfg, t)
        notifier = MultiNotifier(cfg, by_channel)
    signer = Signer(env["AGENT_PM_SIGNING_KEY"]) if env.get("AGENT_PM_SIGNING_KEY") else None
    guard = Guard(cfg, adapter, notifier, signer)
    provider = None
    if use_llm:
        from agentic_pm.llm import provider_from_settings

        provider = provider_from_settings(cfg.llm)
    router = Router(cfg, guard, notifier, provider)
    chat_router = None
    if chats:
        from agentic_pm.chat.inbound import ChatRouter
        from agentic_pm.speech import transcriber_from_settings

        tz = ZoneInfo(cfg.project.timezone)
        chat_router = ChatRouter(
            cfg,
            router,
            transcriber_from_settings(cfg.speech),
            today=lambda: datetime.now(tz).date(),
        )
    return Runtime(
        cfg=cfg,
        adapter=adapter,
        notifier=notifier,
        guard=guard,
        router=router,
        howto=HowToLoop(cfg, guard, notifier),
        provider=provider,
        env=env,
        chats=chats,
        chat_router=chat_router,
        dry_run=dry_run,
    )


def chat_transports(cfg: TeamConfig, env: dict[str, str]) -> list[ChatTransport]:
    """The chat transports whose environment variables are set."""
    out: list[ChatTransport] = []
    if env.get("AGENT_PM_MATRIX_HOMESERVER"):
        from agentic_pm.chat.matrix import MatrixTransport

        allowed = {p.channels.matrix for p in cfg.people.values() if p.channels.matrix}
        out.append(MatrixTransport.from_env(env, allowed))
    if env.get("AGENT_PM_SIGNAL_API_URL"):
        from agentic_pm.chat.signal import SignalTransport

        out.append(SignalTransport.from_env(env))
    return out
