"""Morning brief: what one person should know today, from live tracker data.

Read-only. Facts are computed deterministically; an optional local-LLM summary
(see `summary.py`) only rephrases them and is dropped if it invents anything.
"""

from __future__ import annotations

import html
from datetime import date, timedelta
from email.message import EmailMessage

from pydantic import BaseModel

from agentic_pm.adapters.base import Task, TaskStatus, TrackerAdapter
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine.dependencies import DependencyGraph, Risk


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
    names: dict[str, str] = {}

    @property
    def attention_count(self) -> int:
        return len(self.overdue) + len(self.my_risks) + len(self.waiting_on_me)

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
        )


async def collect(
    cfg: TeamConfig,
    handle: str,
    adapter: TrackerAdapter,
    today: date,
    graph: DependencyGraph | None = None,
) -> BriefData:
    person = cfg.people[handle]
    login = person.login(handle)
    if graph is None:
        graph = await DependencyGraph.build(adapter, cfg.project.repo)
    mine = sorted(
        (t for t in graph.tasks.values() if login in t.assignees),
        key=lambda t: (t.due or date.max, t.ref.id),
    )
    horizon = today + timedelta(days=cfg.project.brief_horizon_days)
    risks = graph.risks(today)
    is_lead = handle in cfg.project.leads
    my_risks = [r for r in risks if login in r.task.assignees]
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
            r for r in risks if login in r.blocker.assignees and login not in r.task.assignees
        ],
        team_risks=[r for r in risks if str(r.task.ref) not in at_risk_ids] if is_lead else [],
        cycles=[[f"#{r.id}" for r in c] for c in graph.cycles()] if is_lead else [],
        open_count=len(mine),
        limitations=graph.limitations() if is_lead else [],
        names={p.login(h): p.name or h.capitalize() for h, p in cfg.people.items()},
    )


# ------------------------------------------------------------------ texts

T: dict[str, dict[str, str]] = {
    "en": {
        "subject_busy": "☀️ Your morning brief: {things} today",
        "subject_calm": "☀️ Your morning brief: a calm day ahead",
        "hello": "Good morning, {name}!",
        "quiet": "Nothing urgent today. Enjoy the focus time! 🎯",
        "overdue": "⏰ Overdue",
        "due_soon": "📅 Due in the next days",
        "blocked": "🚧 Waiting on something",
        "my_risks": "⚠️ At risk because of a blocker",
        "waiting_on_me": "🤝 Others are waiting for you",
        "team_risks": "🧭 Team risks (you're a lead)",
        "cycles": "🔁 Circular dependencies to untangle",
        "due": "due {d}",
        "no_due": "no due date",
        "days_over": "{days} overdue",
        "risk": "{task} may slip {days} because {blocker} is {why}. Suggested new date: {d}",
        "why_blocker_overdue": "overdue",
        "why_blocker_due_too_late": "due too late",
        "why_chain_delay": "delayed further up the chain",
        "waits": "{who} needs {blocker} to start {task}",
        "blocked_by": "{task}, blocked by {refs}",
        "footer": "You have {tasks}. Just reply to this email if anything looks off. 💬",
        "summary": "In short",
        "limits": "🔍 Your tracker doesn't provide this, so I can't check it",
        "limit_dependencies": "dependencies (no risk warnings for blocked tasks)",
        "limit_due_dates": "due dates",
        "limit_estimates": "estimates (each task counts as 1 day)",
    },
    "de": {
        "subject_busy": "☀️ Dein Morgen-Briefing: {things} heute",
        "subject_calm": "☀️ Dein Morgen-Briefing: ein ruhiger Tag",
        "hello": "Guten Morgen, {name}!",
        "quiet": "Heute ist nichts dringend. Genieß die Fokuszeit! 🎯",
        "overdue": "⏰ Überfällig",
        "due_soon": "📅 In den nächsten Tagen fällig",
        "blocked": "🚧 Wartet auf etwas",
        "my_risks": "⚠️ Gefährdet durch einen Blocker",
        "waiting_on_me": "🤝 Andere warten auf Dich",
        "team_risks": "🧭 Team-Risiken (Du bist Lead)",
        "cycles": "🔁 Zirkuläre Abhängigkeiten zum Entwirren",
        "due": "fällig {d}",
        "no_due": "kein Termin",
        "days_over": "{days} überfällig",
        "risk": "{task} rutscht evtl. {days}, weil {blocker} {why} ist. Neuer Vorschlag: {d}",
        "why_blocker_overdue": "überfällig",
        "why_blocker_due_too_late": "zu spät fällig",
        "why_chain_delay": "weiter oben in der Kette verzögert",
        "waits": "{who} braucht {blocker}, um mit {task} zu starten",
        "blocked_by": "{task}, blockiert durch {refs}",
        "footer": "Du hast {tasks}. Antworte einfach auf diese Mail, wenn etwas nicht stimmt. 💬",
        "summary": "Kurz gesagt",
        "limits": "🔍 Dein Tracker liefert das nicht, deshalb kann ich es nicht prüfen",
        "limit_dependencies": "Abhängigkeiten (keine Risiko-Warnungen für blockierte Aufgaben)",
        "limit_due_dates": "Fälligkeiten",
        "limit_estimates": "Schätzungen (jede Aufgabe zählt als 1 Tag)",
    },
}

_PLURALS: dict[str, dict[str, tuple[str, str, str]]] = {
    "en": {
        "days": ("0 days", "1 day", "{n} days"),
        "things": ("nothing needs you", "1 thing needs you", "{n} things need you"),
        "tasks": ("no open tasks", "1 open task", "{n} open tasks"),
    },
    "de": {
        "days": ("0 Tage", "1 Tag", "{n} Tage"),
        "things": ("nichts braucht Dich", "1 Sache braucht Dich", "{n} Sachen brauchen Dich"),
        "tasks": ("keine offenen Aufgaben", "1 offene Aufgabe", "{n} offene Aufgaben"),
    },
}


def base_language(lang: str) -> str:
    """Brief templates exist for English and German; other languages fall back to English."""
    code = lang.split("-")[0]
    return code if code in T else "en"


def texts(lang: str) -> dict[str, str]:
    return T[base_language(lang)]


def plural(lang: str, word: str, n: int) -> str:
    zero, one, many = _PLURALS[base_language(lang)][word]
    return zero if n == 0 else one if n == 1 else many.format(n=n)


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
            who=", ".join(d.names.get(a, a) for a in r.task.assignees) or "?",
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
    sections: list[tuple[str, list[str]]] = [
        (tr["overdue"], overdue),
        (tr["waiting_on_me"], waiting),
        (tr["my_risks"], [risk(r) for r in d.my_risks]),
        (tr["due_soon"], [f"{_label(t)} ({due(t)})" for t in d.due_soon]),
        (tr["blocked"], blocked),
        (tr["team_risks"], [risk(r) for r in d.team_risks]),
        (tr["cycles"], [" → ".join(c) for c in d.cycles]),
        (tr["limits"], [tr[f"limit_{x}"] for x in d.limitations]),
    ]
    return [(h, items) for h, items in sections if items]


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
    msg["Subject"] = subject(d)
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(render_text(d, summary))
    msg.add_alternative(render_html(d, summary), subtype="html")
    return msg
