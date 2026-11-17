"""Reading short chat answers: yes/no, a date, an estimate (any language, deterministic).

Words come from the lexicon of every language file; day and month names
come from CLDR (Babel), so "vendredi" or "piątek" work once a language exists.

Anything parsed here is only ever turned into a **question back** ("Set the
due date to Fri 21 Nov?"), never applied directly, so a misread is harmless.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from agentic_pm import i18n

_EMOJI_YES = {"👍", "✅", "👌"}
_EMOJI_NO = {"👎", "❌"}
_TOKEN = re.compile(r"[\w']+|[👍✅👌👎❌]", re.UNICODE)


def yes_no(text: str) -> bool | None:
    """True / False for a short yes or no, None if it's anything else."""
    words = [w.lower() for w in _TOKEN.findall(text)]
    if not words or len(words) > 6:
        return None
    affirm, negate = set(i18n.words("affirm")) | _EMOJI_YES, set(i18n.words("negate")) | _EMOJI_NO
    yes = any(w in affirm for w in words)
    no = any(w in negate for w in words)
    if yes == no:
        return None
    return yes


_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})?(?!\d)")
_WORD = re.compile(r"[^\W\d_]+")


@i18n.cached
def _patterns() -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    """'25. November', 'Nov 25' and 'in 3 days', in every language we know."""
    d_month = re.compile(r"\b(\d{1,2})\.?\s+([^\W\d_]+)\.?(?:\s+(\d{4}))?")
    month_d = re.compile(r"\b([^\W\d_]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?")
    units = i18n.alternation("day_units") + "|" + i18n.alternation("week_units")
    in_n = re.compile(rf"\b(?:{i18n.alternation('in')})\s+(\d{{1,3}})\s+({units})\b", re.I)
    return d_month, month_d, in_n


def _future(d: date, today: date, *, year_given: bool) -> date:
    if not year_given and d < today:
        try:
            return d.replace(year=d.year + 1)
        except ValueError:
            return d
    return d


def parse_date(text: str, today: date) -> date | None:
    """A date in a short answer, e.g. 'Friday', 'morgen', '25.11.', 'Nov 25', 'in 3 days'."""
    t = text.lower()
    d_month, month_d, in_n = _patterns()
    months = i18n.month_names()
    try:
        if m := _ISO.search(t):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _DMY.search(t):
            year = int(m[3]) if m[3] else today.year
            year += 2000 if m[3] and len(m[3]) == 2 else 0
            return _future(date(year, int(m[2]), int(m[1])), today, year_given=bool(m[3]))
        if (m := d_month.search(t)) and m[2] in months:
            year = int(m[3]) if m[3] else today.year
            d = date(year, months[m[2]], int(m[1]))
            return _future(d, today, year_given=bool(m[3]))
        if (m := month_d.search(t)) and m[1] in months:
            year = int(m[3]) if m[3] else today.year
            d = date(year, months[m[1]], int(m[2]))
            return _future(d, today, year_given=bool(m[3]))
    except ValueError:
        return None  # 31.02. and friends
    if m := in_n.search(t):
        n = int(m[1])
        weeks = m[2].lower() in i18n.words("week_units")
        return today + timedelta(days=n * 7 if weeks else n)
    found = set(_WORD.findall(t))
    if found & set(i18n.words("day_after_tomorrow")):
        return today + timedelta(days=2)
    if found & set(i18n.words("tomorrow")):
        return today + timedelta(days=1)
    if found & set(i18n.words("today")):
        return today
    weekdays = i18n.weekday_names()
    days = [weekdays[w] for w in _WORD.findall(t) if w in weekdays and len(w) > 2]
    if len(set(days)) == 1:
        ahead = (days[0] - today.weekday()) % 7
        if found & set(i18n.words("next")) and ahead == 0:
            ahead = 7
        return today + timedelta(days=ahead)
    return None


@i18n.cached
def _estimate_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    hours, days, weeks = (i18n.alternation(k) for k in ("hour_units", "day_units", "week_units"))
    estimate = re.compile(rf"(\d+(?:[.,]\d+)?)\s*({hours}|{days}|{weeks})\b", re.I)
    half = re.compile(rf"\b({i18n.alternation('half_day')})\b", re.I)
    return estimate, half


def parse_estimate(text: str, hours_per_day: float = 8.0) -> float | None:
    """Hours in a short answer, e.g. '4h', '2 days', '1,5 Tage', 'half a day'."""
    estimate, half = _estimate_patterns()
    if half.search(text):
        return hours_per_day / 2
    m = estimate.search(text)
    if not m:
        return None
    n = float(m[1].replace(",", "."))
    unit = re.sub(r"\s+", " ", m[2].lower())
    if unit in i18n.words("week_units"):
        n *= hours_per_day * 5
    elif unit in i18n.words("day_units"):
        n *= hours_per_day
    return n if 0 < n <= 2000 else None
