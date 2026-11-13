"""Lead rituals: end-of-day note and weekly digest (EN/DE, friendly, no noise).

Both are computed live from the tracker; nothing is remembered between runs.
`updated_at` from the tracker tells what happened today / this week.
"""

from __future__ import annotations

from datetime import date, timedelta

from agentic_pm.adapters.base import CLOSED_STATUSES, Task, TaskStatus, TrackerAdapter
from agentic_pm.briefs.morning import plural, texts
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine.capacity import find_collisions
from agentic_pm.engine.dependencies import DependencyGraph

T: dict[str, dict[str, str]] = {
    "en": {
        "eod_subject": "🌙 End of day: {n} thing(s) worth a look",
        "eod_hello": "Hi {name}, a short look at today before you log off:",
        "eod_closed": "✅ Finished today",
        "eod_unowned": "🙋 Overdue and nobody owns it",
        "eod_urgent": "⏰ Blocked by something overdue",
        "eod_collisions": "🧮 Deadlines that collide",
        "eod_bye": "That's it. Have a good evening! 🌙",
        "wk_subject": "📊 Weekly digest: {done} done, {risks} at risk",
        "wk_hello": "Hi {name}, here's the week at a glance:",
        "wk_closed": "✅ Done this week",
        "wk_next": "📅 Due next week",
        "wk_risks": "⚠️ At risk",
        "wk_collisions": "🧮 Deadlines that collide",
        "wk_cycles": "🔁 Circular dependencies",
        "wk_overdue": "⏰ Overdue: {n}",
        "wk_calm": "A calm week, nothing at risk. 🎉",
        "wk_bye": "Have a good weekend! Just reply if you'd like more detail on anything. 💬",
        "late": "{task}: {days} late, waiting for {blocker}",
        "collision": "{who}: {tasks} due by {by}",
    },
    "de": {
        "eod_subject": "🌙 Tagesabschluss: {n} Punkt(e) zum Anschauen",
        "eod_hello": "Hallo {name}, ein kurzer Blick auf heute, bevor Du Feierabend machst:",
        "eod_closed": "✅ Heute erledigt",
        "eod_unowned": "🙋 Überfällig und niemand ist zuständig",
        "eod_urgent": "⏰ Blockiert durch etwas Überfälliges",
        "eod_collisions": "🧮 Termine, die kollidieren",
        "eod_bye": "Das war's. Schönen Feierabend! 🌙",
        "wk_subject": "📊 Wochenrückblick: {done} erledigt, {risks} gefährdet",
        "wk_hello": "Hallo {name}, hier die Woche auf einen Blick:",
        "wk_closed": "✅ Diese Woche erledigt",
        "wk_next": "📅 Nächste Woche fällig",
        "wk_risks": "⚠️ Gefährdet",
        "wk_collisions": "🧮 Termine, die kollidieren",
        "wk_cycles": "🔁 Zirkuläre Abhängigkeiten",
        "wk_overdue": "⏰ Überfällig: {n}",
        "wk_calm": "Eine ruhige Woche, nichts ist gefährdet. 🎉",
        "wk_bye": "Schönes Wochenende! Antworte einfach, wenn Du zu etwas mehr wissen willst. 💬",
        "late": "{task}: {days} zu spät, wartet auf {blocker}",
        "collision": "{who}: {tasks} fällig bis {by}",
    },
}


def _t(lang: str) -> dict[str, str]:
    return T.get(lang.split("-")[0], T["en"])


def _label(t: Task) -> str:
    return f"#{t.ref.id} {t.title}"


def _block(heading: str, items: list[str]) -> list[str]:
    return [heading, *[f"  • {i}" for i in items], ""] if items else []


async def _closed_since(adapter: TrackerAdapter, project: str, since: date) -> list[Task]:
    tasks = await adapter.list_tasks(project, include_closed=True)
    return [
        t
        for t in tasks
        if t.status in CLOSED_STATUSES
        and t.status is TaskStatus.DONE
        and t.updated_at is not None
        and t.updated_at.date() >= since
    ]


