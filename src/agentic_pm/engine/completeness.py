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

Hints from free text are **suggestions only**: the text is untrusted, nothing
is ever changed automatically, and only the short matched phrase is quoted.
Gaps go to the person concerned; leads see unowned work and a team-level
readiness ratio, never per-person counts (ADR-0004).
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel

from agentic_pm.adapters.base import Task, TaskRef, TaskStatus
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine.dependencies import DependencyGraph

_KEYWORDS = (
    r"blocked by|waiting (?:on|for)|depends on|needs|requires|after|"
    r"blockiert durch|wartet auf|abhängig von|hängt an|braucht|nach"
)
# Only things that look like task ids: #14, #P-7, T-08 / APP-12 (letters-digits),
# instance:T-08 (spreadsheet) or tracker:owner/repo#42. Dates ("after 2026-11-25")
# and plain words ("after review") never match.
_REF = (
    r"(?P<tracker>[a-z0-9_-]+):(?P<project>[\w./-]+)#(?P<qid>[A-Za-z0-9][\w-]*)"
    r"|(?P<inst>[a-z0-9_-]+):(?P<iid>[A-Za-z][A-Za-z0-9]*-\d+)"
    r"|#(?P<hid>[A-Za-z0-9](?:[\w-]*[A-Za-z0-9])?)"
    r"|(?P<key>\b[A-Z][A-Z0-9]*-\d+\b)"
)
_HINT = re.compile(rf"(?i:\b(?:{_KEYWORDS}))\s+(?:{_REF})")
_DUE_HINT = re.compile(
    r"(?i:\b(?:due|deadline|by|until|target|delivery|bis|fällig|termin|abgabe|spätestens)\b)"
    r"[\s:]+(?:[^\s\d]+\s+){0,2}?(?P<date>\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})"
)
EVIDENCE_MAX = 60


class Gap(BaseModel):
    code: str
    task: Task
    recipients: list[str]  # team.yaml handles
    params: dict[str, str] = {}


class CompletenessReport(BaseModel):
    active: int
    ready: int
    gaps: list[Gap]

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
    m = _DUE_HINT.search(text)
    if not m:
        return None
    parsed = _parse_date(m.group("date"))
    return (parsed, _evidence(m.group(0))) if parsed else None


def dependency_hints(task: Task, text: str) -> list[tuple[TaskRef, str]]:
    """Task references named after 'waiting on' & co., resolved relative to `task`."""
    found: dict[str, tuple[TaskRef, str]] = {}
    for m in _HINT.finditer(text):
        here = task.ref
        if m.group("qid"):
            ref = TaskRef(tracker=m.group("tracker"), project=m.group("project"), id=m.group("qid"))
        elif m.group("iid"):
            if m.group("inst") != here.project:
                continue  # some other sheet: can't resolve safely
            ref = TaskRef(tracker=here.tracker, project=here.project, id=m.group("iid"))
        else:
            ref = TaskRef(
                tracker=here.tracker, project=here.project, id=m.group("hid") or m.group("key")
            )
        if ref != here:
            found.setdefault(str(ref), (ref, _evidence(m.group(0))))
    return list(found.values())


def check_completeness(cfg: TeamConfig, graph: DependencyGraph) -> CompletenessReport:
    policy = cfg.completeness
    caps = graph.capabilities
    triage = list(policy.triage or cfg.project.leads)
    check_due = policy.require_due and (caps is None or caps.due_dates != "none")
    check_estimate = policy.require_estimate and (caps is None or caps.estimates != "none")
    check_links = caps is None or caps.dependencies != "none"

    gaps: list[Gap] = []
    active = ready = 0
    for task in sorted(graph.tasks.values(), key=lambda t: str(t.ref)):
        if task.status in (TaskStatus.DONE, TaskStatus.CLOSED):
            continue
        active += 1
        mine: list[Gap] = []
        owners = [h for login in task.assignees if (h := cfg.handle_for_login(login))]
        strangers = [login for login in task.assignees if not cfg.handle_for_login(login)]
        to = owners or triage
        text = task.description or ""

        if policy.require_owner and not task.assignees:
            mine.append(Gap(code="MISSING_OWNER", task=task, recipients=triage))
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
                        params={"done": ", ".join(f"#{t.ref.id}" for t in done)},
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
                label = f"#{ref.id}" if local else str(ref)
                mine.append(
                    Gap(
                        code="UNLINKED_DEPENDENCY",
                        task=task,
                        recipients=to,
                        params={"ref": label, "evidence": evidence},
                    )
                )
        if mine:
            gaps.extend(mine)
        else:
            ready += 1
    return CompletenessReport(active=active, ready=ready, gaps=gaps)
