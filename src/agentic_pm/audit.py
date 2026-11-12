"""Permission tiers and audit trail (docs/guardrails.md)."""

from __future__ import annotations

import json
from enum import StrEnum

from agentic_pm.adapters.base import AuditMeta, Task, TaskPatch


class RiskTier(StrEnum):
    LOW = "low"  # runs automatically, audited
    MEDIUM = "medium"  # runs if the owner confirmed in-channel
    HIGH = "high"  # needs team-lead confirmation


def classify_patch(task: Task, patch: TaskPatch) -> RiskTier:
    """Risk tier of applying `patch` to `task`."""
    if patch.assignees is not None and sorted(patch.assignees) != sorted(task.assignees):
        return RiskTier.HIGH
    if patch.due is not None and patch.due != task.due:
        return RiskTier.HIGH if task.client_facing else RiskTier.MEDIUM
    if patch.status is not None and patch.status != task.status:
        return RiskTier.MEDIUM
    if patch.estimate_hours is not None and patch.estimate_hours != task.estimate_hours:
        return RiskTier.MEDIUM
    return RiskTier.LOW  # labels only, or no-op


def is_allowed(tier: RiskTier, meta: AuditMeta, *, owner_confirmed: bool = False) -> bool:
    if tier is RiskTier.LOW:
        return True
    if tier is RiskTier.MEDIUM:
        return owner_confirmed or meta.approved_by is not None
    return meta.approved_by is not None


AUDIT_MARKER = "agent-pm-audit"


def render_audit_footer(meta: AuditMeta) -> str:
    """Machine-readable footer appended to every agent-written comment."""
    payload = json.dumps(meta.model_dump(mode="json", exclude_none=True), sort_keys=True)
    return f"<!-- {AUDIT_MARKER} {payload} -->"