async def end_of_day(
    cfg: TeamConfig, adapter: TrackerAdapter, graph: DependencyGraph, today: date, lead: str
) -> tuple[str, str] | None:
    """(subject, text) for one lead, or None if nothing needs attention (no noise)."""
    lang = cfg.language_of(lead)
    t = _t(lang)
    closed = await _closed_since(adapter, cfg.project.repo, today)
    unowned = [x for x in graph.tasks.values() if x.due and x.due < today and not x.assignees]
    urgent = [r for r in graph.risks(today) if r.reason == "blocker_overdue"]
    collisions = find_collisions(graph, today, horizon_days=3)
    attention = len(unowned) + len(urgent) + len(collisions)
    if attention == 0:
        return None
    names = {p.login(h).lower(): cfg.display_name(h) for h, p in cfg.people.items()}
    lines = [t["eod_hello"].format(name=cfg.display_name(lead)), ""]
    lines += _block(t["eod_unowned"], [_label(x) for x in unowned])
    lines += _block(
        t["eod_urgent"],
        [
            t["late"].format(
                task=_label(r.task),
                days=plural(lang, "days", r.days_late),
                blocker=_label(r.blocker),
            )
            for r in urgent
        ],
    )
    lines += _block(
        t["eod_collisions"],
        [
            t["collision"].format(
                who=names.get(c.login.lower(), c.login),
                tasks=", ".join(f"#{x.ref.id}" for x in c.tasks),
                by=c.by.isoformat(),
            )
            for c in collisions
        ],
    )
    lines += _block(t["eod_closed"], [_label(x) for x in closed])
    lines.append(t["eod_bye"])
    return t["eod_subject"].format(n=attention), "\n".join(lines)


async def weekly_digest(
    cfg: TeamConfig, adapter: TrackerAdapter, graph: DependencyGraph, today: date, lead: str
) -> tuple[str, str]:
    lang = cfg.language_of(lead)
    t = _t(lang)
    tr = texts(lang)
    closed = await _closed_since(adapter, cfg.project.repo, today - timedelta(days=7))
    upcoming = sorted(
        (x for x in graph.tasks.values() if x.due and today < x.due <= today + timedelta(days=7)),
        key=lambda x: (x.due or today, x.ref.id),
    )
    risks = graph.risks(today)
    collisions = find_collisions(graph, today)
    cycles = graph.cycles()
    overdue = [x for x in graph.tasks.values() if x.due and x.due < today]
    names = {p.login(h).lower(): cfg.display_name(h) for h, p in cfg.people.items()}

    lines = [t["wk_hello"].format(name=cfg.display_name(lead)), ""]
    lines += _block(t["wk_closed"], [_label(x) for x in closed])
    lines += _block(
        t["wk_risks"],
        [
            tr["risk"].format(
                task=_label(r.task),
                days=plural(lang, "days", r.days_late),
                blocker=_label(r.blocker),
                why=tr[f"why_{r.reason}"],
                d=r.proposed_due.isoformat(),
            )
            for r in risks
        ],
    )
    lines += _block(
        t["wk_collisions"],
        [
            t["collision"].format(
                who=names.get(c.login.lower(), c.login),
                tasks=", ".join(f"#{x.ref.id}" for x in c.tasks),
                by=c.by.isoformat(),
            )
            for c in collisions
        ],
    )
    lines += _block(t["wk_cycles"], [" → ".join(f"#{r.id}" for r in c) for c in cycles])
    lines += _block(
        t["wk_next"], [f"{_label(x)} ({x.due.isoformat() if x.due else ''})" for x in upcoming]
    )
    if overdue:
        lines += [t["wk_overdue"].format(n=len(overdue)), ""]
    if not risks and not collisions and not cycles:
        lines += [t["wk_calm"], ""]
    lines.append(t["wk_bye"])
    return t["wk_subject"].format(done=len(closed), risks=len(risks)), "\n".join(lines)
