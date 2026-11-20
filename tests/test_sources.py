"""Several trackers in one team (ADR-0006): sources, seams, isolation.

The isolation tests try to leak on purpose: across a strict boundary nothing may
be resolved, shown to the wrong lead, or written.
"""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from agentic_pm.adapters import Edge, InMemoryTracker, Task, TaskRef, TaskStatus
from agentic_pm.adapters.base import AuditMeta, Channel, TaskPatch
from agentic_pm.adapters.multi import IsolationError, MultiTracker, source_env
from agentic_pm.adapters.registry import _registered, register
from agentic_pm.briefs import collect, render_text
from agentic_pm.chat import tags
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import ref_from_address, task_address
from agentic_pm.engine import DependencyGraph
from agentic_pm.engine.completeness import check_completeness
from agentic_pm.engine.seams import declared, parse_target, resolve

TODAY = date(2026, 11, 16)  # Monday


@pytest.fixture(autouse=True)
def memory_tracker() -> Iterator[None]:
    register("memory", lambda project, env: InMemoryTracker())
    yield
    _registered.pop("memory", None)


def person(**extra: Any) -> dict[str, Any]:
    return {"channels": {"email": "x@example.com"}, "archetype": "reader", **extra}


def config(eng: str = "open", ops: str = "open", **people: Any) -> TeamConfig:
    return TeamConfig.model_validate(
        {
            "project": {"leads": ["lea"]},
            "sources": {
                "eng": {
                    "tracker": "memory",
                    "project": "acme/app",
                    "isolation": eng,
                    "leads": ["erik"],
                },
                "ops": {
                    "tracker": "memory",
                    "project": "launch",
                    "isolation": ops,
                    "ticket_language": "de",
                    "leads": ["lea"],
                },
            },
            "people": people
            or {
                "lea": person(name="Lea", language="de", logins={"ops": "lea"}),
                "erik": person(name="Erik", logins={"eng": "erik"}),
                "dev": person(name="Dev", logins={"eng": "dev"}),
            },
        }
    )


def t(project: str, i: str, **kw: Any) -> Task:
    return Task(
        ref=TaskRef(tracker="memory", project=project, id=i),
        title=kw.pop("title", f"{project} task {i}"),
        status=kw.pop("status", TaskStatus.OPEN),
        **kw,
    )


BLOCK = "Campaign\n\n```agent-pm\nwaits_for: eng:milestone/v2.0\n```\n"


def world(cfg: TeamConfig, *, due_ops: date, eng_due: list[date | None]) -> MultiTracker:
    eng = InMemoryTracker(
        [
            t("acme/app", "30", status=TaskStatus.DONE, milestone="v2.0", assignees=["dev"]),
            *[
                t("acme/app", str(31 + n), milestone="v2.0", assignees=["dev"], due=d)
                for n, d in enumerate(eng_due)
            ],
            t("acme/app", "90", title="Unrelated refactor", assignees=["dev"]),
        ]
    )
    ops = InMemoryTracker(
        [
            t(
                "launch",
                "57",
                title="Launch campaign",
                assignees=["lea"],
                due=due_ops,
                description=BLOCK,
            )
        ]
    )
    return MultiTracker(cfg, {"eng": eng, "ops": ops})


# ------------------------------------------------------------------ config


def test_project_shorthand_and_sources_are_exclusive() -> None:
    cfg = config()
    assert cfg.multi and cfg.scope == "*" and cfg.sources["eng"].isolation == "open"
    with pytest.raises(ValidationError, match=r"either project\.tracker"):
        TeamConfig.model_validate(
            {
                "project": {"tracker": "github", "repo": "o/r", "leads": ["a"]},
                "sources": {"x": {"tracker": "github", "project": "o/r"}},
                "people": {"a": {}},
            }
        )
    with pytest.raises(ValidationError, match="required"):
        TeamConfig.model_validate({"project": {"leads": ["a"]}, "people": {"a": {}}})
    with pytest.raises(ValidationError, match="is not a source"):
        config(a=person(logins={"nope": "a"}))


def test_strict_is_the_default_and_membership_follows_logins() -> None:
    cfg = TeamConfig.model_validate(
        {
            "project": {"leads": ["me"]},
            "sources": {
                "a": {"tracker": "memory", "project": "a"},
                "b": {"tracker": "memory", "project": "b", "isolation": "open"},
            },
            "people": {"me": {}, "helper": {}, "anna": {"logins": {"a": "anna"}}},
        }
    )
    assert cfg.sources["a"].isolation == "strict"
    assert cfg.belongs("me", "a") and cfg.belongs("me", "b")  # lead of both
    assert not cfg.belongs("helper", "a") and cfg.belongs("helper", "b")  # strict needs logins
    assert cfg.belongs("anna", "a") and not cfg.belongs("anna", "b")
    assert cfg.assigned("anna", ["ANNA"], "a") and not cfg.assigned("anna", ["anna"], "b")


