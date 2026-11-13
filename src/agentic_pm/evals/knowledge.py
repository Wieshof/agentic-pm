"""Eval for the Knowledge Extractor (#10): classification + extraction quality.

agent-pm eval --suite knowledge --model qwen3.5
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import yaml

from agentic_pm.evals.brief_summary import Result
from agentic_pm.knowledge import analyze
from agentic_pm.llm import OpenAICompatibleProvider

DEFAULT_CASES = Path(__file__).with_name("knowledge_cases.yaml")


def load_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = yaml.safe_load(
        Path(path or DEFAULT_CASES).read_text(encoding="utf-8")
    )
    return cases


async def run_case(provider: OpenAICompatibleProvider, case: dict[str, Any]) -> Result:
    start = time.perf_counter()
    analysis, problems = await analyze(
        provider,
        case["message"],
        task_title=case["task"],
        author="Sam",
        ticket_language=case["ticket_language"],
    )
    found = list(problems)
    shown = None
    if analysis is not None:
        if analysis.kind != case["kind"]:
            found.append(f"kind {analysis.kind}, expected {case['kind']}")
        text = " ".join(
            [analysis.problem, analysis.root_cause, analysis.fix, analysis.verification]
        )
        missing = [w for w in case.get("must_contain", []) if w.lower() not in text.lower()]
        if missing:
            found.append(f"missing {missing}")
        shown = f"[{analysis.kind}] fix: {analysis.fix}" if analysis.fix else f"[{analysis.kind}]"
    return Result(case["id"], not found, time.perf_counter() - start, shown, found)


async def run(
    model: str, base_url: str, reasoning_effort: str | None, cases_path: str | None
) -> int:
    provider = OpenAICompatibleProvider(
        model=model,
        base_url=base_url,
        reasoning_effort=None if reasoning_effort in (None, "", "default") else reasoning_effort,
    )
    results = [await run_case(provider, c) for c in load_cases(cases_path)]
    await provider.aclose()
    passed = sum(r.passed for r in results)
    print(f"Knowledge extractor · {model} · {passed}/{len(results)} passed\n")
    for r in results:
        print(f"{'✅' if r.passed else '❌'} {r.case_id} ({r.seconds:.1f}s)")
        if r.summary:
            print(f"   {r.summary}")
        for p in r.problems:
            print(f"   ↳ {p}")
    return 0 if passed == len(results) else 1
