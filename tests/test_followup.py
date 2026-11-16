"""Adaptive follow-up (#14): per question, stateless, never a score about a person."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from agentic_pm.adapters import Edge, InMemoryTracker, Task, TaskRef, TaskStatus
from agentic_pm.adapters.base import AuditMeta, Channel, Comment
from agentic_pm.audit import render_audit_footer
from agentic_pm.briefs import collect, render_text
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine import DependencyGraph
from agentic_pm.engine.completeness import check_completeness
from agentic_pm.engine.followup import FollowUp, plan, working_days
from agentic_pm.notify import RecordingNotifier
from agentic_pm.runtime import build_runtime

TODAY = date(2026, 11, 16)  # Monday
REPO = "acme/app"
KEY = "k" * 32


def cfg(sam_brief: str = "chat", **sam: Any) -> TeamConfig:
    return TeamConfig.model_validate(
        {
            "project": {
                "tracker": "github",
                "repo": REPO,
                "leads": ["alex"],
                "allow_writes": True,
            },
            "people": {
                "alex": {
                    "role": "lead",
                    "archetype": "reader",
                    "channels": {"email": "alex@acme.test"},
                    "brief": {"format": "email", "when": "08:00"},
                },
                "sam": {
                    "role": "dev",
                    "archetype": "writer",
                    "channels": {"signal": "+43 660 1111111", "email": "sam@acme.test"},
                    "brief": {"format": sam_brief, "when": "08:30"},
                    **sam,
                },
            },
        }
    )


def ref(i: str) -> TaskRef:
    return TaskRef(tracker="github", project=REPO, id=i)


def at(d: date) -> datetime:
    return datetime.combine(d, time(9), UTC)


def asked(code: str, d: date) -> Comment:
    meta = AuditMeta(actor="agent-pm", channel=Channel.SYSTEM, reason=f"followup:{code}")
    return Comment(
        author="agent-pm", body=f"🙋 asked\n\n{render_audit_footer(meta)}", created_at=at(d)
    )


def task(i: str, **kw: Any) -> Task:
    return Task(ref=ref(i), title=f"Task {i}", status=kw.pop("status", TaskStatus.OPEN), **kw)


def tracker(tasks: list[Task], edges: list[Edge] | None = None) -> InMemoryTracker:
    t = InMemoryTracker(tasks, edges or [])
    t.name = "github"
    return t


async def followups(
    tasks: list[Task], edges: list[Edge] | None = None, **kw: Any
) -> dict[str, FollowUp]:
    c = kw.pop("config", None) or cfg()
    g = await DependencyGraph.build(tracker(tasks, edges), REPO)
    out = plan(c, check_completeness(c, g), g, TODAY, writes=kw.pop("writes", True))
    return {f.key.split("|", 1)[0].rsplit("#", 1)[-1] + "|" + f.gap.code: f for f in out}


def test_working_days_skip_weekends() -> None:
    fri = date(2026, 11, 13)
    assert working_days(fri, TODAY) == 1  # Sat, Sun don't count
    assert working_days(TODAY, TODAY) == 0
    assert working_days(TODAY - timedelta(days=14), TODAY) == 10


async def test_first_ask_is_today() -> None:
    f = (await followups([task("1", assignees=["sam"])]))["1|MISSING_DUE"]
    assert (f.asked_on, f.ignored, f.due_today, f.urgent, f.switch) == (None, 0, True, False, False)


async def test_non_urgent_is_asked_weekly() -> None:
    ago = lambda days: TODAY - timedelta(days=days)  # noqa: E731
    f3 = await followups([task("1", assignees=["sam"], comments=[asked("MISSING_DUE", ago(3))])])
    assert not f3["1|MISSING_DUE"].due_today  # Thu → Mon: 2 working days, not today
    f7 = await followups([task("1", assignees=["sam"], comments=[asked("MISSING_DUE", ago(7))])])
    assert f7["1|MISSING_DUE"].ignored == 5 and f7["1|MISSING_DUE"].due_today


async def test_urgent_daily_then_other_channel_then_leads() -> None:
    def blocked(days_ago: int) -> list[Task]:
        return [
            task(
                "1",
                assignees=["sam"],
                status=TaskStatus.BLOCKED,
                due=TODAY + timedelta(days=30),
                comments=[asked("BLOCKED_WITHOUT_REASON", TODAY - timedelta(days=days_ago))],
            )
        ]

    f = (await followups(blocked(1)))["1|BLOCKED_WITHOUT_REASON"]
    assert f.urgent and f.due_today and not f.switch
    f = (await followups(blocked(3)))["1|BLOCKED_WITHOUT_REASON"]  # Fri → Mon = 1 working day
    assert f.ignored == 1
    f = (await followups(blocked(7)))["1|BLOCKED_WITHOUT_REASON"]
    assert f.ignored == 5 and f.switch and not f.stalled  # 3 nudges: try the next channel
    f = (await followups(blocked(9)))["1|BLOCKED_WITHOUT_REASON"]
    assert f.stalled  # 6 nudges: leads hear about the task


async def test_waiting_work_or_near_due_date_makes_it_urgent() -> None:
    c = cfg()
    c = c.model_copy(
        update={"completeness": c.completeness.model_copy(update={"require_estimate": True})}
    )
    soon = TODAY + timedelta(days=2)
    fs = await followups(
        [
            task("1", assignees=["sam"], due=TODAY + timedelta(days=60)),
            task("2", assignees=["sam"], due=TODAY + timedelta(days=60)),
            task("3", assignees=["sam"], due=soon),
            task("4", assignees=["sam"], due=TODAY + timedelta(days=60)),
        ],
        [Edge(source=ref("1"), target=ref("2"))],
        config=c,
    )
    assert fs["1|MISSING_ESTIMATE"].urgent  # #2 waits on it
    assert fs["3|MISSING_ESTIMATE"].urgent  # due soon
    assert not fs["4|MISSING_ESTIMATE"].urgent  # nothing depends on it, due far away


async def test_an_answer_restarts_the_count() -> None:
    old = TODAY - timedelta(days=10)
    reply = Comment(
        author="sam", body="Waiting for the client.", created_at=at(TODAY - timedelta(days=1))
    )
    f = await followups(
        [
            task(
                "1",
                assignees=["sam"],
                status=TaskStatus.BLOCKED,
                comments=[asked("BLOCKED_WITHOUT_REASON", old), reply],
            )
        ]
    )
    # a reason in a comment doesn't fill the gap (the description is empty), but Sam did answer
    assert "1|BLOCKED_WITHOUT_REASON" in f
    assert f["1|BLOCKED_WITHOUT_REASON"].ignored == 1 and not f["1|BLOCKED_WITHOUT_REASON"].switch


async def test_read_only_uses_last_update() -> None:
    updated = at(TODAY - timedelta(days=7))
    f = (await followups([task("1", assignees=["sam"], updated_at=updated)], writes=False))[
        "1|MISSING_DUE"
    ]
    assert f.asked_on == updated.date() and f.ignored == 5


# ------------------------------------------------------------- runtime


def runtime(t: InMemoryTracker, c: TeamConfig | None = None, dry_run: bool = True) -> Any:
    rt = build_runtime(
        c or cfg(), t, env={"AGENT_PM_SIGNING_KEY": KEY}, dry_run=dry_run, use_llm=False
    )
    rt.today = lambda: TODAY  # type: ignore[method-assign]
    return rt


async def test_urgent_questions_come_one_by_one_and_are_noted_once() -> None:
    t = tracker(
        [task("1", status=TaskStatus.BLOCKED, assignees=["sam"], due=TODAY + timedelta(days=2))]
    )
    rt = runtime(t, dry_run=False)
    rt.notifier = rt.guard.notifier = RecordingNotifier()
    await rt.briefs(["sam"])
    texts = [s.text for s in rt.notifier.sent]
    assert "What is it waiting for?" not in texts[0]  # not in the brief itself
    assert any(x.endswith("— #1") and "What is it waiting for?" in x for x in texts[1:])
    notes = [c.body for c in (await t.get_task(ref("1"))).comments]
    assert (
        len(notes) == 1
        and "🙋 Asked Sam" in notes[0]
        and "followup:BLOCKED_WITHOUT_REASON" in notes[0]
    )
    await rt.briefs(["sam"])  # next run, same day: the note isn't repeated
    assert len((await t.get_task(ref("1"))).comments) == 1


async def test_dry_run_writes_nothing() -> None:
    t = tracker([task("1", status=TaskStatus.BLOCKED, assignees=["sam"])])
    await runtime(t).briefs(["sam"])
    assert (await t.get_task(ref("1"))).comments == []


async def test_after_three_nudges_the_next_channel_is_tried() -> None:
    long_ago = TODAY - timedelta(days=7)
    t = tracker(
        [
            task(
                "1",
                status=TaskStatus.BLOCKED,
                assignees=["sam"],
                comments=[asked("BLOCKED_WITHOUT_REASON", long_ago)],
            )
        ]
    )
    rt = runtime(t)
    await rt.briefs(["sam"])
    sent = rt.notifier.sent
    assert sent[0].channel == "signal"  # the brief stays where it is
    email = [s for s in sent if s.channel == "email"]
    assert len(email) == 1 and "Signal" in email[0].text and "#1 Task 1" in email[0].text
    assert not any(s.channel == "signal" and "What is it waiting for?" in s.text for s in sent[1:])


async def test_interruptions_none_keeps_everything_in_the_brief() -> None:
    t = tracker([task("1", status=TaskStatus.BLOCKED, assignees=["sam"])])
    rt = runtime(t, cfg(interruptions="none"))
    await rt.briefs(["sam"])
    assert len(rt.notifier.sent) == 1 and "What is it waiting for?" in rt.notifier.sent[0].text


async def test_leads_see_stalled_tasks_not_people() -> None:
    t = tracker(
        [
            task(
                "1",
                status=TaskStatus.BLOCKED,
                assignees=["sam"],
                comments=[asked("BLOCKED_WITHOUT_REASON", TODAY - timedelta(days=9))],
            )
        ]
    )
    text = render_text(await collect(cfg(), "alex", t, TODAY))
    assert "⏰ Still waiting for an answer" in text
    assert "#1 Task 1: blocked, reason unknown, asked 6 working days ago" in text
    assert "Sam" not in text and "sam" not in text  # ADR-0004: about the task, not the person
    sam = render_text(await collect(cfg(), "sam", t, TODAY))
    assert "⏰" not in sam
