"""`agent-pm` command line."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from agentic_pm.adapters.base import TrackerAdapter
from agentic_pm.config import json_schema, load_team_config
from agentic_pm.config.team import BriefFormat, TeamConfig

EXAMPLE_CONFIG = ".agent-pm/team.example.yaml"


def _validate(path: str) -> int:
    try:
        cfg = load_team_config(path)
    except FileNotFoundError:
        print(f"✗ {path}: file not found", file=sys.stderr)
        return 2
    except ValidationError as e:
        print(f"✗ {path}: {e.error_count()} problem(s)", file=sys.stderr)
        for err in e.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(root)"
            msg = err["msg"]
            if err["type"] == "string_type" and isinstance(err.get("input"), int):
                msg += ' (hint: quote times in YAML, e.g. "08:00")'
            print(f"  - {loc}: {msg}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"✗ {path}: {e}", file=sys.stderr)
        return 1
    print(f"✓ {path}: {len(cfg.people)} people, tracker={cfg.project.tracker}")
    return 0


def _load(args: argparse.Namespace) -> tuple[TeamConfig, date]:
    path = args.config or (EXAMPLE_CONFIG if args.demo else ".agent-pm/team.yaml")
    today = date.fromisoformat(args.date) if args.date else date.today()
    return load_team_config(path), today


def _adapter(cfg: TeamConfig, args: argparse.Namespace, today: date) -> TrackerAdapter:
    if args.demo:
        from agentic_pm.demo import demo_tracker

        return demo_tracker(cfg.project.repo, today)
    from agentic_pm.adapters.factory import build_adapter

    return build_adapter(cfg.project)


async def _deps(args: argparse.Namespace) -> int:
    from agentic_pm.engine import DependencyGraph

    cfg, today = _load(args)
    graph = await DependencyGraph.build(_adapter(cfg, args, today), cfg.project.repo)
    risks = graph.risks(today)
    print(f"{len(graph.tasks)} open tasks · {len(risks)} at risk · {len(graph.cycles())} cycle(s)")
    for r in risks:
        print(
            f"  ⚠️  #{r.task.ref.id} {r.task.title}: {r.days_late} day(s) late "
            f"(blocker #{r.blocker.ref.id} {r.blocker.title}, {r.reason}); "
            f"suggest {r.proposed_due}"
        )
    for c in graph.cycles():
        print("  🔁 " + " → ".join(f"#{ref.id}" for ref in c))
    return 0


async def _brief(args: argparse.Namespace) -> int:
    from agentic_pm.briefs import build_email, collect, render_html, render_text
    from agentic_pm.engine import DependencyGraph

    cfg, today = _load(args)
    if args.all:
        handles = [
            h for h, p in cfg.people.items() if p.brief and p.brief.format is BriefFormat.EMAIL
        ]
    elif args.person:
        handles = [args.person]
    else:
        print("✗ pass --person HANDLE or --all", file=sys.stderr)
        return 2
    unknown = [h for h in handles if h not in cfg.people]
    if unknown:
        print(f"✗ unknown person(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    adapter = _adapter(cfg, args, today)
    graph = await DependencyGraph.build(adapter, cfg.project.repo)
    provider = None
    if args.llm:
        from agentic_pm.llm import provider_from_settings

        provider = provider_from_settings(cfg.llm)

    for handle in handles:
        data = await collect(cfg, handle, adapter, today, graph)
        summary = None
        if provider is not None:
            from agentic_pm.briefs.summary import generate_summary, summary_facts

            raw, problems = await generate_summary(provider, summary_facts(data), data.language)
            summary = None if problems else raw
            if problems:
                print(
                    f"note: {handle}: LLM summary skipped ({'; '.join(problems)})", file=sys.stderr
                )
        email = cfg.people[handle].channels.email
        if args.send or args.format == "eml":
            from agentic_pm.briefs import smtp

            if not email:
                print(f"✗ {handle} has no email channel", file=sys.stderr)
                return 1
            msg = build_email(data, to=email, sender=smtp.sender_address(), summary=summary)
            if args.send:
                smtp.send(msg)
                print(f"✓ sent brief to {handle}")
                continue
            out = msg.as_string()
        elif args.format == "html":
            out = render_html(data, summary)
        else:
            out = render_text(data, summary)
        if args.out:
            Path(args.out).mkdir(parents=True, exist_ok=True)
            ext = {"text": "txt", "html": "html", "eml": "eml"}[args.format]
            target = Path(args.out) / f"{today.isoformat()}-{handle}.{ext}"
            target.write_text(out, encoding="utf-8")
            print(f"✓ wrote {target}")
        else:
            print(out)
    return 0


def _eval(args: argparse.Namespace) -> int:
    from agentic_pm.evals.brief_summary import run

    return asyncio.run(run(args.model, args.base_url, args.reasoning_effort, args.cases))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-pm")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a team.yaml file")
    v.add_argument("path", nargs="?", default=".agent-pm/team.yaml")
    sub.add_parser("schema", help="print the team.yaml JSON Schema")
    sub.add_parser("mcp", help="run the tracker MCP server (stdio) against demo data")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", help="team.yaml (default .agent-pm/team.yaml)")
        p.add_argument("--date", help="pretend today is YYYY-MM-DD")
        p.add_argument("--demo", action="store_true", help="use built-in demo data")

    d = sub.add_parser("deps", help="show dependency risks and cycles")
    common(d)
    b = sub.add_parser("brief", help="render (or send) morning briefs")
    common(b)
    who = b.add_mutually_exclusive_group()
    who.add_argument("--person", help="team handle")
    who.add_argument("--all", action="store_true", help="everyone with an email brief")
    b.add_argument("--format", choices=["text", "html", "eml"], default="text")
    b.add_argument("--out", help="write files to this directory instead of stdout")
    b.add_argument("--llm", action="store_true", help="add a short summary from the local LLM")
    b.add_argument("--send", action="store_true", help="send via SMTP (AGENT_PM_SMTP_* env)")
    e = sub.add_parser("eval", help="evaluate the brief summary against a local model")
    e.add_argument("--model", required=True)
    e.add_argument("--base-url", default="http://localhost:11434/v1")
    e.add_argument("--reasoning-effort", default="none")
    e.add_argument("--cases", help="YAML file with cases (default: built-in set)")

    args = parser.parse_args(argv)
    if args.cmd == "validate":
        return _validate(args.path)
    if args.cmd == "schema":
        print(json.dumps(json_schema(), indent=2))
        return 0
    if args.cmd == "mcp":
        from agentic_pm.mcp_server import run_demo

        run_demo()
        return 0
    if args.cmd == "deps":
        return asyncio.run(_deps(args))
    if args.cmd == "brief":
        return asyncio.run(_brief(args))
    if args.cmd == "eval":
        return _eval(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
