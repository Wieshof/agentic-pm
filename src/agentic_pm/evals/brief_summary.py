"""Eval for the brief summary: run every case against a local model and grade it.

    agent-pm eval --model qwen3.5

Deterministic graders only (no LLM judge), so results are cheap and repeatable:
valid JSON, the guard in `briefs.summary.check_summary`, and that the most
important task numbers are actually mentioned.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agentic_pm.briefs.summary import generate_summary
from agentic_pm.llm import OpenAICompatibleProvider

DEFAULT_CASES = Path(__file__).with_name("brief_summary_cases.yaml")


@dataclass
class Result:
    case_id: str
    passed: bool
    seconds: float
    summary: str | None
    problems: list[str] = field(default_factory=list)


def load_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = yaml.safe_load(
        Path(path or DEFAULT_CASES).read_text(encoding="utf-8")
    )
    return cases


def grade(case: dict[str, Any], summary: str | None, problems: list[str]) -> list[str]:
    if summary is None:
        if not problems and not case.get("expect_summary", True):
            return []  # correctly skipped (quiet day)
        return problems or ["no summary"]
    if not case.get("expect_summary", True):
        return ["expected no summary on a quiet day"]
    found = list(problems)
    missing = [n for n in case.get("must_mention", []) if n not in summary]
    if missing:
        found.append(f"missing {missing}")
    return found


async def run_case(provider: OpenAICompatibleProvider, case: dict[str, Any]) -> Result:
    start = time.perf_counter()
    summary, problems = await generate_summary(provider, case["facts"], case["language"])
    found = grade(case, summary, problems)
    return Result(case["id"], not found, time.perf_counter() - start, summary, found)


async def run(
    model: str, base_url: str, reasoning_effort: str | None, cases_path: str | None
) -> int:
    provider = OpenAICompatibleProvider(
        model=model,
        base_url=base_url,
        reasoning_effort=None if reasoning_effort in (None, "", "default") else reasoning_effort,
    )
    cases = load_cases(cases_path)
    results = [await run_case(provider, c) for c in cases]
    await provider.aclose()
    passed = sum(r.passed for r in results)
    print(f"Model {model} · reasoning_effort={reasoning_effort} · {passed}/{len(results)} passed\n")
    for r in results:
        mark = "✅" if r.passed else "❌"
        print(f"{mark} {r.case_id} ({r.seconds:.1f}s)")
        if r.summary:
            print(f"   {r.summary}")
        for p in r.problems:
            print(f"   ↳ {p}")
    return 0 if passed == len(results) else 1
