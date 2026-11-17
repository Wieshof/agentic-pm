"""Morning brief: what one person should know today, from live tracker data.

Read-only. Facts are computed deterministically; an optional local-LLM summary
(see `summary.py`) only rephrases them and is dropped if it invents anything.
"""

from __future__ import annotations

import html
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage

from pydantic import BaseModel

from agentic_pm import i18n
from agentic_pm.adapters.base import CLOSED_STATUSES, Task, TaskStatus, TrackerAdapter
from agentic_pm.adapters.coverage import CoverageReport
from agentic_pm.briefs.coverage_text import render_coverage
from agentic_pm.briefs.gap_text import render_gaps, render_readiness, render_stalled
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine.capacity import Collision, find_collisions
from agentic_pm.engine.completeness import CompletenessReport, Gap, check_completeness
from agentic_pm.engine.dependencies import DependencyGraph, Risk
from agentic_pm.engine.followup import FollowUp
from agentic_pm.engine.followup import plan as plan_followups
from agentic_pm.engine.triangulation import Conflict, comment_conflicts


def _lower(values: list[str]) -> set[str]:
    return {v.lower() for v in values}


class Blocked(BaseModel):
    task: Task
    by: list[str]


class BriefData(BaseModel):
    handle: str
    name: str
    language: str
    today: date
    is_lead: bool
    overdue: list[Task] = []
    due_soon: list[Task] = []
    in_progress: list[Task] = []
    blocked: list[Blocked] = []
    my_risks: list[Risk] = []
    waiting_on_me: list[Risk] = []
    team_risks: list[Risk] = []
    cycles: list[list[str]] = []
    open_count: int = 0
    limitations: list[str] = []
    coverage: CoverageReport | None = None
    gaps: list[Gap] = []
    gap_limit: int = 5
    readiness: CompletenessReport | None = None  # leads only, team level
    my_collisions: list[Collision] = []
    team_collisions: list[Collision] = []
    conflicts: list[Conflict] = []  # my tasks whose latest comment claims another status
    followups: list[FollowUp] = []  # my open questions with today's follow-up plan
    stalled: list[FollowUp] = []  # leads: urgent questions long unanswered (task-centric)
    names: dict[str, str] = {}

    @property
    def attention_count(self) -> int:
        return (
            len(self.overdue)
            + len(self.my_risks)
            + len(self.waiting_on_me)
            + len(self.my_collisions)
            + (1 if self.coverage else 0)
        )

    @property
    def is_quiet(self) -> bool:
        return not (
            self.overdue
            or self.due_soon
            or self.blocked
            or self.my_risks
            or self.waiting_on_me
            or self.team_risks
            or self.cycles
            or self.my_collisions
            or self.team_collisions
            or self.coverage
            or self.gaps
            or self.conflicts
            or self.stalled
        )


