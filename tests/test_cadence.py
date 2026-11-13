from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from agentic_pm.adapters import InMemoryTracker, Task, TaskRef, TaskStatus
from agentic_pm.briefs.digest import end_of_day, weekly_digest
from agentic_pm.cadence import Job, next_run, run_scheduler
from agentic_pm.config import load_team_config
from agentic_pm.config.team import TeamConfig
from agentic_pm.demo import demo_tracker
from agentic_pm.engine import DependencyGraph
from agentic_pm.runtime import build_runtime

VIE = ZoneInfo("Europe/Vienna")
FRI = datetime(2026, 11, 13, 10, 0, tzinfo=VIE)  # a Friday
EXAMPLE = Path(__file__).parents[1] / ".agent-pm" / "team.example.yaml"


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("08:30", datetime(2026, 11, 16, 8, 30, tzinfo=VIE)),  # weekdays only -> Monday
        ("daily 08:30", datetime(2026, 11, 14, 8, 30, tzinfo=VIE)),  # Saturday
        ("10:30", datetime(2026, 11, 13, 10, 30, tzinfo=VIE)),  # later today
        ("Fri 15:00", datetime(2026, 11, 13, 15, 0, tzinfo=VIE)),
        ("Fri 09:00", datetime(2026, 11, 20, 9, 0, tzinfo=VIE)),  # already passed today
        ("last_friday 16:00", datetime(2026, 11, 27, 16, 0, tzinfo=VIE)),
        ("first_monday", datetime(2026, 12, 7, 9, 0, tzinfo=VIE)),
    ],
)
def test_next_run(spec: str, expected: datetime) -> None:
    assert next_run(spec, FRI) == expected


@pytest.mark.parametrize("bad", ["8:30", "Friday 15:00", "last_fri", "every day", "25:00"])
def test_invalid_specs(bad: str) -> None:
    with pytest.raises(ValueError):
        next_run(bad, FRI)


async def test_scheduler_runs_jobs_in_order_and_survives_failures() -> None:
    now = [FRI]
    ran: list[str] = []

    async def sleep(seconds: float) -> None:
        now[0] += timedelta(seconds=seconds)

    def job(name: str, spec: str, fail: bool = False) -> Job:
        async def run(_: datetime) -> None:
            ran.append(name)
            if fail:
                raise RuntimeError("boom")

        return Job(name, spec, run)

    runs = await run_scheduler(
        [job("digest", "Fri 15:00", fail=True), job("brief", "10:30")],
        "Europe/Vienna",
        now=lambda: now[0],
        sleep=sleep,
        max_runs=3,
    )
    assert runs == 3 and ran == ["brief", "digest", "brief"]
    assert now[0] == datetime(2026, 11, 16, 10, 30, tzinfo=VIE)


def test_brief_needs_a_time_somewhere() -> None:
    data: dict[str, Any] = {
        "project": {"tracker": "github", "repo": "o/r", "leads": ["a"]},
        "people": {
            "a": {
                "role": "x",
                "archetype": "reader",
                "channels": {"email": "a@x.io"},
                "brief": {"format": "email"},
            }
        },
    }
    with pytest.raises(ValidationError, match=r"cadence\.morning_triage is not set"):
        TeamConfig.model_validate(data)
    data["cadence"] = {"morning_triage": "08:30", "weekly_digest": "Fri 15:00"}
    assert TeamConfig.model_validate(data).cadence.weekly_digest == "Fri 15:00"


def ref(i: int) -> TaskRef:
    return TaskRef(tracker="memory", project="your-org/your-repo", id=str(i))


async def test_end_of_day_only_when_needed() -> None:
    cfg = load_team_config(EXAMPLE)
    today = date(2026, 11, 13)
    quiet = InMemoryTracker(
        [Task(ref=ref(1), title="A", status=TaskStatus.OPEN, assignees=["sam"])]
    )
    g = await DependencyGraph.build(quiet, cfg.project.repo)
    assert await end_of_day(cfg, quiet, g, today, "alex") is None  # no noise
    busy = InMemoryTracker(
        [
            Task(
                ref=ref(1), title="Unowned", status=TaskStatus.OPEN, due=today - timedelta(days=1)
            ),
            Task(
                ref=ref(2),
                title="Done today",
                status=TaskStatus.DONE,
                updated_at=datetime(2026, 11, 13, 9, tzinfo=UTC),
            ),
        ]
    )
    g = await DependencyGraph.build(busy, cfg.project.repo)
    note = await end_of_day(cfg, busy, g, today, "alex")
    assert note is not None
    subject, text = note
    assert subject.startswith("🌙 End of day") and "#1 Unowned" in text and "#2 Done today" in text


async def test_weekly_digest_demo() -> None:
    cfg = load_team_config(EXAMPLE)
    today = date(2026, 11, 13)
    t = demo_tracker(cfg.project.repo, today)
    g = await DependencyGraph.build(t, cfg.project.repo)
    subject, text = await weekly_digest(cfg, t, g, today, "alex")
    assert subject == "📊 Weekly digest: 0 done, 2 at risk"
    assert "🔁 Circular dependencies" in text and "#17 → #18" in text and "Kim: #13, #19" in text


async def test_runtime_jobs_and_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_team_config(EXAMPLE)
    cfg = cfg.model_copy(
        update={
            "cadence": cfg.cadence.model_copy(
                update={"weekly_digest": "Fri 15:00", "end_of_day": "17:30"}
            )
        }
    )
    rt = build_runtime(
        cfg, demo_tracker(cfg.project.repo, date.today()), env={}, dry_run=True, use_llm=False
    )
    names = [j.name for j in rt.jobs()]
    assert names == ["briefs 08:00", "end_of_day", "weekly_digest"]
    assert await rt.run_once("briefs") == 1  # only alex has an email brief
    assert await rt.run_once("monthly_health_check") == 0
    with pytest.raises(ValueError):
        await rt.run_once("nonsense")
