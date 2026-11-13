"""Optional LLM summary for briefs, with a hallucination guard.

The model only gets the computed facts and must rephrase them in 1-3 friendly
sentences. `check_summary` rejects anything that mentions task numbers that
are not in the facts, is empty, or is too long; the brief then simply goes out
without a summary.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agentic_pm.briefs.morning import BriefData
from agentic_pm.llm.base import ChatMessage, LLMError, LLMProvider

MAX_WORDS = 70
# Task ids: 12 (GitHub), P-7 (spreadsheets), APP-12 (Jira/Linear). Trailing punctuation excluded.
_TASK_NO = re.compile(r"#([A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?)")
_FORMAL_DE = re.compile(r"\b(Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer)\b")
_LOWER_DU = re.compile(r"\b(du|dich|dir|dein|deine|deinen|deinem|deiner|deines)\b")
_STRAY_HASH = re.compile(r"#(?![A-Za-z0-9])\S*")  # e.g. "#{15}", "# " - not an id

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}

_STYLE = {
    "en": "Write in English. Warm, calm and encouraging, like a helpful teammate; "
    "no pressure, no commands.",
    "de": "Schreibe auf Deutsch. Duze die Person und schreibe die Anrede immer groß: "
    "Du, Dich, Dir, Dein, Deine. Niemals 'Sie'. Herzlich, ruhig und ermutigend, "
    "wie ein hilfsbereiter Teamkollege; kein Druck, keine Befehle.",
}


def style_for(language: str) -> str:
    code = language.split("-")[0]
    if code in _STYLE:
        return _STYLE[code]
    return (
        f"Write in the language with ISO code '{language}'. Use the informal, friendly "
        "form of address. Warm, calm and encouraging, like a helpful teammate."
    )


def summary_facts(d: BriefData) -> dict[str, Any]:
    def t(task: Any) -> dict[str, Any]:
        return {"id": f"#{task.ref.id}", "title": task.title, "due": str(task.due)}

    return {
        "person": d.name,
        "today": d.today.isoformat(),
        "overdue": [t(x) for x in d.overdue],
        "due_soon": [t(x) for x in d.due_soon],
        "at_risk": [
            {**t(r.task), "blocked_by": f"#{r.blocker.ref.id}", "days_late": r.days_late}
            for r in d.my_risks
        ],
        "others_waiting_on_you": [
            {"waiting": f"#{r.task.ref.id}", "on": f"#{r.blocker.ref.id}"} for r in d.waiting_on_me
        ],
        "team_risks": len(d.team_risks),
    }


def has_content(facts: dict[str, Any]) -> bool:
    """Quiet days need no summary; models tend to invent tasks when given nothing."""
    keys = ("overdue", "due_soon", "at_risk", "others_waiting_on_you")
    return any(facts.get(k) for k in keys) or bool(facts.get("team_risks"))


def allowed_ids(facts: dict[str, Any]) -> set[str]:
    return set(_TASK_NO.findall(json.dumps(facts)))


def normalize_summary(summary: str, language: str) -> str:
    """Deterministic clean-up: German Du-forms are always capitalized (team style)."""
    text = summary.strip()
    if language.startswith("de"):
        text = _LOWER_DU.sub(lambda m: m.group(0).capitalize(), text)
    return text


def check_summary(summary: str, facts: dict[str, Any], language: str) -> list[str]:
    problems: list[str] = []
    text = summary.strip()
    if not text:
        problems.append("empty")
    if len(text.split()) > MAX_WORDS:
        problems.append(f"too long ({len(text.split())} words > {MAX_WORDS})")
    unknown = set(_TASK_NO.findall(text)) - allowed_ids(facts)
    if unknown:
        problems.append(f"mentions unknown tasks: {sorted('#' + u for u in unknown)}")
    if stray := _STRAY_HASH.findall(text):
        problems.append(f"stray '#' tags: {stray}")
    if language.startswith("de") and _FORMAL_DE.search(text):
        problems.append("uses formal 'Sie' instead of 'Du'")
    if language.startswith("de") and (lower := _LOWER_DU.findall(text)):
        problems.append(f"Du-forms must be capitalized: {sorted(set(lower))}")
    return problems


def build_messages(facts: dict[str, Any], language: str) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You write the opening lines of a project-management morning brief. "
                f"{style_for(language)} Use 1-3 short sentences, at most {MAX_WORDS} words. "
                "Mention only tasks that appear in the facts, using their exact #numbers. "
                "Lead with what matters most today. No greeting, no sign-off, no lists. "
                'Answer as JSON: {"summary": "..."}'
            ),
        ),
        ChatMessage(role="user", content=json.dumps(facts, ensure_ascii=False)),
    ]


async def generate_summary(
    provider: LLMProvider, facts: dict[str, Any], language: str
) -> tuple[str | None, list[str]]:
    """(raw summary or None, problems). Use the summary only if `problems` is empty.

    Returns (None, []) on quiet days: nothing to summarize, so the model is not asked.
    """
    if not has_content(facts):
        return None, []
    try:
        out = await provider.complete(
            build_messages(facts, language), json_schema=SCHEMA, max_tokens=400
        )
        summary = normalize_summary(str(json.loads(out.text)["summary"]), language)
    except (LLMError, ValueError, KeyError, TypeError) as e:
        return None, [f"llm error: {e}"]
    return summary, check_summary(summary, facts, language)
