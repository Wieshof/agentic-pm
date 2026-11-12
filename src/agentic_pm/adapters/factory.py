"""Build the configured tracker adapter. Secrets come from the environment only."""

from __future__ import annotations

import os

from agentic_pm.adapters.base import TrackerAdapter
from agentic_pm.config.team import Project, Tracker


class AdapterConfigError(ValueError):
    pass


def build_adapter(project: Project, env: dict[str, str] | None = None) -> TrackerAdapter:
    env = dict(os.environ) if env is None else env
    if project.tracker == Tracker.GITHUB:
        from agentic_pm.adapters.github import GitHubAdapter

        token = env.get("AGENT_PM_GITHUB_TOKEN") or env.get("GITHUB_TOKEN")
        return GitHubAdapter(token=token, api_url=project.base_url or "https://api.github.com")
    if project.tracker == Tracker.OPENPROJECT:
        from agentic_pm.adapters.openproject import OpenProjectAdapter

        if not project.base_url:
            raise AdapterConfigError("project.base_url is required for OpenProject")
        return OpenProjectAdapter(project.base_url, api_key=env.get("OPENPROJECT_API_KEY"))
    raise AdapterConfigError(f"tracker '{project.tracker}' has no adapter yet")
