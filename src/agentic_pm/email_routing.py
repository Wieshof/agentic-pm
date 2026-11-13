"""Conversation-to-ticket routing for email, without a lookup table.

Outbound mail about a task gets
* a `Reply-To` plus-address:  pm+142@acme.com
* a `Message-ID` that encodes the task:  <agent-pm.github.acme%2Fapp.142.1a2b3c4d@acme.com>

A reply then carries its ticket in the `To` address or in `In-Reply-To` /
`References`, whichever survives the mail client. See docs/data-model.md.
"""

from __future__ import annotations

import re
import secrets
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from html import unescape
from urllib.parse import quote, unquote

from pydantic import BaseModel

from agentic_pm.adapters.base import TaskRef
from agentic_pm.config.team import TeamConfig

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_MSGID = re.compile(r"<agent-pm\.([a-z0-9_-]+)\.([^.\s<>@]+)\.([A-Za-z0-9_-]+)\.[0-9a-f]{8}@[^>]+>")
_QUOTE_HEADER = re.compile(
    r"^\s*(On .{0,200} wrote:|Am .{0,200} schrieb .{0,200}:|-----\s*Original Message|"
    r"-----\s*Ursprüngliche Nachricht|From: .+|Von: .+)\s*$",
    re.I,
)
_TAGS = re.compile(r"<[^>]+>")


def _domain(agent_email: str) -> str:
    return agent_email.rsplit("@", 1)[1]


def _enc(project: str) -> str:
    return quote(project, safe="").replace(".", "%2E")


def make_message_id(ref: TaskRef, agent_email: str) -> str:
    return (
        f"<agent-pm.{ref.tracker}.{_enc(ref.project)}.{ref.id}."
        f"{secrets.token_hex(4)}@{_domain(agent_email)}>"
    )


def task_address(agent_email: str, ref: TaskRef) -> str | None:
    """pm@acme.com + #142 -> pm+142@acme.com (None if the id can't be encoded safely)."""
    if not _SAFE_ID.match(ref.id):
        return None
    local, domain = agent_email.split("@", 1)
    return f"{local.split('+')[0]}+{ref.id}@{domain}"


def ref_from_address(address: str, cfg: TeamConfig) -> TaskRef | None:
    agent = cfg.project.agent_email
    if not agent:
        return None
    a_local, a_domain = agent.lower().split("@", 1)
    _, addr = parseaddr(address)
    if "@" not in addr:
        return None
    local, domain = addr.split("@", 1)
    if domain.lower() != a_domain or "+" not in local:
        return None
    base, tag = local.split("+", 1)
    if base.lower() != a_local.split("+")[0] or not _SAFE_ID.match(tag):
        return None
    return TaskRef(tracker=cfg.project.tracker, project=cfg.project.repo, id=tag)


def ref_from_message_ids(header: str) -> TaskRef | None:
    for m in _MSGID.finditer(header or ""):
        return TaskRef(tracker=m.group(1), project=unquote(m.group(2)), id=m.group(3))
    return None


def strip_reply(text: str) -> str:
    """Keep only what the person wrote: drop quoted history and signatures."""
    out: list[str] = []
    for line in text.splitlines():
        if line.strip() == "--" or line.startswith("-- ") or _QUOTE_HEADER.match(line):
            break
        if line.lstrip().startswith(">"):
            continue
        out.append(line)
    return "\n".join(out).strip()


def body_text(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_type() == "text/html":
        content = unescape(_TAGS.sub(" ", content))
    return str(content)


class InboundMessage(BaseModel):
    sender: str
    handle: str | None
    ref: TaskRef | None
    subject: str
    text: str
    message_id: str | None


def parse_inbound(raw: bytes, cfg: TeamConfig) -> InboundMessage:
    msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw)
    sender = parseaddr(str(msg.get("From", "")))[1].lower()
    ref: TaskRef | None = None
    for header in ("To", "Cc", "Delivered-To", "X-Original-To"):
        for _, addr in getaddresses([str(v) for v in msg.get_all(header, [])]):
            ref = ref or ref_from_address(addr, cfg)
    if ref is None:
        ids = " ".join(str(msg.get(h, "")) for h in ("In-Reply-To", "References"))
        ref = ref_from_message_ids(ids)
    if ref is None:  # "#142" in the subject as a last resort
        m = re.search(r"#([A-Za-z0-9_-]+)", str(msg.get("Subject", "")))
        if m:
            ref = TaskRef(tracker=cfg.project.tracker, project=cfg.project.repo, id=m.group(1))
    return InboundMessage(
        sender=sender,
        handle=cfg.handle_for_email(sender),
        ref=ref,
        subject=str(msg.get("Subject", "")),
        text=strip_reply(body_text(msg)),
        message_id=str(msg.get("Message-ID")) if msg.get("Message-ID") else None,
    )
