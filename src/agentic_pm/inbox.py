"""IMAP inbox for the agent's mailbox (e.g. pm@acme.com, incl. pm+<id>@ aliases).

Environment only: AGENT_PM_IMAP_HOST, AGENT_PM_IMAP_PORT (993),
AGENT_PM_IMAP_USER, AGENT_PM_IMAP_PASSWORD, AGENT_PM_IMAP_FOLDER (INBOX).

Messages are read with BODY.PEEK and only marked as seen after they were
handled, so a crash never loses a reply. Process memory holds nothing.
"""

from __future__ import annotations

import asyncio
import imaplib
import os
from collections.abc import Callable
from typing import Any

from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import parse_inbound
from agentic_pm.inbound import Router


class InboxConfigError(ValueError):
    pass


class ImapInbox:
    def __init__(
        self,
        env: dict[str, str] | None = None,
        connect: Callable[[str, int], Any] = imaplib.IMAP4_SSL,
    ) -> None:
        env = dict(os.environ) if env is None else env
        self.host = env.get("AGENT_PM_IMAP_HOST", "")
        if not self.host:
            raise InboxConfigError("AGENT_PM_IMAP_HOST is not set")
        self.port = int(env.get("AGENT_PM_IMAP_PORT", "993"))
        self.user = env.get("AGENT_PM_IMAP_USER", "")
        self.password = env.get("AGENT_PM_IMAP_PASSWORD", "")
        self.folder = env.get("AGENT_PM_IMAP_FOLDER", "INBOX")
        self._connect = connect

    def _open(self) -> Any:
        conn = self._connect(self.host, self.port)
        conn.login(self.user, self.password)
        conn.select(self.folder)
        return conn

    def fetch_unseen(self) -> list[tuple[bytes, bytes]]:
        """[(uid, raw message)] for unseen mail, without marking it seen."""
        conn = self._open()
        try:
            _, data = conn.uid("search", None, "UNSEEN")
            uids = data[0].split() if data and data[0] else []
            out: list[tuple[bytes, bytes]] = []
            for uid in uids:
                _, parts = conn.uid("fetch", uid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if raw:
                    out.append((uid, raw))
            return out
        finally:
            conn.logout()

    def mark_seen(self, uids: list[bytes]) -> None:
        if not uids:
            return
        conn = self._open()
        try:
            conn.uid("store", b",".join(uids), "+FLAGS", "(\\Seen)")
        finally:
            conn.logout()


async def poll_once(inbox: ImapInbox, router: Router, cfg: TeamConfig) -> list[str]:
    messages = await asyncio.to_thread(inbox.fetch_unseen)
    outcomes: list[str] = []
    done: list[bytes] = []
    for uid, raw in messages:
        outcomes.append(await router.handle(parse_inbound(raw, cfg)))
        done.append(uid)
    await asyncio.to_thread(inbox.mark_seen, done)
    return outcomes
