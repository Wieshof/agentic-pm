from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_pm.cli import main
from agentic_pm.config import json_schema, load_team_config
from agentic_pm.config.team import TeamConfig

EXAMPLE = Path(__file__).parents[1] / ".agent-pm" / "team.example.yaml"


def base() -> dict:  # type: ignore[type-arg]
    return {
        "project": {"tracker": "github", "repo": "o/r", "leads": ["alex"]},
        "people": {
            "alex": {"role": "lead", "archetype": "reader", "channels": {"email": "a@x.io"}},
        },
    }


def test_example_file_is_valid() -> None:
    cfg = load_team_config(EXAMPLE)
    assert set(cfg.people) == {"alex", "sam", "kim"}
    assert cfg.llm.base_url.startswith("http://localhost")


def test_unknown_lead_rejected() -> None:
    data = base()
    data["project"]["leads"] = ["nobody"]
    with pytest.raises(ValidationError, match="'nobody' is not defined"):
        TeamConfig.model_validate(data)


def test_archetype_needs_matching_channel() -> None:
    data = base()
    data["people"]["alex"]["archetype"] = "listener"
    with pytest.raises(ValidationError, match="needs one of channels"):
        TeamConfig.model_validate(data)


def test_voice_brief_needs_phone() -> None:
    data = base()
    data["people"]["alex"]["brief"] = {"when": "08:00", "format": "voice"}
    with pytest.raises(ValidationError, match="brief format 'voice'"):
        TeamConfig.model_validate(data)


@pytest.mark.parametrize("when", ["8:00", "25:00", "Monday 09:00", "09:00 Mon"])
def test_bad_time_rejected(when: str) -> None:
    data = base()
    data["people"]["alex"]["brief"] = {"when": when, "format": "email"}
    with pytest.raises(ValidationError):
        TeamConfig.model_validate(data)


def test_unknown_keys_rejected() -> None:
    data = base()
    data["people"]["alex"]["favourite_colour"] = "blue"
    with pytest.raises(ValidationError):
        TeamConfig.model_validate(data)


def test_schema_is_exported() -> None:
    schema = json_schema()
    assert schema["title"] == "agentic-pm team.yaml"
    assert "people" in schema["properties"]


def test_cli_validate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(EXAMPLE)]) == 0
    bad = tmp_path / "team.yaml"
    bad.write_text(
        "project: {tracker: github, repo: o/r, leads: [a]}\n"
        "people:\n  a: {role: x, archetype: reader, channels: {email: a@x.io},"
        " brief: {when: 10:00, format: email}}\n"
    )
    assert main(["validate", str(bad)]) == 1
    assert "quote times" in capsys.readouterr().err
    assert main(["validate", str(tmp_path / "missing.yaml")]) == 2
