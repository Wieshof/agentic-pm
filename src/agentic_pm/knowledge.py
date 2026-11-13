"""Knowledge Extractor: turn "here's how I fixed it" into a how-to on the ticket.

One local-model call classifies an inbound message and, for solutions,
extracts problem / root cause / fix / verification **in the ticket language**
(project.ticket_language), whatever language the person wrote in. A guard
rejects invented ticket ids, empty fixes, overly long fields and output in
the wrong language; the caller then falls back to posting the note as-is.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from agentic_pm.llm.base import ChatMessage, LLMError, LLMProvider
from agentic_pm.messages import language_name

Kind = Literal["solution", "status", "question", "scope_change", "other"]
KINDS: tuple[str, ...] = ("solution", "status", "question", "scope_change", "other")
MAX_FIELD = 300
_ID = re.compile(r"#(\d+)")
_WORD = re.compile(r"[a-zäöüß]+", re.I)


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


_STOP = {
    "de": _words(
        """der die das und ist nicht mit ich wir es ein eine einen den dem auf für von zu
        im bei wurde wurden habe hat sind auch noch nach aus dass"""
    ),
    # Words that are also German ("in", "an", "die") are left out on purpose.
    "en": _words(
        """the and is was were with we it of to for on that this by from has have
        been be are after"""
    ),
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "problem": {"type": "string"},
        "root_cause": {"type": "string"},
        "fix": {"type": "string"},
        "verification": {"type": "string"},
    },
    "required": ["kind", "problem", "root_cause", "fix", "verification"],
    "additionalProperties": False,
}


class Analysis(BaseModel):
    kind: Kind
    problem: str = ""
    root_cause: str = ""
    fix: str = ""
    verification: str = ""


def detect_language(text: str) -> str | None:
    """Rough en/de guess from stopwords; None if unclear (short or other language)."""
    words = [w.lower() for w in _WORD.findall(text)]
    if len(words) < 4:
        return None
    scores = {lang: sum(w in stop for w in words) for lang, stop in _STOP.items()}
    best = max(scores, key=lambda k: scores[k])
    other = min(scores.values())
    if scores[best] < 2 or scores[best] < other + 2:  # needs a clear margin
        return None
    return best


def build_messages(
    message: str, task_title: str, author: str, ticket_language: str
) -> list[ChatMessage]:
    lang = language_name(ticket_language, "en")
    return [
        ChatMessage(
            role="system",
            content=(
                "You read one message a team member sent about a task. Classify it as one of: "
                "solution (explains how something was fixed or done), status (news about "
                "progress or timing), question, scope_change (asks for new or extra work), "
                "other (thanks, greetings or acknowledgements without new information).\n"
                f"For a solution, fill problem, root_cause, fix and verification in {lang}, "
                "translating if the message is in another language. Use short phrases. Use only "
                "facts from the message; keep numbers and names exactly; leave a field empty "
                "if the message doesn't say it. Never invent ticket numbers. For other kinds "
                "leave all four fields empty.\n"
                'Answer as JSON: {"kind": ..., "problem": ..., "root_cause": ..., '
                '"fix": ..., "verification": ...}'
            ),
        ),
        ChatMessage(
            role="user",
            content=json.dumps(
                {"task": task_title, "author": author, "message": message}, ensure_ascii=False
            ),
        ),
    ]


def check_analysis(a: Analysis, message: str, task_title: str, ticket_language: str) -> list[str]:
    problems: list[str] = []
    fields = {k: getattr(a, k) for k in ("problem", "root_cause", "fix", "verification")}
    if a.kind == "solution" and not a.fix.strip():
        problems.append("solution without a fix")
    for name, value in fields.items():
        if len(value) > MAX_FIELD:
            problems.append(f"{name} too long")
    known = set(_ID.findall(message + " " + task_title))
    invented = {i for v in fields.values() for i in _ID.findall(v)} - known
    if invented:
        problems.append(f"invented ticket ids: {sorted('#' + i for i in invented)}")
    if a.kind == "solution":
        written = " ".join(fields.values())
        detected = detect_language(written)
        target = ticket_language.split("-")[0]
        if detected and target in _STOP and detected != target:
            problems.append(f"written in {detected}, expected {target}")
    return problems


async def analyze(
    provider: LLMProvider,
    message: str,
    *,
    task_title: str,
    author: str,
    ticket_language: str,
) -> tuple[Analysis | None, list[str]]:
    try:
        out = await provider.complete(
            build_messages(message, task_title, author, ticket_language),
            json_schema=SCHEMA,
            max_tokens=600,
        )
        analysis = Analysis.model_validate(json.loads(out.text))
    except (LLMError, ValueError, ValidationError) as e:
        return None, [f"llm error: {e}"]
    return analysis, check_analysis(analysis, message, task_title, ticket_language)


HOWTO = {
    "en": {
        "title": "### How it was solved",
        "problem": "Problem",
        "root_cause": "Root cause",
        "fix": "Fix",
        "verification": "Verified",
        "source": "_Explained by {author} via {channel}{lang_note}, structured by agent-pm._",
        "lang_note": " (in {lang})",
        "note_title": "### Note from {author} via {channel}",
    },
    "de": {
        "title": "### Wie es gelöst wurde",
        "problem": "Problem",
        "root_cause": "Ursache",
        "fix": "Lösung",
        "verification": "Verifiziert",
        "source": "_Erklärt von {author} per {channel}{lang_note}, strukturiert von agent-pm._",
        "lang_note": " (auf {lang})",
        "note_title": "### Notiz von {author} per {channel}",
    },
}
HOWTO_MARKERS = tuple(v["title"] for v in HOWTO.values())


def _t(lang: str) -> dict[str, str]:
    return HOWTO.get(lang.split("-")[0], HOWTO["en"])


def render_howto(
    a: Analysis, *, ticket_language: str, author: str, channel: str, source_language: str | None
) -> str:
    t = _t(ticket_language)
    lines = [t["title"]]
    for key in ("problem", "root_cause", "fix", "verification"):
        value = getattr(a, key).strip()
        if value:
            lines.append(f"- **{t[key]}:** {value}")
    lang_note = ""
    if source_language and source_language.split("-")[0] != ticket_language.split("-")[0]:
        lang_note = t["lang_note"].format(lang=language_name(source_language, ticket_language))
    lines += ["", t["source"].format(author=author, channel=channel, lang_note=lang_note)]
    return "\n".join(lines)


def render_note(text: str, *, ticket_language: str, author: str, channel: str) -> str:
    quoted = "\n".join(f"> {line}" if line else ">" for line in text.strip().splitlines())
    return f"{_t(ticket_language)['note_title'].format(author=author, channel=channel)}\n\n{quoted}"
