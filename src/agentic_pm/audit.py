"""Permission tiers and audit trail (docs/guardrails.md)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
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
    """Whether a write can proceed immediately without a separate approval flow.

    - LOW: always allowed (runs automatically, audited).
    - MEDIUM: allowed only if confirmed by the task owner in-channel.
    - HIGH: always requires cryptographic lead approval (cannot proceed immediately).
    """
    if tier is RiskTier.LOW:
        return True
    if tier is RiskTier.MEDIUM:
        return owner_confirmed
    return False


AUDIT_MARKER = "agent-pm-audit"

AUDIT_FOOTER_PATTERN = re.compile(
    r"<!--\s*" + re.escape(AUDIT_MARKER) + r"\s+(?P<body>.+?)\s*-->",
    re.DOTALL,
)


def render_audit_footer(meta: AuditMeta, signing_key: str | bytes | None = None) -> str:
    """Machine-readable footer appended to every agent-written comment."""
    payload = json.dumps(meta.model_dump(mode="json", exclude_none=True), sort_keys=True)
    # Escape angle brackets so free text (e.g. a reason containing "-->") can never
    # close the HTML comment early and smuggle visible Markdown into the ticket.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    key = signing_key if signing_key is not None else os.environ.get("AGENT_PM_SIGNING_KEY")
    if key:
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key
        sig = hmac.new(key_bytes, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"<!-- {AUDIT_MARKER} {payload} sig={sig} -->"
    return f"<!-- {AUDIT_MARKER} {payload} -->"


def extract_audit_footer(
    text: str | None, signing_key: str | bytes | None = None
) -> AuditMeta | None:
    """Extract and verify an AuditMeta from `text` if signed with `signing_key`."""
    if not text:
        return None
    key = signing_key if signing_key is not None else os.environ.get("AGENT_PM_SIGNING_KEY")
    if not key:
        return None
    key_bytes = key.encode("utf-8") if isinstance(key, str) else key
    for match in AUDIT_FOOTER_PATTERN.finditer(text):
        body = match.group("body").strip()
        if " sig=" not in body:
            continue
        payload, sig = body.rsplit(" sig=", 1)
        payload = payload.strip()
        sig = sig.strip()
        if len(sig) != 64:
            continue
        expected_sig = hmac.new(key_bytes, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig.lower(), expected_sig.lower()):
            try:
                data = json.loads(payload)
                return AuditMeta.model_validate(data)
            except Exception:
                continue
    return None


def verify_audit_footer(text: str | None, signing_key: str | bytes | None = None) -> bool:
    """Verify whether `text` contains a cryptographically signed agent audit footer."""
    return extract_audit_footer(text, signing_key) is not None


def audit_meta_in(text: str | None, signing_key: str | bytes | None = None) -> AuditMeta | None:
    """The agent's own audit metadata in `text`, for reading state back from a ticket.

    With a signing key (argument or `AGENT_PM_SIGNING_KEY`) only a verified footer
    counts, so nobody can fake "already asked" or "already declined" by pasting a
    footer. Without a key, signatures can't be checked and the unsigned footer is
    read as before.
    """
    key = signing_key if signing_key is not None else os.environ.get("AGENT_PM_SIGNING_KEY")
    if key:
        return extract_audit_footer(text, key)
    for match in AUDIT_FOOTER_PATTERN.finditer(text or ""):
        payload = match.group("body").strip().rsplit(" sig=", 1)[0]
        try:
            return AuditMeta.model_validate(json.loads(payload))
        except ValueError:
            continue
    return None
