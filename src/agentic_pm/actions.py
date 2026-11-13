"""Permission & Audit Guard: the only way the agent changes a tracker.

* Low-risk writes run right away, with the audit footer.
* Medium/high-risk changes become signed approval requests (see approvals.py):
  the task owner (medium) or the leads (high) get a friendly message with a
  link to the control plane; a short "waiting for OK" comment goes on the ticket.
* Approving re-checks the live task, so stale or repeated approvals never
  apply anything blindly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from agentic_pm.adapters.base import (
    AuditMeta,
    ReadOnlyAdapterError,
    Task,
    TaskPatch,
    TaskRef,
    TrackerAdapter,
)
from agentic_pm.approvals import DEFAULT_TTL, ApprovalRequest, Signer, snapshot
from agentic_pm.audit import AUDIT_MARKER, RiskTier, classify_patch, is_allowed
from agentic_pm.config.team import TeamConfig
from agentic_pm.messages import describe_patch, render
from agentic_pm.notify import Notifier


class Outcome(BaseModel):
    applied: bool
    tier: RiskTier
    status: str  # applied | pending | stale | declined | already_declined
    task: Task | None = None
    waiting_for: list[str] = []
    message: str = ""


class StaleApproval(RuntimeError):
    pass


class Guard:
    def __init__(
        self,
        cfg: TeamConfig,
        adapter: TrackerAdapter,
        notifier: Notifier,
        signer: Signer | None = None,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        self.cfg = cfg
        self.adapter = adapter
        self.notifier = notifier
        self.signer = signer
        self.ttl = ttl

    # ---------------------------------------------------------------- helpers

    def _approvers(self, task: Task, tier: RiskTier) -> list[str]:
        leads = list(self.cfg.project.leads)
        if tier is RiskTier.HIGH:
            return leads
        owners = [h for login in task.assignees if (h := self.cfg.handle_for_login(login))]
        return owners or leads

    def approval_url(self, token: str) -> str:
        base = (self.cfg.project.control_plane_url or "http://localhost:8787").rstrip("/")
        return f"{base}/approve?t={token}"

    def _names(self, handles: list[str]) -> str:
        return ", ".join(self.cfg.display_name(h) for h in handles)

    # ----------------------------------------------------------------- writes

    def _require_writes(self) -> None:
        if not self.adapter.capabilities.writes:
            raise ReadOnlyAdapterError(
                "writes are disabled for this project (set project.allow_writes: true)"
            )

    async def comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None:
        """Low-risk: always allowed (if the project allows writes), always audited."""
        self._require_writes()
        await self.adapter.add_comment(ref, markdown, meta)

    async def propose(
        self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta, *, owner_confirmed: bool = False
    ) -> Outcome:
        self._require_writes()
        task = await self.adapter.get_task(ref)
        tier = classify_patch(task, patch)
        if is_allowed(tier, meta, owner_confirmed=owner_confirmed):
            updated = await self.adapter.update_fields(ref, patch, meta)
            return Outcome(applied=True, tier=tier, status="applied", task=updated)
        if self.signer is None:
            raise RuntimeError("approvals need AGENT_PM_SIGNING_KEY")

        approvers = self._approvers(task, tier)
        exp = self.signer.now() + self.ttl
        before = snapshot(task, patch)
        request = None
        for handle in approvers:
            request = ApprovalRequest(
                ref=ref,
                patch=patch,
                before=before,
                tier=tier.value,
                reason=meta.reason,
                actor=meta.actor,
                channel=meta.channel,
                approver=handle,
                exp=exp,
            )
            lang = self.cfg.language_of(handle)
            change, short = describe_patch(task, patch, lang)
            await self.notifier.notify(
                handle,
                render(lang, "approval_subject", change_short=short, id=ref.id, title=task.title),
                render(
                    lang,
                    "approval_body",
                    name=self.cfg.display_name(handle),
                    actor=self.cfg.display_name(meta.actor)
                    if meta.actor in self.cfg.people
                    else meta.actor,
                    change=change,
                    id=ref.id,
                    title=task.title,
                    reason=meta.reason,
                    why_tier=render(lang, f"why_{tier.value}"),
                    url=self.approval_url(self.signer.sign(request)),
                    expires=datetime.fromtimestamp(exp, UTC).strftime("%Y-%m-%d %H:%M UTC"),
                ),
                ref=ref,
            )
        if self.adapter.capabilities.writes and request is not None:
            lang = self.cfg.project.ticket_language
            change, _ = describe_patch(task, patch, lang)
            await self.adapter.add_comment(
                ref,
                render(lang, "pending_comment", change=change, names=self._names(approvers)),
                meta.model_copy(update={"request_id": request.request_id}),
            )
        return Outcome(applied=False, tier=tier, status="pending", task=task, waiting_for=approvers)

    async def decide(self, token: str, approve: bool) -> Outcome:
        """Apply (or decline) a signed request after re-checking the live task."""
        if self.signer is None:
            raise RuntimeError("approvals need AGENT_PM_SIGNING_KEY")
        req = self.signer.verify(token)
        task = await self.adapter.get_task(req.ref)
        tier = RiskTier(req.tier)
        lang = self.cfg.project.ticket_language
        name = self.cfg.display_name(req.approver)
        reason = req.reason
        if approve:
            reason = f"{req.reason} ({render(lang, 'approved_comment', name=name)})"
        meta = AuditMeta(
            actor=req.actor,
            channel=req.channel,
            reason=reason,
            approved_by=req.approver if approve else None,
            request_id=req.request_id,
        )
        if not approve:
            marker = f'"request_id": "{req.request_id}"'
            if any(
                AUDIT_MARKER in c.body and marker in c.body for c in task.comments if "🙅" in c.body
            ):
                return Outcome(applied=False, tier=tier, status="already_declined", task=task)
            change, _ = describe_patch(task, req.patch, lang)
            if self.adapter.capabilities.writes:
                await self.adapter.add_comment(
                    req.ref, render(lang, "declined_comment", name=name, change=change), meta
                )
            return Outcome(applied=False, tier=tier, status="declined", task=task)
        if snapshot(task, req.patch) != req.before:
            return Outcome(
                applied=False,
                tier=tier,
                status="stale",
                task=task,
                message="The task changed since this was proposed (or it was already applied).",
            )
        updated = await self.adapter.update_fields(req.ref, req.patch, meta)
        return Outcome(applied=True, tier=tier, status="applied", task=updated)
