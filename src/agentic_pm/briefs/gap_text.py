"""Completeness gaps as friendly single questions, plus the readiness line.

Texts: area `gaps` in agentic_pm/i18n/locales/<lang>.yaml.
"""

from __future__ import annotations

from agentic_pm import i18n
from agentic_pm.engine.completeness import CompletenessReport, Gap
from agentic_pm.engine.followup import FollowUp


def _t(lang: str) -> i18n.Texts:
    return i18n.texts("gaps", lang)


def render_gap(gap: Gap, lang: str) -> str:
    """One question; says *why* it matters when other work waits or a label is urgent."""
    task = f"#{gap.task.ref.id} {gap.task.title}"
    t = _t(lang)
    key = gap.code
    if "waiting" in gap.params:
        key = f"{gap.code}_waiting"
    elif "label" in gap.params:
        key = f"{gap.code}_urgent"
    return t[key if key in t else gap.code].format(task=task, **gap.params)


def render_gaps(gaps: list[Gap], lang: str, limit: int) -> tuple[str, list[str]]:
    t = _t(lang)
    items = [render_gap(g, lang) for g in gaps[:limit]]
    if len(gaps) > limit:
        items.append(t["more"].format(n=len(gaps) - limit))
    return t["heading"], items


def render_readiness(report: CompletenessReport, lang: str) -> tuple[str, list[str]]:
    """Team-level only: a ratio and counts by kind, never names (ADR-0004)."""
    t = _t(lang)
    pct = round(report.readiness * 100)
    lines = [t["readiness"].format(pct=pct, n=report.active)] if report.active else []
    counts = report.counts()
    if counts:
        parts = [t[f"count_{code}"].format(n=n) for code, n in sorted(counts.items())]
        lines.append(t["readiness_counts"].format(counts=", ".join(parts)))
    if report.backlog:
        lines.append(t["backlog"].format(n=report.backlog))
    return t["readiness_heading"], lines


def gap_label(gap: Gap, lang: str) -> str:
    """Short label of what's missing, e.g. 'no due date' / 'kein Termin'."""
    return _t(lang)[f"what_{gap.code}"]


def gap_text(lang: str, key: str, **kw: str) -> str:
    return _t(lang)[key].format(**kw)


def render_stalled(items: list[FollowUp], lang: str) -> tuple[str, list[str]]:
    """Task-centric: which tasks still miss something, never who didn't answer."""
    t = _t(lang)
    lines = [
        t["stalled_item"].format(
            id=f.gap.task.ref.id,
            title=f.gap.task.title,
            what=gap_label(f.gap, lang),
            days=f.ignored,
        )
        for f in items
    ]
    return t["stalled_heading"], lines
