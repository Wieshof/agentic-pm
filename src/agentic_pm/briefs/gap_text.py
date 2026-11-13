"""Completeness gaps as friendly single questions (EN/DE), plus the readiness line."""

from __future__ import annotations

from agentic_pm.engine.completeness import CompletenessReport, Gap

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "heading": "🧩 A few details are missing",
        "more": "… and {n} more",
        "MISSING_OWNER": "{task} has no owner, so it shows up in nobody's brief. Who takes it?",
        "OWNER_NOT_IN_TEAM": "{task} belongs to {owner}, who isn't in the team file and gets no "
        "brief. Add them, or hand the task over?",
        "MISSING_DUE": "{task} has no due date, so I can't tell whether it's at risk. "
        "When should it be done?",
        "IMPLICIT_DUE": "{task} has no due date, but the text says “{evidence}”. "
        "Is {date} the due date? Then please add it.",
        "BLOCKER_DONE": "{task} is marked blocked, but {done} is already done. "
        "Can it go ahead, or is it waiting for something else?",
        "MISSING_ESTIMATE": "{task} has no estimate, so I count it as 1 day. "
        "Roughly how long will it take?",
        "BLOCKED_WITHOUT_REASON": "{task} is marked blocked, but I can't see by what. "
        "What is it waiting for?",
        "UNLINKED_DEPENDENCY": "{task} mentions {ref} (“{evidence}”) but isn't linked to it. "
        "Should it wait for {ref}? Then please link them.",
        "readiness_heading": "📊 Data readiness",
        "readiness": "{pct}% of {n} open tasks have everything the checks need",
        "readiness_counts": "missing: {counts}",
        "count_MISSING_OWNER": "{n} without owner",
        "count_OWNER_NOT_IN_TEAM": "{n} with an owner outside the team file",
        "count_MISSING_DUE": "{n} without due date",
        "count_IMPLICIT_DUE": "{n} with a date only in the text",
        "count_MISSING_ESTIMATE": "{n} without estimate",
        "count_BLOCKED_WITHOUT_REASON": "{n} blocked without a reason",
        "count_BLOCKER_DONE": "{n} blocked by something already done",
        "count_UNLINKED_DEPENDENCY": "{n} unlinked dependencies",
    },
    "de": {
        "heading": "🧩 Hier fehlen noch ein paar Angaben",
        "more": "… und {n} weitere",
        "MISSING_OWNER": "{task} hat niemanden, der zuständig ist, und taucht deshalb in keinem "
        "Briefing auf. Wer übernimmt?",
        "OWNER_NOT_IN_TEAM": "{task} gehört {owner}, aber diese Person steht nicht in der "
        "Team-Datei und bekommt kein Briefing. Eintragen oder übergeben?",
        "MISSING_DUE": "{task} hat keinen Termin, deshalb kann ich nicht sagen, ob es eng wird. "
        "Bis wann soll es fertig sein?",
        "IMPLICIT_DUE": "{task} hat keinen Termin, im Text steht aber „{evidence}“. "
        "Ist der {date} der Termin? Dann trag ihn gern ein.",
        "BLOCKER_DONE": "{task} ist als blockiert markiert, aber {done} ist schon erledigt. "
        "Kann es weitergehen, oder wartet es noch auf etwas anderes?",
        "MISSING_ESTIMATE": "{task} hat keine Schätzung, deshalb rechne ich mit 1 Tag. "
        "Wie lange dauert es ungefähr?",
        "BLOCKED_WITHOUT_REASON": "{task} ist als blockiert markiert, aber ich sehe nicht, "
        "wodurch. Worauf wartet es?",
        "UNLINKED_DEPENDENCY": "{task} erwähnt {ref} („{evidence}“), ist aber nicht damit "
        "verknüpft. Soll es auf {ref} warten? Dann verknüpf die beiden gern.",
        "readiness_heading": "📊 Datenqualität",
        "readiness": "{pct} % von {n} offenen Aufgaben haben alles, was die Prüfungen brauchen",
        "readiness_counts": "es fehlen: {counts}",
        "count_MISSING_OWNER": "{n} ohne Zuständige",
        "count_OWNER_NOT_IN_TEAM": "{n} mit Zuständigen außerhalb der Team-Datei",
        "count_MISSING_DUE": "{n} ohne Termin",
        "count_IMPLICIT_DUE": "{n} mit Termin nur im Text",
        "count_MISSING_ESTIMATE": "{n} ohne Schätzung",
        "count_BLOCKED_WITHOUT_REASON": "{n} blockiert ohne Grund",
        "count_BLOCKER_DONE": "{n} blockiert durch bereits Erledigtes",
        "count_UNLINKED_DEPENDENCY": "{n} unverknüpfte Abhängigkeiten",
    },
}


def _t(lang: str) -> dict[str, str]:
    return TEXTS.get(lang.split("-")[0], TEXTS["en"])


def render_gap(gap: Gap, lang: str) -> str:
    task = f"#{gap.task.ref.id} {gap.task.title}"
    return _t(lang)[gap.code].format(task=task, **gap.params)


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
    lines = [t["readiness"].format(pct=pct, n=report.active)]
    counts = report.counts()
    if counts:
        parts = [t[f"count_{code}"].format(n=n) for code, n in sorted(counts.items())]
        lines.append(t["readiness_counts"].format(counts=", ".join(parts)))
    return t["readiness_heading"], lines
