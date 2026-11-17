"""Languages: texts, plurals, dates, tone and the words the agent understands.

One YAML file per language in `locales/` (see docs/languages.md):

* ``texts.<area>.<key>``: what the agent says. Looked up along a chain,
  e.g. ``pt-BR`` → ``pt`` → ``en``, key by key, so a half-translated
  language still works. With ``project.formality: formal`` a ``<key>@formal``
  variant wins where a language provides one.
* ``plurals``: CLDR plural categories (``zero`` / ``one`` / ``few`` /
  ``many`` / ``other``), chosen with Babel's plural rules for the language.
* ``meta.date``: a CLDR date pattern; names of days and months come from Babel.
* ``register``: tone instructions and checks for the model-written summary.
* ``lexicon``: words for reading replies and ticket text. Reading uses **all**
  languages at once: a German reply in an English team is still understood.

English is the reference; every key exists there.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from babel import Locale, UnknownLocaleError
from babel.dates import format_date, get_day_names, get_month_names

LOCALES = Path(__file__).parent / "locales"
BASE = "en"
Formality = Literal["informal", "formal"]

_formality: Formality = "informal"
_caches: list[Callable[[], None]] = []


def cached[T](fn: Callable[[], T]) -> Callable[[], T]:
    """`functools.cache` for things built from the language files; cleared by `reload()`."""
    wrapped = cache(fn)
    _caches.append(wrapped.cache_clear)
    return wrapped


def reload(locales: Path | None = None) -> None:
    """Re-read the language files (tests, or after adding a language at runtime)."""
    global LOCALES
    if locales is not None:
        LOCALES = locales
    for fn in (_load, available, words, weekday_names, month_names):
        fn.cache_clear()
    for clear in _caches:
        clear()


def configure(formality: Formality) -> None:
    """Set the team's form of address (from `project.formality`)."""
    global _formality
    _formality = formality


def formality() -> Formality:
    return _formality


@cache
def _load(code: str) -> dict[str, Any]:  # cleared in reload()
    path = LOCALES / f"{code}.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


@cache
def available() -> tuple[str, ...]:
    """Language codes that have a file, English first."""
    codes = sorted(p.stem for p in LOCALES.glob("*.yaml"))
    return (BASE, *(c for c in codes if c != BASE))


def chain(lang: str) -> list[str]:
    """'pt-BR' → ['pt-BR', 'pt', 'en'], limited to languages that have a file."""
    parts = (lang or BASE).replace("_", "-").split("-")
    candidates = ["-".join(parts[:i]) for i in range(len(parts), 0, -1)] + [BASE]
    out: list[str] = []
    for c in candidates:
        if c not in out and _load(c):
            out.append(c)
    return out or [BASE]


def base_language(lang: str) -> str:
    """The most specific language we have texts for (e.g. 'fr' → 'en' if no fr file)."""
    return chain(lang)[0]


class Texts(Mapping[str, str]):
    """Read-only view of one text area along the language chain."""

    def __init__(self, area: str, lang: str) -> None:
        self.area = area
        self.layers = [(_load(c).get("texts") or {}).get(area) or {} for c in chain(lang)]

    def __getitem__(self, key: str) -> str:
        formal = f"{key}@formal"
        for layer in self.layers:
            if _formality == "formal" and formal in layer:
                return str(layer[formal])
            if key in layer:
                return str(layer[key])
        raise KeyError(f"{self.area}.{key}")

    def __iter__(self) -> Iterator[str]:
        seen: set[str] = set()
        for layer in self.layers:
            for k in layer:
                if "@" not in k and k not in seen:
                    seen.add(k)
                    yield k

    def __len__(self) -> int:
        return sum(1 for _ in self)


def texts(area: str, lang: str) -> Texts:
    return Texts(area, lang)


def text(area: str, lang: str, key: str, **kw: Any) -> str:
    return texts(area, lang)[key].format(**kw)


