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

from agentic_pm.cadence import SPEC_PATTERN

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


CadenceSpec = Annotated[str, StringConstraints(pattern=SPEC_PATTERN)]
"""`"08:30"` (weekdays), `"daily 08:30"`, `"Fri 15:00"`, `"last_friday 16:00"`."""


class Cadence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    morning_triage: CadenceSpec | None = Field(
        default=None, description="Personal briefs for everyone without their own brief.when"
    )
    end_of_day: CadenceSpec | None = Field(
        default=None, description="Short evening note to leads, only if something needs them"
    )
    weekly_digest: CadenceSpec | None = Field(
        default=None, description="Week roll-up for leads (steering)"
    )
    monthly_health_check: CadenceSpec | None = Field(
        default=None, description="Monthly check against baseline (arrives with issue #54)"
    )
    inbox_poll_minutes: int = Field(default=2, ge=1, le=60)
    chat_poll_seconds: int = Field(default=15, ge=2, le=600)


Handle = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$")]
Phone = Annotated[str, StringConstraints(pattern=r"^\+[0-9 ]{6,20}$")]
Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
MatrixId = Annotated[str, StringConstraints(pattern=r"^@[^:\s]+:[^\s]+$")]
ChannelName = Literal["email", "matrix", "signal"]


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
    matrix: MatrixId | None = Field(
        default=None, description="Matrix user id, e.g. @sam:matrix.org"
    )
    signal: Phone | None = Field(
        default=None, description="Signal phone number, e.g. +43 660 1234567"
    )

    def has(self, name: str) -> bool:
        return getattr(self, name) is not None


class Brief(_Strict):
    when: CadenceSpec | None = Field(
        default=None, description="Own time; default is cadence.morning_triage"
    )
    format: BriefFormat


class CheckIn(_Strict):
    window: TimeWindow
    max_call_seconds: int = Field(default=90, ge=30, le=600)


