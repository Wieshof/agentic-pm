"""Coverage warnings in the reader's language (EN/DE), for briefs and digests."""

from __future__ import annotations

from agentic_pm.adapters.coverage import CoverageReport, CoverageWarning

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "heading": "🧾 Coverage incomplete: {source}",
        "more": "… and {n} more (run `agent-pm deps` for the full list)",
        "row": "row",
        "SOURCE_NOT_FOUND": "the file wasn't found ({path}), so nothing could be checked",
        "UNSUPPORTED_FORMAT": "'{suffix}' files aren't supported; use .xlsx or .csv",
        "SOURCE_READ_ERROR": "the file couldn't be read ({error})",
        "MISSING_COLUMNS": "required column(s) missing: {missing}",
        "SHEET_NOT_FOUND": "sheet '{sheet}' not found (sheets: {sheets})",
        "COLUMN_NOT_FOUND": "column '{column}' not found, so {key} is ignored",
        "DUPLICATE_HEADER": "column '{column}' appears twice; the first one is used",
        "FORMULA_WITHOUT_VALUE": "'{column}' has a formula without a calculated value; "
        "open and save the file in Excel",
        "MISSING_TASK_ID": "row has content but no ID, skipped",
        "DUPLICATE_TASK_ID": "ID '{id}' is used twice (first at {first}), row skipped",
        "MISSING_TITLE": "'{id}' has no title, skipped",
        "MISSING_STATUS": "'{id}' has no status, skipped",
        "UNKNOWN_STATUS": "'{id}' has status '{status}', which isn't mapped, skipped",
        "INVALID_DUE_DATE": "'{id}' has due date '{value}', which isn't a date; "
        "checked without a deadline",
        "INVALID_ESTIMATE": "'{id}' has estimate '{value}', which isn't readable",
        "BAD_REFERENCE": "'{id}' depends on '{ref}', which isn't a known reference",
        "DANGLING_DEPENDENCY": "'{id}' depends on '{dep}', which isn't in the sheet",
        "EXTERNAL_DEPENDENCY": "'{id}' depends on {dep}, which can't be checked yet",
    },
    "de": {
        "heading": "🧾 Nicht alles lesbar: {source}",
        "more": "… und {n} weitere (`agent-pm deps` zeigt die ganze Liste)",
        "row": "Zeile",
        "SOURCE_NOT_FOUND": "die Datei wurde nicht gefunden ({path}), deshalb konnte ich nichts "
        "prüfen",
        "UNSUPPORTED_FORMAT": "'{suffix}'-Dateien werden nicht unterstützt; nimm .xlsx oder .csv",
        "SOURCE_READ_ERROR": "die Datei konnte nicht gelesen werden ({error})",
        "MISSING_COLUMNS": "Pflichtspalte(n) fehlen: {missing}",
        "SHEET_NOT_FOUND": "Blatt '{sheet}' nicht gefunden (vorhanden: {sheets})",
        "COLUMN_NOT_FOUND": "Spalte '{column}' nicht gefunden, deshalb wird {key} ignoriert",
        "DUPLICATE_HEADER": "Spalte '{column}' kommt doppelt vor; die erste wird verwendet",
        "FORMULA_WITHOUT_VALUE": "'{column}' enthält eine Formel ohne berechneten Wert; "
        "öffne und speichere die Datei in Excel",
        "MISSING_TASK_ID": "Zeile hat Inhalt, aber keine ID, übersprungen",
        "DUPLICATE_TASK_ID": "ID '{id}' kommt doppelt vor (zuerst in {first}), Zeile übersprungen",
        "MISSING_TITLE": "'{id}' hat keinen Titel, übersprungen",
        "MISSING_STATUS": "'{id}' hat keinen Status, übersprungen",
        "UNKNOWN_STATUS": "'{id}' hat den Status '{status}', der nicht zugeordnet ist, "
        "übersprungen",
        "INVALID_DUE_DATE": "'{id}' hat als Fälligkeit '{value}', das ist kein Datum; "
        "ohne Termin geprüft",
        "INVALID_ESTIMATE": "'{id}' hat als Schätzung '{value}', das ist nicht lesbar",
        "BAD_REFERENCE": "'{id}' hängt von '{ref}' ab, das ist keine bekannte Referenz",
        "DANGLING_DEPENDENCY": "'{id}' hängt von '{dep}' ab, das steht nicht in der Tabelle",
        "EXTERNAL_DEPENDENCY": "'{id}' hängt von {dep} ab, das kann ich noch nicht prüfen",
    },
}
MAX_ITEMS = 10


def _t(lang: str) -> dict[str, str]:
    return TEXTS.get(lang.split("-")[0], TEXTS["en"])


def render_warning(w: CoverageWarning, lang: str) -> str:
    t = _t(lang)
    location = w.location.replace("row ", f"{t['row']} ")
    try:
        text = t[w.code].format(**w.params)
    except (KeyError, IndexError):
        text = w.message  # unknown code or missing params: the English message
    text = text.replace("row ", f"{t['row']} ")
    return f"{location}: {text}"


def render_coverage(report: CoverageReport, lang: str) -> tuple[str, list[str]]:
    """(heading, items) with errors first and at most MAX_ITEMS lines."""
    t = _t(lang)
    ordered = sorted(report.warnings, key=lambda w: w.severity != "error")
    items = [render_warning(w, lang) for w in ordered[:MAX_ITEMS]]
    if len(ordered) > MAX_ITEMS:
        items.append(t["more"].format(n=len(ordered) - MAX_ITEMS))
    return t["heading"].format(source=report.source), items