def every(area: str, key: str) -> tuple[str, ...]:
    """The value of `key` in every language (e.g. to recognise a heading in any language)."""
    out = []
    for code in available():
        value = ((_load(code).get("texts") or {}).get(area) or {}).get(key)
        if value and value not in out:
            out.append(str(value))
    return tuple(out)


def _babel(lang: str) -> Locale:
    try:
        return Locale.parse(lang.replace("-", "_"))
    except (UnknownLocaleError, ValueError):
        return Locale.parse(BASE)


def plural(lang: str, word: str, n: int) -> str:
    """'3 days' / '1 Tag' / '5 dni', using the language's own plural rules."""
    for code in chain(lang):
        forms = (_load(code).get("plurals") or {}).get(word)
        if not forms:
            continue
        if n == 0 and "zero" in forms:
            return str(forms["zero"]).format(n=n)
        category = _babel(code).plural_form(n)
        form = forms.get(category) or forms.get("other")
        if form:
            return str(form).format(n=n)
    raise KeyError(f"plurals.{word}")


def friendly_date(d: date, lang: str) -> str:
    """'Fri 21 Nov 2026' / 'Fr., 21.11.2026', in the language's own pattern and names."""
    code = chain(lang)[0]
    pattern = (_load(code).get("meta") or {}).get("date") or "EEE d MMM y"
    return format_date(d, str(pattern), locale=_babel(code))


def language_name(code: str, in_lang: str) -> str:
    """Name of a language, in another language ('de' in 'en' → 'German')."""
    try:
        name = _babel(in_lang).languages.get(code.split("-")[0])
    except (UnknownLocaleError, ValueError):
        name = None
    return name or code


def has_formal(lang: str) -> bool:
    """Does the language provide `@formal` texts (beyond English)?"""
    code = chain(lang)[0]
    areas = (_load(code).get("texts") or {}).values()
    return any("@formal" in str(k) for area in areas for k in (area or {}))


def review_status(lang: str) -> str:
    """'native' or 'draft' (needs a native speaker's review)."""
    return str((_load(chain(lang)[0]).get("meta") or {}).get("review") or "draft")


def register(lang: str) -> dict[str, Any]:
    """Tone rules for the summary in the team's formality (may be empty)."""
    for code in chain(lang):
        reg = (_load(code).get("register") or {}).get(_formality)
        if reg:
            return dict(reg)
    return {}


# ------------------------------------------------------------------ reading


@cache
def words(key: str) -> tuple[str, ...]:
    """Lexicon entries for `key` across all languages, longest first."""
    found: set[str] = set()
    for code in available():
        for w in (_load(code).get("lexicon") or {}).get(key) or []:
            found.add(str(w).lower())
    return tuple(sorted(found, key=lambda w: (-len(w), w)))


def words_by_language(key: str) -> dict[str, frozenset[str]]:
    out = {}
    for code in available():
        found = (_load(code).get("lexicon") or {}).get(key) or []
        if found:
            out[code] = frozenset(str(w).lower() for w in found)
    return out


def alternation(key: str) -> str:
    """A regex alternation of the lexicon words (spaces match any whitespace)."""
    return "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in words(key))


def _names(kind: Literal["day", "month"]) -> dict[str, int]:
    out: dict[str, int] = {}
    for code in available():
        loc = _babel(code)
        for width in ("wide", "abbreviated"):
            for context in ("format", "stand-alone"):
                if kind == "day":
                    names = get_day_names(width, context, locale=loc)
                else:
                    names = get_month_names(width, context, locale=loc)
                for idx, name in names.items():
                    key = str(name).lower().rstrip(".")
                    out.setdefault(key, idx)
        if kind == "month":
            for name, idx in ((_load(code).get("lexicon") or {}).get("extra_months") or {}).items():
                out.setdefault(str(name).lower(), int(idx))
    return out


@cache
def weekday_names() -> dict[str, int]:
    """'friday' / 'freitag' / 'fri' → 4 (Monday = 0), from CLDR for every language."""
    return _names("day")


@cache
def month_names() -> dict[str, int]:
    """'november' / 'nov' / 'jänner' → month number, from CLDR for every language."""
    return _names("month")
