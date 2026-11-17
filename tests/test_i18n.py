"""Languages: file consistency, fallback, plurals, dates, formality, reading any language."""

import re
import shutil
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
import yaml
from babel import Locale

from agentic_pm import i18n
from agentic_pm.briefs.summary import check_summary, normalize_summary, style_for
from agentic_pm.chat.answers import parse_date, parse_estimate, yes_no
from agentic_pm.engine.completeness import dependency_hints, due_hint
from agentic_pm.engine.triangulation import detect_claim

ORIGINAL = i18n.LOCALES
TODAY = date(2026, 11, 16)  # Monday
_FIELD = re.compile(r"\{(\w+)\}")
CATEGORIES = {"zero", "one", "two", "few", "many", "other"}


def _load(code: str) -> dict:
    return yaml.safe_load((ORIGINAL / f"{code}.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------- every shipped file


@pytest.mark.parametrize("code", [p.stem for p in ORIGINAL.glob("*.yaml")])
def test_language_file_is_consistent_with_english(code: str) -> None:
    en, doc = _load("en"), _load(code)
    assert doc["meta"]["review"] in ("native", "draft")
    Locale.parse(code.replace("-", "_"))  # a real language code
    for area, keys in doc.get("texts", {}).items():
        assert area in en["texts"], f"{code}: unknown area {area}"
        for key, value in keys.items():
            base = key.split("@", 1)[0]
            assert base in en["texts"][area], f"{code}: unknown key {area}.{key}"
            want = set(_FIELD.findall(en["texts"][area][base]))
            assert set(_FIELD.findall(str(value))) == want, f"{code}: {area}.{key} placeholders"
    for word, forms in doc.get("plurals", {}).items():
        assert word in en["plurals"] and set(forms) <= CATEGORIES and "other" in forms
    assert set(doc.get("lexicon", {})) <= set(en["lexicon"]), f"{code}: unknown lexicon key"
    for formality in doc.get("register", {}).values():
        for pattern in formality.get("forbid", []):
            re.compile(pattern)


def test_native_languages_are_complete() -> None:
    en = _load("en")
    for path in ORIGINAL.glob("*.yaml"):
        doc = _load(path.stem)
        if doc["meta"]["review"] != "native":
            continue
        for area, keys in en["texts"].items():
            missing = set(keys) - set(doc["texts"].get(area, {}))
            assert not missing, f"{path.stem}: missing {area}: {sorted(missing)}"


# --------------------------------------- adding a language needs no code


@pytest.fixture
def more_languages(tmp_path: Path) -> Iterator[Path]:
    for f in ORIGINAL.glob("*.yaml"):
        shutil.copy(f, tmp_path / f.name)
    (tmp_path / "fr.yaml").write_text(
        """
meta: {name: Français, review: draft, date: "EEE d MMM y"}
register:
  informal: {style: "Écris en français. Tutoie la personne."}
  formal: {style: "Écris en français. Vouvoie la personne."}
lexicon:
  affirm: ["oui", "ouais", "d'accord"]
  negate: ["non"]
  tomorrow: ["demain"]
  next: ["prochain"]
  day_units: ["jour", "jours", "j"]
  claim_done: ["terminé", "fini"]
  hedge: ["pas", "presque"]
  dependency_words: ["attend"]
  deadline_words: ["échéance"]
texts:
  messages:
    ack_note: "Merci, {name} ! J'ai ajouté ta note à #{id} : {url}"
    ack_note@formal: "Merci, {name} ! J'ai ajouté votre note à #{id} : {url}"
plurals:
  days: {one: "{n} jour", other: "{n} jours"}
""",
        encoding="utf-8",
    )
    (tmp_path / "pl.yaml").write_text(
        """
meta: {name: Polski, review: draft, date: "EEE, d MMM y"}
plurals:
  days: {one: "{n} dzień", few: "{n} dni", many: "{n} dni", other: "{n} dnia"}
""",
        encoding="utf-8",
    )
    i18n.reload(tmp_path)
    yield tmp_path
    i18n.configure("informal")
    i18n.reload(ORIGINAL)


def test_fallback_chain_and_partial_language(more_languages: Path) -> None:
    assert i18n.chain("fr-CA") == ["fr", "en"]
    assert i18n.chain("pt-BR") == ["en"]  # no file: English
    fr = i18n.texts("messages", "fr")
    assert fr["ack_note"].startswith("Merci")
    assert fr["approval_subject"] == i18n.texts("messages", "en")["approval_subject"]
    assert i18n.review_status("fr") == "draft" and i18n.review_status("de") == "native"


def test_formality_picks_formal_variants(more_languages: Path) -> None:
    assert "ta note" in i18n.text("messages", "fr", "ack_note", name="Ana", id="1", url="u")
    i18n.configure("formal")
    assert "votre note" in i18n.text("messages", "fr", "ack_note", name="Ana", id="1", url="u")
    assert i18n.has_formal("fr") and not i18n.has_formal("de")
    assert "Vouvoie" in style_for("fr")


def test_plural_rules_come_from_cldr(more_languages: Path) -> None:
    assert [i18n.plural("pl", "days", n) for n in (1, 2, 5, 22)] == [
        "1 dzień",
        "2 dni",
        "5 dni",
        "22 dni",
    ]
    assert i18n.plural("fr", "days", 2) == "2 jours"
    assert i18n.plural("de", "days", 1) == "1 Tag" and i18n.plural("en", "days", 0) == "0 days"


def test_dates_and_language_names(more_languages: Path) -> None:
    d = date(2026, 11, 20)
    assert i18n.friendly_date(d, "en") == "Fri 20 Nov 2026"
    assert i18n.friendly_date(d, "de") == "Fr., 20.11.2026"
    assert i18n.friendly_date(d, "fr") == "ven. 20 nov. 2026"
    assert i18n.language_name("de", "en") == "German"
    assert i18n.language_name("en", "fr") == "anglais"


def test_reading_works_in_a_new_language(more_languages: Path) -> None:
    assert yes_no("oui") is True and yes_no("non") is False
    assert parse_date("vendredi", TODAY) == date(2026, 11, 20)  # CLDR day names
    assert parse_date("demain", TODAY) == date(2026, 11, 17)
    assert parse_date("25 novembre", TODAY) == date(2026, 11, 25)  # CLDR month names
    assert parse_estimate("2 jours") == 16.0
    claim = detect_claim("C'est terminé.")
    assert claim and claim.kind == "done"
    assert detect_claim("Pas terminé.") is None
    # and the existing languages still work alongside
    assert yes_no("ja") is True and parse_date("Freitag", TODAY) == date(2026, 11, 20)


def test_hints_in_a_new_language(more_languages: Path) -> None:
    from agentic_pm.adapters import Task, TaskRef, TaskStatus

    t = Task(ref=TaskRef(tracker="memory", project="p", id="1"), title="x", status=TaskStatus.OPEN)
    [(ref, _)] = dependency_hints(t, "attend #7")
    assert ref.id == "7"
    hint = due_hint("échéance 2026-12-01")
    assert hint and hint[0] == date(2026, 12, 1)


# ------------------------------------------------- tone of the summary


def test_german_register_rules_still_apply() -> None:
    facts = {"overdue": [{"id": "#11"}]}
    assert "capitalized" in check_summary("Kümmere dich um #11.", facts, "de")[0]
    assert "formal" in check_summary("Bitte erledigen Sie #11.", facts, "de")[0]
    assert normalize_summary("Du schaffst das, dein Team hilft.", "de") == (
        "Du schaffst das, Dein Team hilft."
    )
    i18n.configure("formal")
    try:
        assert check_summary("Bitte erledigen Sie #11.", facts, "de") == []
        assert "informal" in check_summary("Kümmere Dich um #11.", facts, "de")[0]
    finally:
        i18n.configure("informal")


def test_language_without_a_file_gets_a_clear_instruction() -> None:
    assert "Italian" in style_for("it") and "'it'" in style_for("it")