def test_per_source_credentials() -> None:
    cfg = config()
    env = source_env(cfg, "eng", {"AGENT_PM_ENG_TOKEN": "e", "GITHUB_TOKEN": "shared"})
    assert env["GITHUB_TOKEN"] == "e" and env["AGENT_PM_GITHUB_TOKEN"] == "e"
    assert source_env(cfg, "ops", {"GITHUB_TOKEN": "shared"})["GITHUB_TOKEN"] == "shared"


# --------------------------------------------------------------- reading


async def test_union_tags_every_reference_with_its_source() -> None:
    cfg = config()
    multi = world(cfg, due_ops=TODAY + timedelta(days=10), eng_due=[TODAY])
    graph = await DependencyGraph.build(multi, cfg.scope)
    labels = sorted(task.ref.label for task in graph.tasks.values())
    assert labels == ["eng#31", "eng#90", "ops#57"]
    got = await multi.get_task(cfg.ref("57", "ops"))  # type: ignore[arg-type]
    assert got.ref.source == "ops" and got.title == "Launch campaign"


async def test_cross_source_link_is_followed_only_between_open_sources() -> None:
    a = t("acme/app", "1", due=TODAY + timedelta(days=5), estimate_hours=16)
    b = t("launch", "2", due=TODAY + timedelta(days=1))
    link = Edge(source=b.ref, target=a.ref)
    for isolation, followed in (("open", True), ("strict", False)):
        cfg = config(eng=isolation)
        multi = MultiTracker(
            cfg, {"eng": InMemoryTracker([a], [link]), "ops": InMemoryTracker([b])}
        )
        graph = await DependencyGraph.build(multi, cfg.scope)
        assert bool(graph.blockers(a.ref.model_copy(update={"source": "eng"}))) is followed
        codes = [w.code for w in (graph.coverage.warnings if graph.coverage else [])]
        assert ("ISOLATION_BOUNDARY_BLOCKED" in codes) is not followed


# ------------------------------------------------------------------ seams


def test_seam_targets_parse() -> None:
    assert parse_target("eng:milestone/v2.0").text == "eng:milestone/v2.0"  # type: ignore[union-attr]
    assert parse_target("eng#142").kind == "item"  # type: ignore[union-attr]
    assert parse_target("eng:label/launch").kind == "label"  # type: ignore[union-attr]
    assert parse_target("not a seam") is None
    task = t("launch", "1", description=BLOCK, waits_for=["eng#5"])
    assert declared(task) == ["eng#5", "eng:milestone/v2.0"]
    broken = t("launch", "2", description="```agent-pm\nwaits_for: [unclosed\n```")
    assert declared(broken) == []


async def test_rollup_forecast_and_buffer() -> None:
    cfg = config()
    multi = world(
        cfg,
        due_ops=TODAY + timedelta(days=10),
        eng_due=[TODAY + timedelta(days=4), TODAY + timedelta(days=7)],
    )
    graph = await DependencyGraph.build(multi, cfg.scope)
    [seam] = await resolve(cfg, multi, graph, TODAY)
    r = seam.rollup
    assert seam.status == "ok" and r is not None
    assert (r.done, r.total, r.forecast) == (1, 3, TODAY + timedelta(days=7))
    assert seam.buffer == 3 and not seam.at_risk
    assert [x.ref.label for x in r.deciding] == ["eng#32"]


async def test_seam_lines_in_both_sides_briefs() -> None:
    cfg = config()
    multi = world(cfg, due_ops=TODAY + timedelta(days=3), eng_due=[TODAY + timedelta(days=5)])
    graph = await DependencyGraph.build(multi, cfg.scope)
    lea = render_text(await collect(cfg, "lea", multi, TODAY, graph))
    assert "🌉 Über Teamgrenzen" in lea
    assert "ops#57 Launch campaign wartet auf eng:milestone/v2.0: 1/2 erledigt" in lea
    assert "2 Tage nach seinem Termin" in lea and "Gefährdet" in lea
    assert "eng#31" not in lea and "eng task" not in lea  # no upstream items cross over
    dev = render_text(await collect(cfg, "dev", multi, TODAY, graph))
    assert "ops#57 Launch campaign on Thu 19 Nov 2026 waits for eng:milestone/v2.0" in dev
    assert "eng#31 decide it" in dev