async def collect(
    cfg: TeamConfig,
    handle: str,
    adapter: TrackerAdapter,
    today: date,
    graph: DependencyGraph | None = None,
) -> BriefData:
    person = cfg.people[handle]
    login = person.login(handle).lower()  # sheets often say "Sam", trackers "sam"
    if graph is None:
        graph = await DependencyGraph.build(adapter, cfg.project.repo)
    mine = sorted(
        (t for t in graph.tasks.values() if login in _lower(t.assignees)),
        key=lambda t: (t.due or date.max, t.ref.id),
    )
    horizon = today + timedelta(days=cfg.project.brief_horizon_days)
    risks = graph.risks(today)
    collisions = find_collisions(graph, today)
    completeness = check_completeness(cfg, graph)
    is_lead = handle in cfg.project.leads
    followups = plan_followups(cfg, completeness, graph, today, writes=adapter.capabilities.writes)
    mine_fu = [f for f in followups if handle in f.gap.recipients]
    my_risks = [r for r in risks if login in _lower(r.task.assignees)]
    at_risk_ids = {str(r.task.ref) for r in my_risks}
    # Each task appears once, in its most important section.
    blocked = [
        Blocked(task=t, by=[f"#{b.ref.id}" for b in graph.blockers(t.ref)])
        for t in mine
        if (t.status is TaskStatus.BLOCKED or graph.blockers(t.ref))
        and str(t.ref) not in at_risk_ids
    ]
    return BriefData(
        handle=handle,
        name=person.name or handle.capitalize(),
        language=person.language,
        today=today,
        is_lead=is_lead,
        overdue=[t for t in mine if t.due and t.due < today],
        due_soon=[
            t for t in mine if t.due and today <= t.due <= horizon and str(t.ref) not in at_risk_ids
        ],
        in_progress=[t for t in mine if t.status is TaskStatus.IN_PROGRESS],
        blocked=blocked,
        my_risks=my_risks,
        waiting_on_me=[
            r
            for r in risks
            if login in _lower(r.blocker.assignees) and login not in _lower(r.task.assignees)
        ],
        team_risks=[r for r in risks if str(r.task.ref) not in at_risk_ids] if is_lead else [],
        cycles=[[f"#{r.id}" for r in c] for c in graph.cycles()] if is_lead else [],
        open_count=len(mine),
        limitations=graph.limitations() if is_lead else [],
        my_collisions=[c for c in collisions if c.login == login],
        team_collisions=[c for c in collisions if c.login != login] if is_lead else [],
        names={p.login(h).lower(): p.name or h.capitalize() for h, p in cfg.people.items()},
        gaps=[f.gap for f in mine_fu if f.due_today],
        followups=mine_fu,
        stalled=[f for f in followups if f.stalled] if is_lead else [],
        conflicts=[
            c
            for c in comment_conflicts(mine, datetime.now(UTC))
            if c.task.status not in CLOSED_STATUSES
        ],
        gap_limit=cfg.completeness.max_per_brief,
        readiness=completeness if is_lead and completeness.gaps else None,
        coverage=(
            graph.coverage
            if is_lead and graph.coverage is not None and not graph.coverage.is_complete
            else None
        ),
    )


# ------------------------------------------------------------------ texts


def base_language(lang: str) -> str:
    """The language the brief is written in: the person's, or English if it has no texts."""
    return i18n.base_language(lang)


def texts(lang: str) -> i18n.Texts:
    return i18n.texts("brief", lang)


def plural(lang: str, word: str, n: int) -> str:
    return i18n.plural(lang, word, n)


def _label(t: Task) -> str:
    return f"#{t.ref.id} {t.title}"