class Person(_Strict):
    role: str | None = Field(
        default=None, description="What this person does, e.g. backend-engineer"
    )
    archetype: Archetype | None = Field(
        default=None,
        description="How this person likes to get information (reader | writer | talker | "
        "listener). Leave it out to start: briefs then go to the console only",
    )
    channels: Channels = Field(default_factory=lambda: Channels())
    brief: Brief | None = None
    check_in: CheckIn | None = None
    interruptions: Interruptions = Interruptions.ANY
    quiet_hours: TimeWindow | None = None
    escalate_after_ignored: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Unanswered nudges for one question before the next channel in `prefer` "
        "is tried (counted per question, never per person)",
    )
    name: str | None = Field(default=None, description="How the agent greets this person")
    language: LanguageCode = Field(
        default="en",
        description="Language the agent uses with this person (briefs, calls, chats)",
    )
    prefer: list[ChannelName] = Field(
        default_factory=list,
        description="Channels to reach this person on, in order (default: chat first for "
        "writers, talkers and listeners, email first for readers)",
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
    formality: Literal["informal", "formal"] = Field(
        default="informal",
        description="How the agent addresses people in every language: 'informal' (German "
        "'Du', French 'tu', …) or 'formal' ('Sie', 'vous', …). Languages without formal texts "
        "yet stay informal for fixed texts",
    )
    allow_writes: bool = Field(
        default=False,
        description="Opt-in: let the agent write to the tracker (comments, labels, fields), "
        "always behind the permission tiers",
    )
    agent_email: str | None = Field(
        default=None,
        description="The agent's mailbox, e.g. pm@acme.com. Replies about a task go to "
        "plus-addresses like pm+142@acme.com",
    )
    email_trusted_authserv_id: str | None = Field(
        default=None,
        description="Host name your incoming mail server writes into Authentication-Results "
        "(e.g. mx.acme.com). When set, only email it verified (DMARC, or DKIM/SPF aligned "
        "with the sender's domain) is acted on; everything else is ignored as possibly forged",
    )
    control_plane_url: str | None = Field(
        default=None,
        description="Public URL of `agent-pm run` (approval links, webhooks), "
        "e.g. https://pm.acme.com",
    )
    agent_accounts: list[str] = Field(
        default_factory=list,
        description="Tracker logins the agent writes with (service accounts). Webhooks "
        "caused by these accounts are ignored to prevent self-triggering loops.",
    )


class Completeness(_Strict):
    """Which details every open task should have (data completeness check)."""

    require_owner: bool = True
    require_due: bool = True
    require_estimate: bool = False
    require_blocker_reason: bool = True
    detect_hints: bool = Field(
        default=True, description="Suggest links for 'waiting on #14' & co. in task text"
    )
    triage: list[Handle] = Field(
        default_factory=list, description="Who gets unowned tasks (default: project.leads)"
    )
    max_per_brief: int = Field(default=5, ge=1, le=20)
    urgent_labels: list[str] = Field(
        default_factory=list,
        description="Extra labels that mark a task as urgent, on top of the built-in ones "
        "(blocker, critical, urgent, p0, p1, sev1, security, hotfix, … in every language). "
        "Urgent tasks are never backlog and come first",
    )
    backlog: Literal["separate", "check"] = Field(
        default="separate",
        description="'separate': open tasks with no owner, no due date, no progress and no "
        "dependencies are backlog, counted on one line instead of asked about. "
        "'check': ask about every open task",
    )


class LLMSettings(_Strict):
    """Model access; local-first per ADR-0001."""

    provider: str = "openai-compatible"
    model: str = "gemma4"
    base_url: str = "http://localhost:11434/v1"
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None


# Which channel each archetype / brief format needs to be reachable at all.
_ARCHETYPE_NEEDS: dict[Archetype, tuple[str, ...]] = {
    Archetype.READER: ("email",),
    Archetype.WRITER: ("whatsapp", "chat", "matrix", "signal"),
    Archetype.TALKER: ("phone", "whatsapp", "signal", "matrix"),
    Archetype.LISTENER: ("phone",),
}
_FORMAT_NEEDS: dict[BriefFormat, tuple[str, ...]] = {
    BriefFormat.EMAIL: ("email",),
    BriefFormat.CHAT: ("matrix", "signal"),
    BriefFormat.VOICE: ("phone",),
}


class Speech(_Strict):
    """Speech-to-text for voice notes. Runs locally; audio and transcripts stay in RAM."""

    engine: Literal["none", "faster-whisper", "whisper-cpp"] = Field(
        default="none",
        description="faster-whisper (pip extra 'voice') or a whisper.cpp server at `url`",
    )
    model: str = Field(default="small", description="Whisper model size for faster-whisper")
    url: str | None = Field(
        default=None, description="whisper.cpp server, e.g. http://localhost:8080/inference"
    )


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
    cadence: Cadence = Cadence()
    completeness: Completeness = Completeness()
    speech: Speech = Speech()

    # ------------------------------------------------------------ lookups

    def handle_for_login(self, login: str) -> str | None:
        return next(
            (h for h, p in self.people.items() if p.login(h).lower() == login.lower()), None
        )

    def handle_for_email(self, email: str) -> str | None:
        return next(
            (
                h
                for h, p in self.people.items()
                if p.channels.email and p.channels.email.lower() == email.lower()
            ),
            None,
        )

    def handle_for_chat(self, platform: str, address: str) -> str | None:
        """matrix: '@sam:example.org' (case-insensitive), signal: '+43 660…' (spaces ignored)."""

        def norm(v: str) -> str:
            return v.replace(" ", "").lower()

        return next(
            (
                h
                for h, p in self.people.items()
                if (v := getattr(p.channels, platform, None)) and norm(v) == norm(address)
            ),
            None,
        )

    def reach_order(self, handle: str) -> list[str]:
        """Channels to try for this person, in order, limited to the ones they have."""
        p = self.people[handle]
        default = (
            ["email", "matrix", "signal"]
            if p.archetype in (None, Archetype.READER)
            else ["signal", "matrix", "email"]
        )
        order = list(p.prefer) or default
        order += [c for c in default if c not in order]
        return [c for c in order if p.channels.has(c)]

    def display_name(self, handle: str) -> str:
        person = self.people.get(handle)
        return (person.name if person and person.name else None) or handle.capitalize()

    def language_of(self, handle: str) -> str:
        person = self.people.get(handle)
        return person.language if person else "en"

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        errors: list[str] = []
        from agentic_pm.adapters.registry import known_trackers

        if self.project.tracker not in known_trackers():
            errors.append(
                f"project.tracker: unknown tracker '{self.project.tracker}' "
                f"(known: {', '.join(sorted(known_trackers()))})"
            )
        if self.project.tracker == "spreadsheet":
            from pydantic import ValidationError

            from agentic_pm.adapters.spreadsheet import SpreadsheetOptions

            try:
                SpreadsheetOptions.model_validate(self.project.tracker_options)
            except ValidationError as e:
                for err in e.errors():
                    loc = ".".join(str(x) for x in err["loc"])
                    errors.append(f"project.tracker_options.{loc}: {err['msg']}")
        if self.project.tracker == "openproject" and not self.project.base_url:
            errors.append("project.base_url is required for tracker 'openproject'")
        for h in self.completeness.triage:
            if h not in self.people:
                errors.append(f"completeness.triage: '{h}' is not defined under people")
        for lead in self.project.leads:
            if lead not in self.people:
                errors.append(f"project.leads: '{lead}' is not defined under people")
        for handle, p in self.people.items():
            need = _ARCHETYPE_NEEDS[p.archetype] if p.archetype else ()
            if need and not any(p.channels.has(c) for c in need):
                errors.append(
                    f"people.{handle}: archetype '{p.archetype}' needs one of channels {need}"
                )
            if p.brief and not any(p.channels.has(c) for c in _FORMAT_NEEDS[p.brief.format]):
                errors.append(
                    f"people.{handle}: brief format '{p.brief.format}' needs one of channels "
                    f"{_FORMAT_NEEDS[p.brief.format]}"
                )
            if p.brief and p.brief.when is None and self.cadence.morning_triage is None:
                errors.append(
                    f"people.{handle}: brief.when is missing and cadence.morning_triage is not set"
                )
            if p.check_in and not p.channels.has("phone"):
                errors.append(f"people.{handle}: check_in requires a phone channel")
        if errors:
            raise ValueError("; ".join(errors))
        from agentic_pm import i18n

        i18n.configure(self.project.formality)
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