async def test_delivering_side_hears_nothing_while_on_track() -> None:
    cfg = config()
    multi = world(cfg, due_ops=TODAY + timedelta(days=20), eng_due=[TODAY + timedelta(days=5)])
    graph = await DependencyGraph.build(multi, cfg.scope)
    assert "🌉" not in render_text(await collect(cfg, "dev", multi, TODAY, graph))
    assert "im Plan (15 Tage Puffer)" in render_text(await collect(cfg, "lea", multi, TODAY, graph))


async def test_undated_items_give_no_forecast_and_never_hide_in_the_backlog() -> None:
    cfg = config(
        dev=person(logins={"eng": "dev"}),
        lea=person(language="de", logins={"ops": "lea"}),
        erik=person(logins={"eng": "erik"}),
    )
    eng = InMemoryTracker([t("acme/app", "40", milestone="v2.0")])  # no owner, no date
    ops = InMemoryTracker(
        [
            t(
                "launch",
                "57",
                title="Launch campaign",
                assignees=["lea"],
                due=TODAY + timedelta(days=9),
                description=BLOCK,
            )
        ]
    )
    multi = MultiTracker(cfg, {"eng": eng, "ops": ops})
    graph = await DependencyGraph.build(multi, cfg.scope)
    [seam] = await resolve(cfg, multi, graph, TODAY)
    assert seam.rollup and seam.rollup.forecast is None and seam.at_risk
    report = check_completeness(cfg, graph)
    assert report.backlog == 0  # another team waits on it
    gap = next(g for g in report.gaps if g.task.ref.label == "eng#40")
    assert gap.code == "MISSING_OWNER" and gap.waiting == 1 and gap.recipients == ["erik"]


async def test_strict_seam_is_blocked_and_reported_to_the_waiting_lead() -> None:
    cfg = config(eng="strict")
    multi = world(cfg, due_ops=TODAY + timedelta(days=3), eng_due=[TODAY + timedelta(days=5)])
    graph = await DependencyGraph.build(multi, cfg.scope)
    [seam] = await resolve(cfg, multi, graph, TODAY)
    assert seam.status == "blocked" and seam.rollup is None
    lea = render_text(await collect(cfg, "lea", multi, TODAY, graph))
    assert "ops#57 → eng:milestone/v2.0" in lea and "abgeschottet" in lea
    assert "1/2" not in lea and "eng#3" not in lea
    erik = render_text(await collect(cfg, "erik", multi, TODAY, graph))
    assert "Launch campaign" not in erik and "ops#57" not in erik


async def test_seam_suggestion_from_text() -> None:
    cfg = config()
    ops = InMemoryTracker(
        [
            t(
                "launch",
                "58",
                assignees=["lea"],
                due=TODAY + timedelta(days=9),
                description="Blocked until eng:milestone/v2.0 ships",
            )
        ]
    )
    multi = MultiTracker(cfg, {"eng": InMemoryTracker(), "ops": ops})
    graph = await DependencyGraph.build(multi, cfg.scope)
    gaps = check_completeness(cfg, graph).gaps
    assert [(g.code, g.params) for g in gaps] == [
        ("SEAM_SUGGESTED", {"target": "eng:milestone/v2.0"})
    ]
    strict = config(eng="strict")
    graph = await DependencyGraph.build(
        MultiTracker(strict, {"eng": InMemoryTracker(), "ops": ops}), "*"
    )
    assert check_completeness(strict, graph).gaps == []  # it could never be resolved


# ------------------------------------------------------- people and leads


def freelancer() -> TeamConfig:
    return TeamConfig.model_validate(
        {
            "project": {"leads": ["me"]},
            "sources": {
                "acme": {"tracker": "memory", "project": "acme"},
                "beta": {"tracker": "memory", "project": "beta", "leads": ["bob"]},
            },
            "people": {
                "me": person(logins={"acme": "me", "beta": "me"}),
                "bob": person(logins={"beta": "bob"}),
            },
        }
    )


async def test_same_day_collision_names_tasks_and_date_only_privately() -> None:
    cfg = freelancer()
    day = TODAY + timedelta(days=3)
    multi = MultiTracker(
        cfg,
        {
            "acme": InMemoryTracker(
                [t("acme", "14", title="Review", assignees=["me"], due=day, estimate_hours=2)]
            ),
            "beta": InMemoryTracker(
                [t("beta", "T-04", title="Launch", assignees=["me"], due=day, estimate_hours=2)]
            ),
        },
    )
    graph = await DependencyGraph.build(multi, cfg.scope)
    mine = render_text(await collect(cfg, "me", multi, TODAY, graph))
    assert "acme#14 Review and beta#T-04 Launch are due on the same day, Thu 19 Nov 2026." in mine
    bob = render_text(await collect(cfg, "bob", multi, TODAY, graph))  # lead of beta only
    assert "acme" not in bob and "Review" not in bob