def _sections(d: BriefData) -> list[tuple[str, list[str]]]:
    tr = texts(d.language)
    lang = d.language

    def due(t: Task) -> str:
        return tr["due"].format(d=t.due.isoformat()) if t.due else tr["no_due"]

    def risk(r: Risk) -> str:
        return tr["risk"].format(
            task=_label(r.task),
            days=plural(lang, "days", r.days_late),
            blocker=_label(r.blocker),
            why=tr[f"why_{r.reason}"],
            d=r.proposed_due.isoformat(),
        )

    overdue = [
        f"{_label(t)} ({tr['days_over'].format(days=plural(lang, 'days', (d.today - t.due).days))})"
        for t in d.overdue
        if t.due
    ]
    waiting = [
        tr["waits"].format(
            who=", ".join(d.names.get(a.lower(), a) for a in r.task.assignees) or "?",
            blocker=_label(r.blocker),
            task=_label(r.task),
        )
        for r in d.waiting_on_me
    ]
    blocked = [
        tr["blocked_by"].format(task=_label(b.task), refs=", ".join(b.by))
        if b.by
        else _label(b.task)
        for b in d.blocked
    ]

    def collision(c: Collision, with_name: bool) -> str:
        labels = [_label(t) for t in c.tasks]
        joined = ", ".join(labels[:-1]) + f" {tr['and']} " + labels[-1]
        days_needed = max(1, round(c.needed_hours / 8))
        text = tr["collision"].format(
            tasks=joined,
            by=c.by.isoformat(),
            need=plural(lang, "days", days_needed),
            left=plural(lang, "workdays", int(c.available_hours // 8)),
        )
        if c.suggestion_id:
            text += tr["collision_move"].format(id=f"#{c.suggestion_id}")
        else:
            text += tr["collision_all_critical"]
        return f"{d.names.get(c.login.lower(), c.login)}: {text}" if with_name else text

    sections: list[tuple[str, list[str]]] = [
        (tr["overdue"], overdue),
        (tr["collisions"], [collision(c, False) for c in d.my_collisions]),
        (tr["waiting_on_me"], waiting),
        (tr["my_risks"], [risk(r) for r in d.my_risks]),
        (tr["due_soon"], [f"{_label(t)} ({due(t)})" for t in d.due_soon]),
        (tr["blocked"], blocked),
        (tr["team_risks"], [risk(r) for r in d.team_risks]),
        (tr["team_collisions"], [collision(c, True) for c in d.team_collisions]),
        (tr["cycles"], [" → ".join(c) for c in d.cycles]),
        (tr["limits"], [tr[f"limit_{x}"] for x in d.limitations]),
    ]
    if d.conflicts:
        sections.append(render_conflicts(d, lang))
    if d.gaps:
        sections.append(render_gaps(d.gaps, lang, d.gap_limit))
    if d.stalled:
        sections.append(render_stalled(d.stalled, lang))
    if d.readiness is not None:
        sections.append(render_readiness(d.readiness, lang))
    if d.coverage is not None:  # never present a partial picture as "all clear"
        heading, items = render_coverage(d.coverage, lang)
        sections.insert(0, (heading, items))
    return [(h, items) for h, items in sections if items]


def render_conflicts(d: BriefData, lang: str) -> tuple[str, list[str]]:
    from agentic_pm.messages import render, status_name

    items = [
        render(
            lang,
            "conflict_item",
            who=d.names.get((c.by or "").lower()) or c.by or render(lang, "someone"),
            evidence=c.claim.evidence,
            id=c.task.ref.id,
            title=c.task.title,
            status=status_name(c.task.status, lang),
            new=status_name(c.proposed, lang),
        )
        for c in d.conflicts
    ]
    return render(lang, "conflicts_heading"), items


def subject(d: BriefData) -> str:
    tr = texts(d.language)
    n = d.attention_count
    return (
        tr["subject_busy"].format(things=plural(d.language, "things", n))
        if n
        else tr["subject_calm"]
    )


def render_text(d: BriefData, summary: str | None = None) -> str:
    tr = texts(d.language)
    lines = [tr["hello"].format(name=d.name), ""]
    if summary:
        lines += [summary, ""]
    if d.is_quiet:
        lines += [tr["quiet"], ""]
    for heading, items in _sections(d):
        lines.append(heading)
        lines += [f"  • {i}" for i in items]
        lines.append("")
    lines.append(tr["footer"].format(tasks=plural(d.language, "tasks", d.open_count)))
    return "\n".join(lines)


def render_html(d: BriefData, summary: str | None = None) -> str:
    tr = texts(d.language)
    e = html.escape
    parts = [
        '<div style="font-family:system-ui,sans-serif;max-width:640px;line-height:1.5">',
        f"<h2>{e(tr['hello'].format(name=d.name))}</h2>",
    ]
    if summary:
        parts.append(
            f'<p style="background:#f4f7fb;padding:12px;border-radius:8px">'
            f"<strong>{e(tr['summary'])}:</strong> {e(summary)}</p>"
        )
    if d.is_quiet:
        parts.append(f"<p>{e(tr['quiet'])}</p>")
    for heading, items in _sections(d):
        parts.append(f"<h3>{e(heading)}</h3><ul>")
        parts += [f"<li>{e(i)}</li>" for i in items]
        parts.append("</ul>")
    footer = tr["footer"].format(tasks=plural(d.language, "tasks", d.open_count))
    parts.append(f'<p style="color:#666">{e(footer)}</p></div>')
    return "\n".join(parts)


def build_email(d: BriefData, to: str, sender: str, summary: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = " ".join(subject(d).split())  # titles may contain line breaks
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(render_text(d, summary))
    msg.add_alternative(render_html(d, summary), subtype="html")
    return msg
