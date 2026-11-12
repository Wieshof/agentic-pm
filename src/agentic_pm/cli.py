"""`agent-pm` command line."""

from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from agentic_pm.config import json_schema, load_team_config


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-pm")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a team.yaml file")
    v.add_argument("path", nargs="?", default=".agent-pm/team.yaml")
    sub.add_parser("schema", help="print the team.yaml JSON Schema")
    sub.add_parser("mcp", help="run the tracker MCP server (stdio) against the demo tracker")
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
