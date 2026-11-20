"""Data completeness: garbage in, garbage out, caught before the briefs.

A deterministic pre-flight check over the open tasks in the dependency graph:

Gaps (who gets them):
* MISSING_OWNER: appears in nobody's brief (triage, i.e. leads)
* OWNER_NOT_IN_TEAM: owner isn't in team.yaml, so gets no brief (triage)
* MISSING_DUE: left out of risk and collision checks (owner)
* IMPLICIT_DUE: no due date, but the text names one, "due 2026-11-25" (owner)
* MISSING_ESTIMATE: the schedule counts it as 1 day; off by default (owner)
* BLOCKED_WITHOUT_REASON: "blocked", no linked blocker, no explanation (owner)
* BLOCKER_DONE: "blocked", but everything it waited for is finished (owner)
* UNLINKED_DEPENDENCY: text says "waiting on #14", nothing linked (owner)
* SEAM_SUGGESTED: text names another source (eng#142, eng:milestone/v2.0) but
  doesn't declare `waits_for` (owner; several trackers only, ADR-0006)

Hints from free text are **suggestions only**: the text is untrusted, nothing
is ever changed automatically, and only the short matched phrase is quoted.
Gaps go to the person concerned; leads see unowned work and a team-level
readiness ratio, never per-person counts (ADR-0004).
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel

from agentic_pm import i18n
from agentic_pm.adapters.base import Task, TaskRef, TaskStatus
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine.dependencies import DependencyGraph

# Only things that look like task ids: #14, #P-7, T-08 / APP-12 (letters-digits),
# instance:T-08 (spreadsheet) or tracker:owner/repo#42. Dates ("after 2026-11-25")
# and plain words ("after review") never match.
_REF = (
    r"(?P<tracker>[a-z0-9_-]+):(?P<project>[\w./-]+)#(?P<qid>[A-Za-z0-9][\w-]*)"
    r"|(?P<inst>[a-z0-9_-]+):(?P<iid>[A-Za-z][A-Za-z0-9]*-\d+)"
    r"|#(?P<hid>[A-Za-z0-9](?:[\w-]*[A-Za-z0-9])?)"
    r"|(?P<key>\b[A-Z][A-Z0-9]*-\d+\b)"
)


@i18n.cached
def _hint_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    """'waiting on #14' / 'wartet auf #14' and 'due 2026-11-25' / 'fällig bis …', any language."""
    deps = i18n.alternation("dependency_words")
    hint = re.compile(rf"(?i:\b(?:{deps}))\s+(?:{_REF})")
    deadline = i18n.alternation("deadline_words")
    due = re.compile(
        rf"(?i:\b(?:{deadline})\b)"
        r"[\s:]+(?:[^\s\d]+\s+){0,2}?(?P<date>\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})"
    )
    return hint, due


EVIDENCE_MAX = 60
OWNER_CODES = frozenset({"MISSING_OWNER", "OWNER_NOT_IN_TEAM"})


class Gap(BaseModel):
    code: str
    task: Task
    recipients: list[str]  # team.yaml handles
    params: dict[str, str] = {}
    waiting: int = 0  # open tasks that wait on this task (linked or named in their text)
    urgent_label: str | None = None  # e.g. "blocker", "p0"

    @property
    def priority(self) -> tuple[int, int, int, date, str]:
        """'Who takes it?' first, then blockers, urgent labels and the nearest due date."""
        return (
            0 if self.code in OWNER_CODES else 1,
            -self.waiting,
            0 if self.urgent_label else 1,
            self.task.due or date.max,
            str(self.task.ref),
        )


class CompletenessReport(BaseModel):
    active: int  # planned open tasks that were checked
    ready: int
    gaps: list[Gap]
    backlog: int = 0  # open but not planned yet: not asked about (policy.backlog)

    @property
    def readiness(self) -> float:
        return 1.0 if self.active == 0 else round(self.ready / self.active, 3)

    def for_handle(self, handle: str) -> list[Gap]:
        return [g for g in self.gaps if handle in g.recipients]

    def counts(self) -> dict[str, int]:
        """Gap counts by kind (team level, no names)."""
        out: dict[str, int] = {}
        for g in self.gaps:
            out[g.code] = out.get(g.code, 0) + 1
        return out


def _evidence(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= EVIDENCE_MAX else flat[: EVIDENCE_MAX - 1] + "…"


def _parse_date(text: str) -> date | None:
    try:
        if "." in text:
            d, m, y = (int(x) for x in text.split("."))
            return date(y, m, d)
        return date.fromisoformat(text)
    except ValueError:
        return None


def due_hint(text: str) -> tuple[date, str] | None:
    m = _hint_patterns()[1].search(text)
    if not m:
        return None
    parsed = _parse_date(m.group("date"))
    return (parsed, _evidence(m.group(0))) if parsed else None


def dependency_hints(task: Task, text: str) -> list[tuple[TaskRef, str]]:
    """Task references named after 'waiting on' & co., resolved relative to `task`."""
    found: dict[str, tuple[TaskRef, str]] = {}
    for m in _hint_patterns()[0].finditer(text):
        here = task.ref
        if m.group("qid"):
            ref = TaskRef(tracker=m.group("tracker"), project=m.group("project"), id=m.group("qid"))
        elif m.group("iid"):
            if m.group("inst") != here.project:
                continue  # some other sheet: can't resolve safely
            ref = here.model_copy(update={"id": m.group("iid")})
        else:
            ref = here.model_copy(update={"id": m.group("hid") or m.group("key")})
        if ref != here:
            found.setdefault(str(ref), (ref, _evidence(m.group(0))))
    return list(found.values())


def _norm_label(label: str) -> str:
    """'Priority: High', 'priority/high', 'must-have', 'Must Have' all compare equal."""
    return re.sub(r"[\s_-]+", "", label.lower()).replace("/", ":").replace("=", ":")


def urgent_label(task: Task, extra: list[str] | tuple[str, ...] = ()) -> str | None:
    """The first label that marks the task as urgent ('blocker', 'P0', 'priority: high' …)."""
    wanted = {_norm_label(w) for w in (*i18n.words("urgent_labels"), *extra)}
    return next((label for label in task.labels if _norm_label(label) in wanted), None)


def waiting_on(graph: DependencyGraph) -> dict[str, list[Task]]:
    """For every task: the open tasks waiting on it, linked or named in their text.

    "Waiting on #204" in another ticket makes #204 a blocker even before anyone
    links the two, so it must never disappear into the backlog.
    """
    out: dict[str, dict[str, Task]] = {}
    for task in graph.tasks.values():
        if task.status in (TaskStatus.DONE, TaskStatus.CLOSED):
            continue
        for down in graph.downstream(task.ref):
            if down.status not in (TaskStatus.DONE, TaskStatus.CLOSED):
                out.setdefault(str(task.ref), {})[str(down.ref)] = down
        for ref, _ in dependency_hints(task, f"{task.title}\n{task.description or ''}"):
            if str(ref) in graph.tasks:
                out.setdefault(str(ref), {})[str(task.ref)] = task
    for key, waiters in graph.seam_waiters.items():  # another source waits on it (ADR-0006)
        for w in waiters:
            out.setdefault(key, {})[str(w.ref)] = w
    return {k: sorted(v.values(), key=lambda t: str(t.ref)) for k, v in out.items()}


def is_backlog(
    task: Task,
    graph: DependencyGraph,
    *,
    waiting: list[Task] | None = None,
    urgent: str | None = None,
) -> bool:
    """Not planned yet: nobody owns it, no date, not started, nothing depends on it.

    Every real tracker has many of these (ideas, roadmap items). Asking "who
    takes it?" about each of them every morning is noise, not help. But a task
    that something waits on, or that carries an urgent label, is never backlog.
    """
    return (
        not task.assignees
        and task.due is None
        and task.status is TaskStatus.OPEN
        and not waiting
        and urgent is None
        and not graph.blockers(task.ref)
        and not graph.done_blockers(task.ref)
        and not graph.downstream(task.ref)
    )


def _names(tasks: list[Task], limit: int = 2) -> str:
    shown = ", ".join(f"{t.ref.label} {t.title}" for t in tasks[:limit])
    return shown + (f" (+{len(tasks) - limit})" if len(tasks) > limit else "")


def check_completeness(cfg: TeamConfig, graph: DependencyGraph) -> CompletenessReport:
    policy = cfg.completeness
    caps = graph.capabilities
    check_due = policy.require_due and (caps is None or caps.due_dates != "none")
    check_estimate = policy.require_estimate and (caps is None or caps.estimates != "none")
    check_links = caps is None or caps.dependencies != "none"

    gaps: list[Gap] = []
    active = ready = backlog = 0
    waits = waiting_on(graph)
    for task in sorted(graph.tasks.values(), key=lambda t: str(t.ref)):
        if task.status in (TaskStatus.DONE, TaskStatus.CLOSED):
            continue
        waiting = waits.get(str(task.ref), [])
        urgent = urgent_label(task, policy.urgent_labels)
        if policy.backlog == "separate" and is_backlog(task, graph, waiting=waiting, urgent=urgent):
            backlog += 1
            continue
        active += 1
        mine: list[Gap] = []
        source = task.ref.source
        owners = [h for login in task.assignees if (h := cfg.handle_for_login(login, source))]
        strangers = [login for login in task.assignees if not cfg.handle_for_login(login, source)]
        triage = [h for h in policy.triage or cfg.leads_of(source) if cfg.belongs(h, source)]
        triage = triage or cfg.leads_of(source)
        to = owners or triage
        text = task.description or ""

        if policy.require_owner and not task.assignees:
            why = {"waiting": _names(waiting)} if waiting else {"label": urgent} if urgent else {}
            mine.append(Gap(code="MISSING_OWNER", task=task, recipients=triage, params=why))
        if strangers:
            mine.append(
                Gap(
                    code="OWNER_NOT_IN_TEAM",
                    task=task,
                    recipients=triage,
                    params={"owner": ", ".join(strangers)},
                )
            )
        reported = {
            w.code
            for w in (graph.coverage.warnings if graph.coverage else [])
            if w.task_id == task.ref.id
        }  # a value the source couldn't read is already reported there; don't ask twice
        if check_due and task.due is None and "INVALID_DUE_DATE" not in reported:
            hint = due_hint(f"{task.title}\n{text}")
            if hint:
                mine.append(
                    Gap(
                        code="IMPLICIT_DUE",
                        task=task,
                        recipients=to,
                        params={"date": hint[0].isoformat(), "evidence": hint[1]},
                    )
                )
            else:
                mine.append(Gap(code="MISSING_DUE", task=task, recipients=to))
        if check_estimate and task.estimate_hours is None and "INVALID_ESTIMATE" not in reported:
            mine.append(Gap(code="MISSING_ESTIMATE", task=task, recipients=to))
        if (
            policy.require_blocker_reason
            and task.status is TaskStatus.BLOCKED
            and not graph.blockers(task.ref)
        ):
            done = graph.done_blockers(task.ref)
            if done:
                mine.append(
                    Gap(
                        code="BLOCKER_DONE",
                        task=task,
                        recipients=to,
                        params={"done": ", ".join(t.ref.label for t in done)},
                    )
                )
            elif not text.strip():
                mine.append(Gap(code="BLOCKED_WITHOUT_REASON", task=task, recipients=to))
        if policy.detect_hints and check_links:
            for ref, evidence in dependency_hints(task, f"{task.title}\n{text}"):
                local = (ref.tracker, ref.project) == (task.ref.tracker, task.ref.project)
                if local and str(ref) not in graph.tasks:
                    continue  # closed or unknown: it can't block anything
                if local and graph.linked(ref, task.ref):
                    continue
                label = ref.label if local else str(ref)
                mine.append(
                    Gap(
                        code="UNLINKED_DEPENDENCY",
                        task=task,
                        recipients=to,
                        params={"ref": label, "evidence": evidence},
                    )
                )
        if policy.detect_hints:
            from agentic_pm.engine.seams import mentions

            for target in mentions(task, cfg):
                mine.append(
                    Gap(
                        code="SEAM_SUGGESTED",
                        task=task,
                        recipients=to,
                        params={"target": target.text},
                    )
                )
        if mine:
            gaps.extend(
                g.model_copy(update={"waiting": len(waiting), "urgent_label": urgent}) for g in mine
            )
        else:
            ready += 1
    gaps.sort(key=lambda g: g.priority)  # what blocks the most comes first
    return CompletenessReport(active=active, ready=ready, gaps=gaps, backlog=backlog)