async def test_lead_of_one_client_sees_nothing_of_the_other() -> None:
    cfg = freelancer()
    multi = MultiTracker(
        cfg,
        {
            "acme": InMemoryTracker(
                [t("acme", "1", title="Acme secret roadmap", labels=["blocker"])]  # unowned
            ),
            "beta": InMemoryTracker([t("beta", "2", title="Beta thing", due=TODAY)]),
        },
    )
    graph = await DependencyGraph.build(multi, cfg.scope)
    bob = render_text(await collect(cfg, "bob", multi, TODAY, graph))
    assert "Acme" not in bob and "acme#" not in bob
    me = render_text(await collect(cfg, "me", multi, TODAY, graph))
    assert "acme#1 Acme secret roadmap" in me


# ----------------------------------------------------------------- writes


async def test_write_guard_refuses_leaks() -> None:
    cfg = freelancer()
    acme = InMemoryTracker([t("acme", "1", title="Acme secret roadmap")])
    beta = InMemoryTracker([t("beta", "2", title="Beta launch plan")])
    multi = MultiTracker(cfg, {"acme": acme, "beta": beta})
    await DependencyGraph.build(multi, cfg.scope)  # learns the titles
    ref = cfg.ref("2", "beta")
    assert ref is not None
    ok = AuditMeta(actor="me", channel=Channel.SYSTEM, reason="x", source="beta")
    await multi.add_comment(ref, "All good here.", ok)  # allowed
    for text, meta in [
        ("fine", ok.model_copy(update={"source": "acme"})),  # acts for the wrong source
        ("fine", ok.model_copy(update={"source": None})),  # acts for no source
        ("Same as acme#1, by the way", ok),  # names the other client
        ("Like the acme secret roadmap!", ok),  # quotes its title
    ]:
        with pytest.raises(IsolationError):
            await multi.add_comment(ref, text, meta)
    with pytest.raises(IsolationError):
        await multi.update_fields(ref, TaskPatch(add_labels=["acme:urgent"]), ok)
    comments = (await beta.get_task(ref.bare())).comments
    assert len(comments) == 1 and "acme" not in comments[0].body.lower()


async def test_open_target_may_mention_open_source_but_not_strict() -> None:
    cfg = TeamConfig.model_validate(
        {
            "project": {"leads": ["me"]},
            "sources": {
                "eng": {"tracker": "memory", "project": "e", "isolation": "open"},
                "ops": {"tracker": "memory", "project": "o", "isolation": "open"},
                "client": {"tracker": "memory", "project": "c"},
            },
            "people": {"me": {}},
        }
    )
    ops = InMemoryTracker([t("o", "1")])
    multi = MultiTracker(cfg, {"eng": InMemoryTracker(), "ops": ops, "client": InMemoryTracker()})
    ref = cfg.ref("1", "ops")
    assert ref is not None
    meta = AuditMeta(actor="me", channel=Channel.SYSTEM, reason="x", source="ops")
    await multi.add_comment(ref, "eng:milestone/v2.0 · 14/18 done · forecast 2026-11-28", meta)
    with pytest.raises(IsolationError):
        await multi.add_comment(ref, "see client#3", meta)


# ------------------------------------------------- replies find their source


def test_chat_tags_and_email_addresses_carry_the_source() -> None:
    key = "k" * 32
    tag = tags.proposal(key, "12", "status", "done", "eng")
    line = tag.render()
    assert line.startswith("— eng#12 · set status done · ")
    parsed = tags.parse(f"hello\n{line}")
    assert parsed is not None and parsed.source == "eng" and tags.verified_patch(parsed, key)
    forged = parsed.model_copy(update={"source": "ops"})  # same id, other source
    assert tags.verified_patch(forged, key) is None
    assert tags.proposal(key, "12", "status", "done").render().startswith("— #12 ·")

    cfg = config().model_copy(
        update={"project": config().project.model_copy(update={"agent_email": "pm@acme.com"})}
    )
    ref = cfg.ref("57", "ops")
    assert ref is not None
    address = task_address("pm@acme.com", ref)
    assert address == "pm+ops.57@acme.com"
    assert ref_from_address(address, cfg) == ref
    assert ref_from_address("pm+57@acme.com", cfg) is None  # which source? don't guess
