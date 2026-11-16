"""Webhook gate: self-trigger protection and de-duplication, without a database.

Every write the agent makes (a comment, a how-to section) makes the tracker
fire a webhook straight back. Without a filter, the agent would react to its
own change, write again, and loop. Trackers also retry deliveries and send
bursts of events for one ticket (edit + label + assign within seconds).

`WebhookGate.admit()` decides per delivery, in this order:

1. **duplicate_delivery** - the same delivery id (e.g. `X-GitHub-Delivery`)
   was already seen within `dedup_ttl` seconds.
2. **self_authored** - the sender is one of the agent's service accounts, or
   the text carries the agent's cryptographically signed audit footer (`agentic_pm.audit`).
3. **coalesced** - an event of the same kind for the same ticket was admitted
   less than `coalesce_window` seconds ago.

Dropping (2) and (3) loses nothing: the agent is stateless and fetches the
live ticket on every admitted event anyway. All memory is process-local and
bounded (oldest entries are evicted), so a restart simply starts fresh.
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from agentic_pm.audit import verify_audit_footer


class _ExpiringSet:
    """Keys that expire after `ttl` seconds; never holds more than `max_entries`."""

    def __init__(self, ttl: float, max_entries: int, clock: Callable[[], float]) -> None:
        self.ttl = ttl
        self.max_entries = max_entries
        self._clock = clock
        self._items: OrderedDict[str, float] = OrderedDict()

    def _evict(self, now: float) -> None:
        while self._items:
            _key, seen = next(iter(self._items.items()))
            if now - seen < self.ttl and len(self._items) <= self.max_entries:
                break
            self._items.popitem(last=False)

    def seen_recently(self, key: str) -> bool:
        now = self._clock()
        self._evict(now)
        return key in self._items

    def add(self, key: str) -> None:
        now = self._clock()
        self._items[key] = now
        self._items.move_to_end(key)
        self._evict(now)

    def __len__(self) -> int:
        return len(self._items)


@dataclass(frozen=True)
class Decision:
    admitted: bool
    reason: str  # "admitted" | "duplicate_delivery" | "self_authored" | "coalesced"


def is_self_authored(
    actor: str | None,
    text: str | None,
    agent_accounts: Iterable[str],
    signing_key: str | bytes | None = None,
) -> bool:
    accounts = {a.lower() for a in agent_accounts}
    if actor and actor.lower() in accounts:
        return True
    if not text:
        return False
    return verify_audit_footer(text, signing_key=signing_key)


class WebhookGate:
    def __init__(
        self,
        agent_accounts: Iterable[str] = (),
        dedup_ttl: float = 3600.0,
        coalesce_window: float = 10.0,
        max_entries: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
        signing_key: str | bytes | None = None,
    ) -> None:
        self.agent_accounts = tuple(agent_accounts)
        self.signing_key = (
            signing_key if signing_key is not None else os.environ.get("AGENT_PM_SIGNING_KEY")
        )
        self._deliveries = _ExpiringSet(dedup_ttl, max_entries, clock)
        self._recent = _ExpiringSet(coalesce_window, max_entries, clock)

    def admit(
        self,
        *,
        ticket: str,
        kind: str,
        delivery_id: str | None = None,
        actor: str | None = None,
        text: str | None = None,
    ) -> Decision:
        if delivery_id:
            if self._deliveries.seen_recently(delivery_id):
                return Decision(False, "duplicate_delivery")
            self._deliveries.add(delivery_id)
        if is_self_authored(actor, text, self.agent_accounts, signing_key=self.signing_key):
            return Decision(False, "self_authored")
        key = f"{ticket}|{kind}"
        if self._recent.seen_recently(key):
            return Decision(False, "coalesced")
        self._recent.add(key)
        return Decision(True, "admitted")
