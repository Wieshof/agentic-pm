"""Small parsers for task metadata written as plain text in descriptions.

Trackers like GitHub Issues have no native due date or estimate. Teams can
write them as simple lines in the issue body, e.g.

    Due: 2026-12-01
    Estimate: 2d
    Blocked by #12, #15
"""

from __future__ import annotations

import re
from datetime import date

_DUE = re.compile(r"^\s*(?:due|deadline|fällig)\s*:\s*(\d{4}-\d{2}-\d{2})\s*$", re.I | re.M)
_EST = re.compile(r"^\s*(?:estimate|schätzung)\s*:\s*([\d.]+)\s*([hdw])\s*$", re.I | re.M)
_EST_LABEL = re.compile(r"^estimate:([\d.]+)([hdw])$", re.I)
_BLOCKED_BY = re.compile(r"^\s*(?:blocked by|depends on|abhängig von)\s*:?\s*(.+)$", re.I | re.M)
_BLOCKS = re.compile(r"^\s*(?:blocks|blockiert)\s*:?\s*(.+)$", re.I | re.M)
_ISSUE_NO = re.compile(r"#(\d+)")

HOURS_PER = {"h": 1.0, "d": 8.0, "w": 40.0}


def parse_due(text: str | None) -> date | None:
    if not text:
        return None
    m = _DUE.search(text)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _hours(num: str, unit: str) -> float | None:
    try:
        return float(num) * HOURS_PER[unit.lower()]
    except ValueError:
        return None


def parse_estimate(text: str | None, labels: list[str] | None = None) -> float | None:
    """Estimate in hours from an `Estimate: 4h|2d|1w` line or an `estimate:4h` label."""
    if text and (m := _EST.search(text)):
        return _hours(m.group(1), m.group(2))
    for label in labels or []:
        if m := _EST_LABEL.match(label.strip()):
            return _hours(m.group(1), m.group(2))
    return None


def parse_issue_links(text: str | None) -> tuple[list[str], list[str]]:
    """(blocked_by, blocks) issue numbers referenced as `#N` on those lines."""
    if not text:
        return [], []
    blocked_by = [n for line in _BLOCKED_BY.findall(text) for n in _ISSUE_NO.findall(line)]
    blocks = [n for line in _BLOCKS.findall(text) for n in _ISSUE_NO.findall(line)]
    return blocked_by, blocks
