"""Inconsistency triangulation (#15): a status claim that doesn't match the tracker.

Sources of claims:
* a chat or email message ("#12 is done", "ich hänge bei #12 fest")
* a recent human comment on the ticket while its status says otherwise

A conflict is never fixed automatically. It turns into one short question
(a "micro-interview") to the person who can settle it: the claimant if they
own the task (chat: reply "yes"), otherwise the owner via the normal approval
flow. Claims come from untrusted text, so the rules here are deliberately
conservative: negations, questions and "almost done" don't count.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from agentic_pm.adapters.base import CLOSED_STATUSES, Task, TaskStatus
from agentic_pm.audit import AUDIT_MARKER

ClaimKind = Literal["done", "blocked", "started"]
EVIDENCE_MAX = 80

_PATTERNS: dict[ClaimKind, re.Pattern[str]] = {
    "done": re.compile(
        r"\b(done|finished|fixed|completed|shipped|merged|deployed|resolved|"
        r"erledigt|fertig|behoben|abgeschlossen|ausgeliefert|gemergt|gemerged)\b",
        re.I,
    ),
    "blocked": re.compile(
        r"\b(blocked|stuck|waiting (?:on|for)|can'?t continue|"
        r"blockiert|hänge fest|hängt fest|komme nicht weiter|warte auf|wartet auf)\b",
        re.I,
    ),
    "started": re.compile(
        r"\b(started|starting|working on|in progress|picked (?:it )?up|on it|"
        r"angefangen|begonnen|arbeite (?:dran|daran)|bin dran)\b",
        re.I,
    ),
}
# Within a few words before the claim word, these make it "not a claim".
_HEDGE = re.compile(
    r"\b(not|n't|never|almost|nearly|soon|once|when|until|if|whether|"
    r"nicht|nie|kein|keine|fast|bald|sobald|wenn|falls|ob|bis)\b|n't\b",
    re.I,
)
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


class Claim(BaseModel):
    kind: ClaimKind
    evidence: str


class Conflict(BaseModel):
    task: Task
    claim: Claim
    proposed: TaskStatus
    by: str | None = None  # tracker login of the comment author (comment conflicts)


def _evidence(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= EVIDENCE_MAX else flat[: EVIDENCE_MAX - 1] + "…"


def detect_claim(text: str) -> Claim | None:
    """The one clear status claim in `text`, or None (none, hedged, or contradictory)."""
    found: dict[ClaimKind, str] = {}
    for sentence in _SENTENCE.findall(text):
        s = sentence.strip()
        if not s or s.endswith("?"):
            continue
        for kind, pattern in _PATTERNS.items():
            m = pattern.search(s)
            if not m:
                continue
            before = " ".join(s[: m.start()].split()[-3:])
            if _HEDGE.search(before) or _HEDGE.search(m.group(0)):
                continue
            found.setdefault(kind, s)
    if "done" in found and "blocked" not in found:
        return Claim(kind="done", evidence=_evidence(found["done"]))
    if len(found) == 1:
        kind = next(iter(found))
        return Claim(kind=kind, evidence=_evidence(found[kind]))
    return None


def conflict(task: Task, claim: Claim) -> Conflict | None:
    """The status the claim implies, if the tracker says something else."""
    status = task.status
    proposed: TaskStatus | None = None
    if claim.kind == "done" and status not in CLOSED_STATUSES:
        proposed = TaskStatus.DONE
    elif claim.kind == "blocked" and status is not TaskStatus.BLOCKED:
        proposed = TaskStatus.BLOCKED
    elif claim.kind == "started" and status in (TaskStatus.OPEN, *CLOSED_STATUSES):
        proposed = TaskStatus.IN_PROGRESS
    if proposed is None:
        return None
    return Conflict(task=task, claim=claim, proposed=proposed)


def comment_conflicts(tasks: list[Task], now: datetime, window_hours: int = 24) -> list[Conflict]:
    """Open tasks whose latest human comment (from the last day) claims otherwise.

    Only the latest comment counts and only within `window_hours`, so the same
    question isn't asked again tomorrow (no state needed).
    """
    out: list[Conflict] = []
    since = now - timedelta(hours=window_hours)
    for task in tasks:
        human = [c for c in task.comments if AUDIT_MARKER not in c.body]
        if not human:
            continue
        last = max(human, key=lambda c: c.created_at)
        if last.created_at < since:
            continue
        claim = detect_claim(last.body)
        if claim and (c := conflict(task, claim)):
            out.append(c.model_copy(update={"by": last.author}))
    return out
