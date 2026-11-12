"""Adapter registry: built-in adapters plus plugins via entry points.

A third-party package can add a tracker without touching this repository:

    # pyproject.toml of the plugin
    [project.entry-points."agentic_pm.adapters"]
    youtrack = "agentic_pm_youtrack:build"

where `build(project, env) -> TrackerAdapter`. Secrets come from `env` only.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from agentic_pm.adapters.base import TrackerAdapter
from agentic_pm.adapters.catalog import load_catalog

if TYPE_CHECKING:
    from agentic_pm.config.team import Project

AdapterFactory = Callable[["Project", Mapping[str, str]], TrackerAdapter]
ENTRY_POINT_GROUP = "agentic_pm.adapters"
REPO_URL = "https://github.com/Wieshof/agentic-pm"


class AdapterConfigError(ValueError):
    pass


def _github(project: Project, env: Mapping[str, str]) -> TrackerAdapter:
    from agentic_pm.adapters.github import GitHubAdapter
    from agentic_pm.ingress import WebhookGate

    return GitHubAdapter(
        token=env.get("AGENT_PM_GITHUB_TOKEN") or env.get("GITHUB_TOKEN"),
        api_url=project.base_url or "https://api.github.com",
        gate=WebhookGate(agent_accounts=project.agent_accounts),
    )


def _openproject(project: Project, env: Mapping[str, str]) -> TrackerAdapter:
    from agentic_pm.adapters.openproject import OpenProjectAdapter

    if not project.base_url:
        raise AdapterConfigError("project.base_url is required for OpenProject")
    return OpenProjectAdapter(project.base_url, api_key=env.get("OPENPROJECT_API_KEY"))


_BUILTIN: dict[str, AdapterFactory] = {"github": _github, "openproject": _openproject}
_registered: dict[str, AdapterFactory] = {}


def register(key: str, factory: AdapterFactory) -> None:
    """Register an adapter at runtime (tests, embedding applications)."""
    _registered[key] = factory


def _plugins() -> dict[str, AdapterFactory]:
    found: dict[str, AdapterFactory] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        found[ep.name] = ep.load()
    return found


def factories() -> dict[str, AdapterFactory]:
    return {**_BUILTIN, **_plugins(), **_registered}


def known_trackers() -> set[str]:
    """Every tracker name team.yaml may use: catalog entries plus plugins."""
    return set(load_catalog()) | set(_plugins()) | set(_registered)


def build_adapter(project: Project, env: Mapping[str, str] | None = None) -> TrackerAdapter:
    env = os.environ if env is None else env
    available = factories()
    if project.tracker in available:
        return available[project.tracker](project, env)
    entry = load_catalog().get(project.tracker)
    if entry is not None:
        where = f" (see {REPO_URL}/issues/{entry.issue})" if entry.issue else ""
        raise AdapterConfigError(
            f"Support for {entry.name} is {entry.status} but not built yet{where}. "
            "Contributions are very welcome, see docs/trackers.md."
        )
    raise AdapterConfigError(f"unknown tracker '{project.tracker}'")
