"""`agent-pm run`: scheduler + web control plane + inbox + how-to loop in one process.

Everything is optional and switched on by configuration:

| Piece            | Needs                                                      |
|------------------|------------------------------------------------------------|
| Briefs, digests  | `cadence:` / `brief.when` in team.yaml, SMTP env vars      |
| Approvals        | AGENT_PM_SIGNING_KEY, project.control_plane_url            |
| GitHub webhooks  | AGENT_PM_GITHUB_WEBHOOK_SECRET (+ webhook in GitHub)       |
| Inbox (replies)  | AGENT_PM_IMAP_* env vars, project.agent_email              |
| Writes           | project.allow_writes: true                                 |
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from agentic_pm.actions import Guard
from agentic_pm.adapters.base import TrackerAdapter
from agentic_pm.approvals import Signer
from agentic_pm.briefs.digest import end_of_day, weekly_digest
from agentic_pm.briefs.morning import build_email, collect, render_text
from agentic_pm.cadence import Job, run_scheduler
from agentic_pm.config.team import BriefFormat, TeamConfig
from agentic_pm.engine.dependencies import DependencyGraph
from agentic_pm.inbound import HowToLoop, Router
from agentic_pm.llm.base import LLMProvider
from agentic_pm.notify import EmailNotifier, Notifier, RecordingNotifier

log = logging.getLogger("agentic_pm.runtime")
JOB_NAMES = ("briefs", "end_of_day", "weekly_digest", "monthly_health_check", "inbox")


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
    log_lines: list[str] = field(default_factory=list)

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
        graph = await DependencyGraph.build(self.adapter, self.cfg.project.repo)
        sent = 0
        for handle in handles or self.brief_handles():
            person = self.cfg.people[handle]
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
        self.say(f"briefs: sent {sent}")
        return sent

    def brief_handles(self, at: str | None = None) -> list[str]:
        """People whose email brief runs at `at` (None = all email briefs)."""
        default = self.cfg.cadence.morning_triage
        out = []
        for h, p in self.cfg.people.items():
            if not p.brief or p.brief.format is not BriefFormat.EMAIL:
                continue
            when = p.brief.when or default
            if at is None or when == at:
                out.append(h)
        return out

    async def end_of_day(self) -> int:
        today = self.today()
        graph = await DependencyGraph.build(self.adapter, self.cfg.project.repo)
        sent = 0
        for lead in self.cfg.project.leads:
            note = await end_of_day(self.cfg, self.adapter, graph, today, lead)
            if note and await self.notifier.notify(lead, note[0], note[1]):
                sent += 1
        self.say(f"end_of_day: sent {sent}")
        return sent

    async def weekly_digest(self) -> int:
        today = self.today()
        graph = await DependencyGraph.build(self.adapter, self.cfg.project.repo)
        sent = 0
        for lead in self.cfg.project.leads:
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
            if p.brief and p.brief.format is BriefFormat.EMAIL
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

    async def serve(self, host: str = "0.0.0.0", port: int = 8787) -> None:
        import uvicorn

        from agentic_pm.web import create_app

        handler = None
        if hasattr(self.adapter, "handle_webhook"):
            handler = self.adapter.handle_webhook
            self.adapter.subscribe(self.howto.on_event)
        app = create_app(
            self.guard,
            webhook_secret=self.env.get("AGENT_PM_GITHUB_WEBHOOK_SECRET"),
            on_github_webhook=handler,
        )
        tasks: list[Awaitable[Any]] = [
            uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info")).serve(),
            run_scheduler(self.jobs(), self.cfg.project.timezone),
        ]
        if self.env.get("AGENT_PM_IMAP_HOST"):
            tasks.append(self._poll_inbox_forever())
        await asyncio.gather(*tasks)

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
    notifier: Notifier = RecordingNotifier() if dry_run else EmailNotifier(cfg)
    signer = Signer(env["AGENT_PM_SIGNING_KEY"]) if env.get("AGENT_PM_SIGNING_KEY") else None
    guard = Guard(cfg, adapter, notifier, signer)
    provider = None
    if use_llm:
        from agentic_pm.llm import provider_from_settings

        provider = provider_from_settings(cfg.llm)
    return Runtime(
        cfg=cfg,
        adapter=adapter,
        notifier=notifier,
        guard=guard,
        router=Router(cfg, guard, notifier, provider),
        howto=HowToLoop(cfg, guard, notifier),
        provider=provider,
        env=env,
    )
