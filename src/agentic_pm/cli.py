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
    from agentic_pm.briefs.morning import base_language

    for handle, person in cfg.people.items():
        if base_language(person.language) != person.language.split("-")[0]:
            print(
                f"  note: {handle} speaks '{person.language}'; briefs use English templates "
                "for now (the optional LLM summary is written in their language)"
            )
    if not cfg.project.agent_accounts:
        print(
            "  note: project.agent_accounts is empty; set it before the agent writes to the tracker"
        )
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


REPO_URL = "https://github.com/Wieshof/agentic-pm"
TRACKER_DOCS = {"en": Path("docs/trackers.md"), "de": Path("docs/de/trackers.md")}


def _trackers(args: argparse.Namespace) -> int:
    from agentic_pm.adapters.catalog import load_catalog, render_matrix, replace_matrix

    if args.write_docs or args.check_docs:
        stale = []
        for lang, path in TRACKER_DOCS.items():
            doc = path.read_text(encoding="utf-8")
            new = replace_matrix(doc, render_matrix(lang, REPO_URL))  # type: ignore[arg-type]
            if new != doc:
                stale.append(str(path))
                if args.write_docs:
                    path.write_text(new, encoding="utf-8")
        if args.check_docs and stale:
            print(f"✗ outdated: {', '.join(stale)} (run agent-pm trackers --write-docs)")
            return 1
        print(f"✓ tracker matrix {'written' if args.write_docs else 'up to date'}")
        return 0
    entries = sorted(load_catalog().values(), key=lambda e: (e.status != "available", e.tier))
    for e in entries:
        if args.tier and e.tier != args.tier:
            continue
        mark = {"available": "✅", "planned": "🗓️ ", "candidate": "💡"}[e.status]
        issue = f"  #{e.issue}" if e.issue else ""
        print(
            f"{mark} {e.key:<16} tier {e.tier}  deps={e.dependencies:<10} "
            f"events={e.events:<8} {e.name}{issue}"
        )
    return 0


async def _run(args: argparse.Namespace) -> int:
    from agentic_pm.notify import RecordingNotifier
    from agentic_pm.runtime import build_runtime

    cfg, today = _load(args)
    adapter = _adapter(cfg, args, today)
    rt = build_runtime(cfg, adapter, dry_run=args.dry_run, use_llm=not args.no_llm)
    if args.once:
        result = await rt.run_once(args.once)
        if isinstance(rt.notifier, RecordingNotifier):
            for m in rt.notifier.sent:
                print(f"--- to {m.handle}: {m.subject}\n{m.text}\n")
        print(f"✓ {args.once}: {result}")
        return 0
    jobs = rt.jobs()
    print(f"agent-pm running: {len(jobs)} scheduled job(s), web on :{args.port}")
    for j in jobs:
        print(f"  • {j.name} ({j.spec}, {cfg.project.timezone})")
    await rt.serve(port=args.port)
    return 0


async def _onboarding(args: argparse.Namespace) -> int:
    from agentic_pm.messages import onboarding
    from agentic_pm.notify import EmailNotifier

    cfg, _ = _load(args)
    handles = list(cfg.people) if args.all else [args.person]
    for handle in handles:
        if handle not in cfg.people:
            print(f"✗ unknown person: {handle}", file=sys.stderr)
            return 2
        subject, text = onboarding(cfg, handle)
        if args.send:
            ok = await EmailNotifier(cfg).notify(handle, subject, text)
            print(f"{'✓ sent to' if ok else '✗ no email channel for'} {handle}")
        else:
            print(f"--- {handle}: {subject}\n{text}\n")
    return 0


def _eval(args: argparse.Namespace) -> int:
    if args.suite == "knowledge":
        from agentic_pm.evals.knowledge import run as run_knowledge

        return asyncio.run(
            run_knowledge(args.model, args.base_url, args.reasoning_effort, args.cases)
        )
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
    r = sub.add_parser("run", help="run the agent: cadence, approvals web, webhooks, inbox")
    common(r)
    r.add_argument(
        "--once",
        choices=["briefs", "end_of_day", "weekly_digest", "monthly_health_check", "inbox"],
        help="run one job now and exit (for cron)",
    )
    r.add_argument("--dry-run", action="store_true", help="print messages instead of sending")
    r.add_argument("--no-llm", action="store_true", help="skip the local model")
    r.add_argument("--port", type=int, default=8787)
    o = sub.add_parser("onboarding", help="friendly intro message: what the agent does with data")
    common(o)
    ow = o.add_mutually_exclusive_group(required=True)
    ow.add_argument("--person")
    ow.add_argument("--all", action="store_true")
    o.add_argument("--send", action="store_true", help="send by email instead of printing")
    t = sub.add_parser("trackers", help="list supported and planned trackers")
    t.add_argument("--tier", type=int, choices=[1, 2, 3])
    t.add_argument("--write-docs", action="store_true", help="update the matrix in docs/")
    t.add_argument("--check-docs", action="store_true", help="fail if docs are outdated")
    e = sub.add_parser("eval", help="evaluate the brief summary against a local model")
    e.add_argument("--model", required=True)
    e.add_argument("--suite", choices=["brief", "knowledge"], default="brief")
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
    if args.cmd == "onboarding":
        return asyncio.run(_onboarding(args))
    if args.cmd == "run":
        return asyncio.run(_run(args))
    if args.cmd == "trackers":
        return _trackers(args)
    if args.cmd == "eval":
        return _eval(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
