"""Operating cadence: when the agent does what (issue #45).

Time specs (in `project.timezone`):

| Spec                 | Meaning                                       |
|----------------------|-----------------------------------------------|
| `"08:30"`            | every weekday (Mon-Fri) at 08:30              |
| `"daily 08:30"`      | every day, weekends included                  |
| `"Fri 15:00"`        | every Friday at 15:00                         |
| `"last_friday 16:00"`| last Friday of the month (time optional, 09:00) |
| `"first_monday"`     | first Monday of the month at 09:00            |
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger("agentic_pm.cadence")

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_HHMM = r"(?:[01]\d|2[0-3]):[0-5]\d"
SPEC_PATTERN = (
    rf"^(?:(?:daily|{'|'.join(d.capitalize() for d in DAYS)}) )?{_HHMM}$"
    rf"|^(?:first|last)_(?:{'|'.join(DAY_NAMES)})(?: {_HHMM})?$"
)
_SPEC = re.compile(SPEC_PATTERN)


def _time(text: str | None) -> time:
    if not text:
        return time(9, 0)
    h, m = text.split(":")
    return time(int(h), int(m))


def _nth_weekday(year: int, month: int, weekday: int, which: str) -> date:
    days = [
        date(year, month, d)
        for d in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, d).weekday() == weekday
    ]
    return days[0] if which == "first" else days[-1]


def next_run(spec: str, after: datetime) -> datetime:
    """Next occurrence strictly after `after` (aware datetime, in the wanted timezone)."""
    if not _SPEC.match(spec):
        raise ValueError(f"invalid cadence spec: {spec!r}")
    tz = after.tzinfo
    parts = spec.split()
    if "_" in parts[0]:
        which, dayname = parts[0].split("_")
        at = _time(parts[1] if len(parts) > 1 else None)
        y, m = after.year, after.month
        for _ in range(3):
            d = _nth_weekday(y, m, DAY_NAMES.index(dayname), which)
            candidate = datetime.combine(d, at, tz)
            if candidate > after:
                return candidate
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        raise AssertionError("unreachable")
    if len(parts) == 1:
        allowed, at = set(range(5)), _time(parts[0])  # weekdays
    elif parts[0] == "daily":
        allowed, at = set(range(7)), _time(parts[1])
    else:
        allowed, at = {DAYS.index(parts[0].lower())}, _time(parts[1])
    d = after.date()
    for _ in range(8):
        candidate = datetime.combine(d, at, tz)
        if d.weekday() in allowed and candidate > after:
            return candidate
        d += timedelta(days=1)
    raise AssertionError("unreachable")


@dataclass
class Job:
    name: str
    spec: str
    run: Callable[[datetime], Awaitable[object]]


async def run_scheduler(
    jobs: list[Job],
    timezone: str,
    *,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    stop: asyncio.Event | None = None,
    max_runs: int | None = None,
) -> int:
    """Run jobs at their next occurrence, forever (or until `stop` / `max_runs`)."""
    tz = ZoneInfo(timezone)
    clock = now or (lambda: datetime.now(tz))
    runs = 0
    if not jobs:
        return 0
    last = clock()
    while not (stop and stop.is_set()) and (max_runs is None or runs < max_runs):
        upcoming = sorted(((next_run(j.spec, last), j) for j in jobs), key=lambda x: x[0])
        when, job = upcoming[0]
        delay = (when - clock()).total_seconds()
        if delay > 0:
            await sleep(delay)
        try:
            await job.run(when)
        except Exception:  # keep the rhythm going; one failing job must not stop the others
            log.exception("cadence job %s failed", job.name)
        last = when
        runs += 1
    return runs
