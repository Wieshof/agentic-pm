from datetime import date, timedelta

from agentic_pm.adapters import Edge, InMemoryTracker, Task, TaskRef, TaskStatus
from agentic_pm.engine import DependencyGraph
from agentic_pm.engine.capacity import find_collisions, working_days

MON = date(2026, 11, 16)
P = "acme/app"


def ref(i: int) -> TaskRef:
    return TaskRef(tracker="memory", project=P, id=str(i))


def task(i: int, who: str, due_in: int, est: float | None) -> Task:
    return Task(
        ref=ref(i),
        title=f"T{i}",
        status=TaskStatus.OPEN,
        assignees=[who],
        due=MON + timedelta(days=due_in),
        estimate_hours=est,
    )


async def graph(tasks: list[Task], edges: list[Edge] | None = None) -> DependencyGraph:
    return await DependencyGraph.build(InMemoryTracker(tasks, edges or []), P)


def test_working_days() -> None:
    assert working_days(MON, MON + timedelta(days=6)) == 5  # Mon..Sun
    assert working_days(MON, MON - timedelta(days=1)) == 0


async def test_no_collision_when_it_fits() -> None:
    g = await graph([task(1, "sam", 1, 8), task(2, "sam", 4, 16)])
    assert find_collisions(g, MON) == []


async def test_collision_names_tasks_and_suggests_non_critical() -> None:
    # Tue: needs 8h+16h = 24h by Tue, only Mon+Tue = 16h available.
    g = await graph(
        [task(1, "sam", 1, 8), task(2, "sam", 1, 16), task(3, "kim", 5, 8)],
        [Edge(source=ref(1), target=ref(3))],  # kim waits for #1 -> critical
    )
    [c] = find_collisions(g, MON)
    assert c.login == "sam" and [t.ref.id for t in c.tasks] == ["1", "2"]
    assert c.needed_hours == 24 and c.available_hours == 16
    assert c.critical == ["1"] and c.suggestion_id == "2"


async def test_single_task_is_never_a_collision() -> None:
    g = await graph([task(1, "sam", 0, 40)])
    assert find_collisions(g, MON) == []


async def test_outcome_has_no_people_scores() -> None:
    g = await graph([task(1, "sam", 0, 8), task(2, "sam", 0, 8)])
    [c] = find_collisions(g, MON)
    assert set(c.model_dump()) == {
        "login",
        "tasks",
        "by",
        "needed_hours",
        "available_hours",
        "critical",
        "suggestion_id",
    }  # ADR-0004: task-centric, no utilisation or history fields
