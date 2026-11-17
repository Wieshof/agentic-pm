"""Coverage warnings in the reader's language (EN/DE), for briefs and digests."""

from __future__ import annotations

from agentic_pm import i18n
from agentic_pm.adapters.coverage import CoverageReport, CoverageWarning

MAX_ITEMS = 10


def _t(lang: str) -> i18n.Texts:
    return i18n.texts("coverage", lang)


def render_warning(w: CoverageWarning, lang: str) -> str:
    t = _t(lang)
    location = w.location.replace("row ", f"{t['row']} ")
    try:
        text = t[w.code].format(**w.params)
    except (KeyError, IndexError):
        text = w.message  # unknown code or missing params: the English message
    text = text.replace("row ", f"{t['row']} ")
    return f"{location}: {text}"


def render_coverage(report: CoverageReport, lang: str) -> tuple[str, list[str]]:
    """(heading, items) with errors first and at most MAX_ITEMS lines."""
    t = _t(lang)
    ordered = sorted(report.warnings, key=lambda w: w.severity != "error")
    items = [render_warning(w, lang) for w in ordered[:MAX_ITEMS]]
    if len(ordered) > MAX_ITEMS:
        items.append(t["more"].format(n=len(ordered) - MAX_ITEMS))
    return t["heading"].format(source=report.source), items
