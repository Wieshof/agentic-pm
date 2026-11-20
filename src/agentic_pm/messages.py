"""Friendly messages the agent sends to people.

The texts live in `agentic_pm/i18n/locales/<lang>.yaml` (area `messages`), so
tone stays consistent: warm, short, never pushy. Missing languages or keys
fall back to English (see docs/languages.md).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from agentic_pm import i18n
from agentic_pm.adapters.base import Task, TaskPatch, TaskStatus
from agentic_pm.config.team import TeamConfig


def texts(lang: str) -> i18n.Texts:
    return i18n.texts("messages", lang)


def language_name(code: str, in_lang: str) -> str:
    return i18n.language_name(code, in_lang)


def describe_patch(task: Task, patch: TaskPatch, lang: str) -> tuple[str, str]:
    """(long description, short label) of a patch, e.g. ('move the due date …', 'new due date')."""
    t = texts(lang)
    from agentic_pm.adapters._text import format_hours

    parts: list[tuple[str, str]] = []
    if patch.due is not None and patch.due != task.due:
        parts.append(
            (t["status_due"].format(old=task.due or "-", new=patch.due), t["status_due_short"])
        )
    if patch.assignees is not None and sorted(patch.assignees) != sorted(task.assignees):
        parts.append(
            (
                t["assign"].format(
                    old=", ".join(task.assignees) or t["nobody"],
                    new=", ".join(patch.assignees) or t["nobody"],
                ),
                t["assign_short"],
            )
        )
    if patch.status is not None and patch.status != task.status:
        parts.append((t["status"].format(new=status_name(patch.status, lang)), t["status_short"]))
    if patch.estimate_hours is not None and patch.estimate_hours != task.estimate_hours:
        parts.append(
            (t["estimate"].format(new=format_hours(patch.estimate_hours)), t["estimate_short"])
        )
    if not parts:
        parts.append((t["labels"], t["labels"]))
    return "; ".join(p[0] for p in parts), parts[0][1]


def render(lang: str, key: str, **kw: Any) -> str:
    return texts(lang)[key].format(**kw)


def channel_label(name: str, lang: str) -> str:
    """'email' → 'email' / 'E-Mail', 'signal' → 'Signal'."""
    return i18n.texts("channels", lang).get(name, name)


def status_name(status: TaskStatus, lang: str) -> str:
    return i18n.texts("status", lang).get(status.value, status.value)


def friendly_date(d: date, lang: str) -> str:
    """'Fri 21 Nov 2026' / 'Fr., 21.11.2026'."""
    return i18n.friendly_date(d, lang)


def tracker_name(key: str) -> str:
    from agentic_pm.adapters.catalog import load_catalog

    entry = load_catalog().get(key)
    return entry.name if entry else key


DOC_URL = "https://github.com/Wieshof/agentic-pm/blob/main/docs/{path}people-data.md"


def onboarding(cfg: TeamConfig, handle: str) -> tuple[str, str]:
    """(subject, text) of the friendly first message to a person (ADR-0004 transparency)."""
    person = cfg.people[handle]
    lang = person.language
    t = texts(lang)
    channels = ", ".join(
        channel_label(k, lang) for k, v in person.channels.model_dump().items() if v
    )
    brief = t["onboarding_no_brief"]
    if person.brief:
        when = person.brief.when or cfg.cadence.morning_triage or "-"
        brief = f"{person.brief.format.value} ({when}, {cfg.project.timezone})"
    llm = cfg.llm.model
    names = ", ".join(cfg.display_name(h) for h in cfg.all_leads())
    de = i18n.base_language(lang) == "de"  # the docs exist in English and German
    return (
        t["onboarding_subject"].format(name=cfg.display_name(handle)),
        t["onboarding_body"].format(
            name=cfg.display_name(handle),
            project=cfg.project.repo or ", ".join(cfg.sources),
            channels=channels,
            language=language_name(lang, lang),
            tracker=", ".join(
                dict.fromkeys(tracker_name(cfg.tracker_of(k)) for k in cfg.sources or [None])
            ),
            llm=llm,
            brief=brief,
            leads=names,
            doc=DOC_URL.format(path="de/" if de else ""),
        ),
    )
