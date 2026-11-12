import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from agentic_pm.briefs import build_email, collect, render_html, render_text, subject
from agentic_pm.briefs.summary import (
    check_summary,
    generate_summary,
    has_content,
    normalize_summary,
    summary_facts,
)
from agentic_pm.cli import main
from agentic_pm.config import load_team_config
from agentic_pm.demo import demo_tracker
from agentic_pm.llm import ChatMessage, Completion

TODAY = date(2026, 11, 13)
EXAMPLE = Path(__file__).parents[1] / ".agent-pm" / "team.example.yaml"


@pytest.fixture
def cfg() -> Any:
    return load_team_config(EXAMPLE)


async def brief(cfg: Any, who: str) -> Any:
    return await collect(cfg, who, demo_tracker(cfg.project.repo, TODAY), TODAY)


async def test_alex_lead_brief(cfg: Any) -> None:
    d = await brief(cfg, "alex")
    assert [t.ref.id for t in d.overdue] == ["15"]
    assert [r.task.ref.id for r in d.my_risks] == ["14"]
    assert [r.task.ref.id for r in d.team_risks] == ["13"]  # own risk not repeated
    assert d.cycles == [["#17", "#18"]]
    assert not any(t.ref.id == "14" for t in d.due_soon)  # each task once
    text = render_text(d)
    assert text.startswith("Good morning, Alex!")
    assert "1 day overdue" in text and "#17 → #18" in text
    assert subject(d) == "☀️ Your morning brief: 2 things need you today"


async def test_sam_german_brief_uses_du(cfg: Any) -> None:
    d = await brief(cfg, "sam")
    text = render_text(d)
    assert text.startswith("Guten Morgen, Sam!")
    assert "Kim braucht #12" in text
    assert "Du hast 3 offene Aufgaben" in text
    assert " Sie " not in text
    assert not d.team_risks  # not a lead


async def test_quiet_brief(cfg: Any) -> None:
    from agentic_pm.adapters import InMemoryTracker

    d = await collect(cfg, "kim", InMemoryTracker(), TODAY)
    assert d.is_quiet
    assert "Nothing urgent today" in render_text(d)
    assert subject(d).endswith("a calm day ahead")


async def test_email_has_text_and_html(cfg: Any) -> None:
    d = await brief(cfg, "alex")
    msg = build_email(d, to="alex@example.com", sender="pm@example.com", summary="All good <3")
    assert msg["To"] == "alex@example.com"
    types = [p.get_content_type() for p in msg.iter_parts()]
    assert types == ["text/plain", "text/html"]
    assert "All good &lt;3" in render_html(d, "All good <3")


def test_summary_guard() -> None:
    facts = {"overdue": [{"id": "#11"}], "due_soon": [], "at_risk": [], "team_risks": 0}
    assert check_summary("Finish #11 today.", facts, "en") == []
    assert "unknown" in check_summary("Finish #12.", facts, "en")[0]
    assert "stray" in check_summary("Finish #11 and #abc.", facts, "en")[0]
    assert "formal" in check_summary("Bitte erledigen Sie #11.", facts, "de")[0]
    assert "capitalized" in check_summary("Kümmere dich um #11.", facts, "de")[0]
    assert check_summary("", facts, "en") == ["empty"]
    assert (
        normalize_summary("Kümmere dich um deine Aufgabe.", "de")
        == "Kümmere Dich um Deine Aufgabe."
    )
    assert not has_content({"overdue": [], "due_soon": [], "at_risk": [], "team_risks": 0})


class FakeLLM:
    name = "fake"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    async def complete(self, messages: list[ChatMessage], **_: Any) -> Completion:
        self.calls += 1
        return Completion(text=self.text, model="fake")


async def test_generate_summary(cfg: Any) -> None:
    d = await brief(cfg, "sam")
    facts = summary_facts(d)
    good = FakeLLM(json.dumps({"summary": "Kümmere dich zuerst um #11."}))
    text, problems = await generate_summary(good, facts, "de")
    assert problems == [] and text == "Kümmere Dich zuerst um #11."
    bad = FakeLLM(json.dumps({"summary": "Erledige #99."}))
    _, problems = await generate_summary(bad, facts, "de")
    assert problems and "unknown" in problems[0]
    quiet = FakeLLM("{}")
    assert await generate_summary(quiet, {"overdue": []}, "en") == (None, [])
    assert quiet.calls == 0


def test_cli_demo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["deps", "--demo", "--date", "2026-11-13"]) == 0
    assert "2 at risk · 1 cycle(s)" in capsys.readouterr().out
    assert (
        main(
            [
                "brief",
                "--demo",
                "--all",
                "--date",
                "2026-11-13",
                "--format",
                "eml",
                "--out",
                str(tmp_path),
            ]
        )
        == 0
    )
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["2026-11-13-alex.eml"]  # only alex has an email brief
    assert main(["brief", "--demo", "--person", "nobody"]) == 2


async def test_unknown_language_falls_back_to_english(cfg: Any) -> None:
    from agentic_pm.briefs.summary import style_for

    d = await brief(cfg, "alex")
    d.language = "fr"
    assert render_text(d).startswith("Good morning, Alex!")
    assert "'fr'" in style_for("fr")
    assert "Du" in style_for("de-AT")
