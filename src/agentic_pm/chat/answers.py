"""Reading short chat answers: yes/no, a date, an estimate (EN/DE, deterministic).

Anything parsed here is only ever turned into a **question back** ("Set the
due date to Fri 21 Nov?"), never applied directly, so a misread is harmless.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

_YES = {
    "yes", "y", "yep", "yeah", "yup", "ok", "okay", "sure", "correct", "right", "please",
    "ja", "jo", "jep", "jup", "passt", "gern", "gerne", "genau", "richtig", "bitte", "klar",
    "👍", "✅", "👌",
}  # fmt: skip
_NO = {
    "no", "n", "nope", "nah", "not", "dont", "don't", "wrong",
    "nein", "nö", "nee", "ne", "nicht", "falsch", "lieber",
    "👎", "❌",
}  # fmt: skip
_TOKEN = re.compile(r"[\w']+|[👍✅👌👎❌]", re.UNICODE)


def yes_no(text: str) -> bool | None:
    """True / False for a short yes or no, None if it's anything else."""
    words = [w.lower() for w in _TOKEN.findall(text)]
    if not words or len(words) > 6:
        return None
    yes = any(w in _YES for w in words)
    no = any(w in _NO for w in words)
    if yes == no:
        return None
    return yes


_WEEKDAYS = {
    **dict.fromkeys(["monday", "mon", "montag", "mo"], 0),
    **dict.fromkeys(["tuesday", "tue", "dienstag", "di"], 1),
    **dict.fromkeys(["wednesday", "wed", "mittwoch", "mi"], 2),
    **dict.fromkeys(["thursday", "thu", "donnerstag", "do"], 3),
    **dict.fromkeys(["friday", "fri", "freitag", "fr"], 4),
    **dict.fromkeys(["saturday", "sat", "samstag", "sa"], 5),
    **dict.fromkeys(["sunday", "sun", "sonntag", "so"], 6),
}
_MONTHS = {
    **dict.fromkeys(["january", "jan", "januar", "jänner", "jän"], 1),
    **dict.fromkeys(["february", "feb", "februar"], 2),
    **dict.fromkeys(["march", "mar", "märz", "mär"], 3),
    **dict.fromkeys(["april", "apr"], 4),
    **dict.fromkeys(["may", "mai"], 5),
    **dict.fromkeys(["june", "jun", "juni"], 6),
    **dict.fromkeys(["july", "jul", "juli"], 7),
    **dict.fromkeys(["august", "aug"], 8),
    **dict.fromkeys(["september", "sep", "sept"], 9),
    **dict.fromkeys(["october", "oct", "oktober", "okt"], 10),
    **dict.fromkeys(["november", "nov"], 11),
    **dict.fromkeys(["december", "dec", "dezember", "dez"], 12),
}
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})?(?!\d)")
_D_MONTH = re.compile(r"\b(\d{1,2})\.?\s+([a-zäö]+)\.?(?:\s+(\d{4}))?", re.I)
_MONTH_D = re.compile(r"\b([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?", re.I)
_IN_N = re.compile(r"\bin\s+(\d{1,3})\s+(days?|tagen?|weeks?|wochen?)\b", re.I)
_WORD = re.compile(r"[a-zäöüß]+", re.I)


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
    try:
        if m := _ISO.search(t):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _DMY.search(t):
            year = int(m[3]) if m[3] else today.year
            year += 2000 if m[3] and len(m[3]) == 2 else 0
            return _future(date(year, int(m[2]), int(m[1])), today, year_given=bool(m[3]))
        if (m := _D_MONTH.search(t)) and m[2] in _MONTHS:
            year = int(m[3]) if m[3] else today.year
            d = date(year, _MONTHS[m[2]], int(m[1]))
            return _future(d, today, year_given=bool(m[3]))
        if (m := _MONTH_D.search(t)) and m[1] in _MONTHS:
            year = int(m[3]) if m[3] else today.year
            d = date(year, _MONTHS[m[1]], int(m[2]))
            return _future(d, today, year_given=bool(m[3]))
    except ValueError:
        return None  # 31.02. and friends
    if m := _IN_N.search(t):
        n = int(m[1])
        return today + timedelta(days=n * 7 if m[2].startswith(("week", "woche")) else n)
    words = _WORD.findall(t)
    if "übermorgen" in words:
        return today + timedelta(days=2)
    if {"tomorrow", "morgen"} & set(words):
        return today + timedelta(days=1)
    if {"today", "heute"} & set(words):
        return today
    days = [_WEEKDAYS[w] for w in words if w in _WEEKDAYS and len(w) > 2]
    if len(set(days)) == 1:
        ahead = (days[0] - today.weekday()) % 7
        if {"next", "nächsten", "nächster", "nächste", "kommenden"} & set(words) and ahead == 0:
            ahead = 7
        return today + timedelta(days=ahead)
    return None


_ESTIMATE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(h|hrs?|hours?|std|stunden?|d|days?|tage?n?|w|wks?|weeks?|wochen?)\b",
    re.I,
)
_HALF_DAY = re.compile(r"\b(half a day|halben tag|halber tag|1/2 tag)\b", re.I)


def parse_estimate(text: str, hours_per_day: float = 8.0) -> float | None:
    """Hours in a short answer, e.g. '4h', '2 days', '1,5 Tage', 'half a day'."""
    if _HALF_DAY.search(text):
        return hours_per_day / 2
    m = _ESTIMATE.search(text)
    if not m:
        return None
    n = float(m[1].replace(",", "."))
    unit = m[2].lower()
    if unit.startswith(("w", "wo")):
        n *= hours_per_day * 5
    elif unit.startswith(("d", "t")):
        n *= hours_per_day
    return n if 0 < n <= 2000 else None
