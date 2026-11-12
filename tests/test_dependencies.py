from datetime import date, timedelta

from agentic_pm.adapters import Edge, InMemoryTracker, Task, TaskRef, TaskStatus
from agentic_pm.demo import demo_tracker
from agentic_pm.engine import DependencyGraph, duration_days

TODAY = date(2026, 11, 13)
P = "acme/app"


def ref(i: int) -> TaskRef:
    return TaskRef(tracker="memory", project=P, id=str(i))


def task(i: int, due: int | None, est: float | None = None, **kw: object) -> Task:
    return Task(
        ref=ref(i),
        title=f"T{i}",
        due=TODAY + timedelta(days=due) if due is not None else None,
        estimate_hours=est,
        **{"status": TaskStatus.OPEN, **kw},  # type: ignore[arg-type]
    )


def blocks(a: int, b: int) -> Edge:
    return Edge(source=ref(a), target=ref(b))


async def build(tasks: list[Task], edges: list[Edge]) -> DependencyGraph:
    return await DependencyGraph.build(InMemoryTracker(tasks, edges), P)


def test_duration_days() -> None:
    assert duration_days(task(1, 0)) == 1
    assert duration_days(task(1, 0, est=9)) == 2
    assert duration_days(task(1, 0, est=0.5)) == 1


async def test_no_risk_when_on_schedule() -> None:
    g = await build([task(1, 2), task(2, 5, est=8)], [blocks(1, 2)])
    assert g.risks(TODAY) == []


async def test_blocker_due_too_late() -> None:
    # 2 needs 2 days and is due in 3 days; its blocker finishes in 2 days -> 1 day late.
    g = await build([task(1, 2), task(2, 3, est=16)], [blocks(1, 2)])
    [r] = g.risks(TODAY)
    assert r.task.ref == ref(2) and r.blocker.ref == ref(1)
    assert r.days_late == 1 and r.reason == "blocker_due_too_late"
    assert r.proposed_due == TODAY + timedelta(days=4)


async def test_overdue_blocker_and_chain() -> None:
    g = await build(
        [task(1, -3), task(2, 0), task(3, 1, est=8)],
        [blocks(1, 2), blocks(2, 3)],
    )
    risks = {r.task.ref.id: r for r in g.risks(TODAY)}
    assert risks["2"].reason == "blocker_overdue"
    assert risks["3"].reason == "chain_delay"
    assert risks["3"].days_late == 1


async def test_closed_tasks_do_not_block() -> None:
    g = await build([task(1, -5, status=TaskStatus.DONE), task(2, 0)], [blocks(1, 2)])
    assert g.blockers(ref(2)) == [] and g.risks(TODAY) == []


async def test_cycles_detected_and_skipped() -> None:
    g = await build(
        [task(1, 1), task(2, 2), task(3, 3)], [blocks(1, 2), blocks(2, 1), blocks(2, 3)]
    )
    assert [[r.id for r in c] for c in g.cycles()] == [["1", "2"]]
    g.risks(TODAY)  # must not loop forever


async def test_impact_of_slip() -> None:
    g = await build(
        [task(1, 1), task(2, 3, est=8), task(3, 4, est=8)], [blocks(1, 2), blocks(2, 3)]
    )
    assert g.impact_of(ref(1), TODAY + timedelta(days=1), TODAY) == []
    hit = g.impact_of(ref(1), TODAY + timedelta(days=5), TODAY)
    assert {r.task.ref.id: r.days_late for r in hit} == {"2": 3, "3": 3}
    assert [t.ref.id for t in g.downstream(ref(1))] == ["2", "3"]


async def test_demo_data_has_expected_story() -> None:
    g = await DependencyGraph.build(demo_tracker(P, TODAY), P)
    assert {r.task.ref.id for r in g.risks(TODAY)} == {"13", "14"}
    assert len(g.cycles()) == 1
