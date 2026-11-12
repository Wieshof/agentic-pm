"""Schema for `.agent-pm/team.yaml` ("Drucker profiles").

The file is the human-editable source of truth for who prefers which channel,
when, and how the agent may escalate. See docs/data-model.md.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

_DAYS = "Mon|Tue|Wed|Thu|Fri|Sat|Sun"
_HHMM = r"(?:[01]\d|2[0-3]):[0-5]\d"

TimeOfDay = Annotated[str, StringConstraints(pattern=rf"^(?:(?:{_DAYS}) )?{_HHMM}$")]
"""`"08:00"` (daily) or `"Mon 09:00"` (weekly)."""

TimeWindow = Annotated[str, StringConstraints(pattern=rf"^{_HHMM}-{_HHMM}$")]
"""`"14:00-16:00"`."""

LanguageCode = Annotated[str, StringConstraints(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")]
"""ISO 639-1 code, optionally with region: `en`, `de`, `pt-BR`."""

# team.yaml is meant to be committed. These patterns catch credentials pasted
# into it by mistake; secrets belong in environment variables (see README).
_SECRET_PATTERNS = [
    re.compile(p)
    for p in (
        r"gh[pousr]_[A-Za-z0-9]{20,}",  # GitHub tokens
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"\bsk-[A-Za-z0-9_-]{16,}",  # common API keys
        r"\bxox[abposr]-[A-Za-z0-9-]{10,}",  # Slack
        r"\bAKIA[0-9A-Z]{16}\b",  # AWS access key id
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"://[^/\s:@]+:[^/\s@]+@",  # user:password@ in URLs
        r"[?&](api[_-]?key|token|secret|password|access_token)=",
    )
]
_SECRET_KEYS = re.compile(r"(password|passwd|secret|token|api[_-]?key|credential)", re.I)


def find_secrets(data: Any, path: str = "") -> list[str]:
    """Paths in raw team.yaml data that look like credentials."""
    hits: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            sub = f"{path}.{k}" if path else str(k)
            if _SECRET_KEYS.search(str(k)) and v not in (None, ""):
                hits.append(sub)
            else:
                hits += find_secrets(v, sub)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            hits += find_secrets(v, f"{path}[{i}]")
    elif isinstance(data, str) and any(p.search(data) for p in _SECRET_PATTERNS):
        hits.append(path)
    return hits


Handle = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$")]
Phone = Annotated[str, StringConstraints(pattern=r"^\+[0-9 ]{6,20}$")]
Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Archetype(StrEnum):
    READER = "reader"
    WRITER = "writer"
    TALKER = "talker"
    LISTENER = "listener"


class BriefFormat(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    VOICE = "voice"


class Interruptions(StrEnum):
    ANY = "any"
    URGENT_ONLY = "urgent-only"
    NONE = "none"


class Channels(_Strict):
    email: Email | None = None
    phone: Phone | None = None
    whatsapp: Phone | None = None
    chat: str | None = Field(default=None, description="Slack/Teams handle")

    def has(self, name: str) -> bool:
        return getattr(self, name) is not None


class Brief(_Strict):
    when: TimeOfDay
    format: BriefFormat


class CheckIn(_Strict):
    window: TimeWindow
    max_call_seconds: int = Field(default=90, ge=30, le=600)


class Person(_Strict):
    role: str
    archetype: Archetype
    channels: Channels
    brief: Brief | None = None
    check_in: CheckIn | None = None
    interruptions: Interruptions = Interruptions.ANY
    quiet_hours: TimeWindow | None = None
    escalate_after_ignored: int = Field(default=3, ge=1, le=20)
    name: str | None = Field(default=None, description="How the agent greets this person")
    language: LanguageCode = Field(
        default="en",
        description="Language the agent uses with this person (briefs, calls, chats)",
    )
    tracker_login: str | None = Field(
        default=None,
        description="Username in the tracker if it differs from the handle "
        "(GitHub login, or OpenProject display name)",
    )

    def login(self, handle: str) -> str:
        return self.tracker_login or handle


class Project(_Strict):
    tracker: str = Field(
        description="Tracker key from the catalog (`agent-pm trackers`), e.g. github, jira, "
        "or an installed plugin"
    )
    repo: str = Field(description="GitHub 'owner/repo', or OpenProject project identifier")
    base_url: str | None = Field(
        default=None, description="Tracker URL, required for self-hosted trackers (OpenProject)"
    )
    tracker_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Tracker-specific mapping, e.g. status_map for Trello lists or "
        "property names for Notion databases (never secrets)",
    )
    timezone: str = "UTC"
    leads: list[Handle] = Field(min_length=1)
    brief_horizon_days: int = Field(
        default=3, ge=1, le=14, description="'Due soon' window used in briefs"
    )
    ticket_language: LanguageCode = Field(
        default="en",
        description="Language the agent writes in the tracker (how-to docs, comments), "
        "independent of the language people speak with it",
    )
    agent_accounts: list[str] = Field(
        default_factory=list,
        description="Tracker logins the agent writes with (service accounts). Webhooks "
        "caused by these accounts are ignored to prevent self-triggering loops.",
    )


class LLMSettings(_Strict):
    """Model access; local-first per ADR-0001."""

    provider: str = "openai-compatible"
    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434/v1"
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None


# Which channel each archetype / brief format needs to be reachable at all.
_ARCHETYPE_NEEDS: dict[Archetype, tuple[str, ...]] = {
    Archetype.READER: ("email",),
    Archetype.WRITER: ("whatsapp", "chat"),
    Archetype.TALKER: ("phone", "whatsapp"),
    Archetype.LISTENER: ("phone",),
}
_FORMAT_NEEDS: dict[BriefFormat, tuple[str, ...]] = {
    BriefFormat.EMAIL: ("email",),
    BriefFormat.CHAT: ("whatsapp", "chat"),
    BriefFormat.VOICE: ("phone",),
}


class TeamConfig(_Strict):
    @model_validator(mode="before")
    @classmethod
    def _no_secrets(cls, data: Any) -> Any:
        if hits := find_secrets(data):
            raise ValueError(
                f"looks like a secret at {', '.join(hits)}. team.yaml is committed to the "
                "repository; put credentials in environment variables instead (see README)"
            )
        return data

    project: Project
    people: dict[Handle, Person] = Field(min_length=1)
    llm: LLMSettings = LLMSettings()

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        errors: list[str] = []
        from agentic_pm.adapters.registry import known_trackers

        if self.project.tracker not in known_trackers():
            errors.append(
                f"project.tracker: unknown tracker '{self.project.tracker}' "
                f"(known: {', '.join(sorted(known_trackers()))})"
            )
        if self.project.tracker == "openproject" and not self.project.base_url:
            errors.append("project.base_url is required for tracker 'openproject'")
        for lead in self.project.leads:
            if lead not in self.people:
                errors.append(f"project.leads: '{lead}' is not defined under people")
        for handle, p in self.people.items():
            need = _ARCHETYPE_NEEDS[p.archetype]
            if not any(p.channels.has(c) for c in need):
                errors.append(
                    f"people.{handle}: archetype '{p.archetype}' needs one of channels {need}"
                )
            if p.brief and not any(p.channels.has(c) for c in _FORMAT_NEEDS[p.brief.format]):
                errors.append(
                    f"people.{handle}: brief format '{p.brief.format}' needs one of channels "
                    f"{_FORMAT_NEEDS[p.brief.format]}"
                )
            if p.check_in and not p.channels.has("phone"):
                errors.append(f"people.{handle}: check_in requires a phone channel")
        if errors:
            raise ValueError("; ".join(errors))
        return self


def load_team_config(path: str | Path) -> TeamConfig:
    """Parse and validate a team.yaml file. Raises pydantic.ValidationError or ValueError."""
    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return TeamConfig.model_validate(raw)


def json_schema() -> dict[str, Any]:
    schema = TeamConfig.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "agentic-pm team.yaml"
    return schema
