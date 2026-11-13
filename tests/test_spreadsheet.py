import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from openpyxl.styles import PatternFill

from agentic_pm.adapters import AuditMeta, Channel, TaskPatch, TaskRef, TaskStatus
from agentic_pm.adapters.base import ReadOnlyAdapterError, TaskNotFoundError, TrackerAdapter
from agentic_pm.adapters.registry import build_adapter
from agentic_pm.adapters.spreadsheet import SpreadsheetAdapter, SpreadsheetOptions
from agentic_pm.briefs import collect, render_text
from agentic_pm.cli import main
from agentic_pm.config.team import TeamConfig
from agentic_pm.engine import DependencyGraph
from agentic_pm.testing import AdapterContract

TODAY = date(2026, 11, 16)  # a Monday


def sheet(path: Path, **options: Any) -> SpreadsheetAdapter:
    return SpreadsheetAdapter("ops_sheet", SpreadsheetOptions(path=str(path), **options))


def codes(a: SpreadsheetAdapter) -> list[str]:
    assert a.last_coverage is not None
    return [w.code for w in a.last_coverage.warnings]


# --------------------------------------------------------------------- CSV

CSV = (
    "﻿ID,Task,Status,Due,Depends On\n"  # Excel's byte-order mark
    "T-01,Finalize architecture,done,2026-11-10,\n"
    'T-02,Ship MVP,blocked,2026-11-18,"T-01, github:acme/api#9"\n'
    ",Row without ID,open,2026-11-20,\n"
    "T-02,Duplicate ID row,open,2026-11-21,\n"
    "T-03,Client kickoff,open,TBD,T-99\n"
    ",,,,\n"  # trailing blank row: ignored quietly
)


async def test_csv_loads_valid_rows_and_reports_the_rest(tmp_path: Path) -> None:
    f = tmp_path / "tasks.csv"
    f.write_text(CSV, encoding="utf-8")
    a = sheet(f)
    tasks = {t.ref.id: t for t in await a.list_tasks("ops_sheet", include_closed=True)}
    assert set(tasks) == {"T-01", "T-02", "T-03"}
    assert tasks["T-02"].status is TaskStatus.BLOCKED and tasks["T-02"].due == date(2026, 11, 18)
    assert tasks["T-03"].due is None
    cov = a.last_coverage
    assert cov is not None and cov.rows_scanned == 5 and cov.tasks_loaded == 3
    assert codes(a) == [
        "COLUMN_NOT_FOUND",  # default 'Owner' column isn't in this sheet: said out loud
        "MISSING_TASK_ID",
        "DUPLICATE_TASK_ID",
        "INVALID_DUE_DATE",
        "EXTERNAL_DEPENDENCY",
        "DANGLING_DEPENDENCY",
    ]
    dup = cov.warnings[2]
    assert dup.location == "tasks.csv:row 5" and dup.params["first"] == "tasks.csv:row 3"
    edges = await a.list_dependencies(
        TaskRef(tracker="spreadsheet", project="ops_sheet", id="T-02")
    )
    assert {(str(e.source), str(e.target)) for e in edges} == {
        ("spreadsheet:ops_sheet#T-01", "spreadsheet:ops_sheet#T-02"),
        ("github:acme/api#9", "spreadsheet:ops_sheet#T-02"),
    }
    assert [t.ref.id for t in await a.list_tasks("ops_sheet")] == ["T-02", "T-03"]  # done hidden


async def test_status_map_estimates_owners_and_german_dates(tmp_path: Path) -> None:
    f = tmp_path / "t.csv"
    f.write_text(
        "ID,Aufgabe,Stand,Fällig,Wer,Schätzung\n"
        "A1,Druckfreigabe,In Arbeit,13.11.2026,Sam / Kim,2\n"
        "A2,Website,Warten auf Kunde,2026-11-20,sam,4h\n"
        "A3,Logo,fertig,,,viel\n",
        encoding="utf-8",
    )
    a = sheet(
        f,
        columns={
            "id": "ID",
            "title": "Aufgabe",
            "status": "Stand",
            "due": "Fällig",
            "owner": "Wer",
            "depends_on": None,
            "estimate": "Schätzung",
        },
        status_map={"blocked": ["warten auf kunde"]},
        estimate_unit="days",
    )
    tasks = {t.ref.id: t for t in await a.list_tasks("ops_sheet", include_closed=True)}
    assert tasks["A1"].status is TaskStatus.IN_PROGRESS and tasks["A1"].due == date(2026, 11, 13)
    assert tasks["A1"].assignees == ["Sam", "Kim"] and tasks["A1"].estimate_hours == 16
    assert tasks["A2"].status is TaskStatus.BLOCKED and tasks["A2"].estimate_hours == 4
    assert tasks["A3"].status is TaskStatus.DONE
    assert codes(a) == ["INVALID_ESTIMATE"]


async def test_unknown_status_skips_row(tmp_path: Path) -> None:
    f = tmp_path / "t.csv"
    f.write_text("ID,Task,Status\nT-1,A,Maybe later\n", encoding="utf-8")
    a = sheet(f, columns={"due": None, "owner": None, "depends_on": None})
    assert await a.list_tasks("ops_sheet") == []
    assert codes(a) == ["UNKNOWN_STATUS"]


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("missing.csv", None, "SOURCE_NOT_FOUND"),
        ("tasks.ods", b"x", "UNSUPPORTED_FORMAT"),
        # Missing columns are found inside the row iterator: still reported, never a crash.
        ("cols.csv", b"Identifier,Task,Status\nT-1,A,open\n", "MISSING_COLUMNS"),
        ("broken.xlsx", b"not a zip file", "SOURCE_READ_ERROR"),
    ],
)
async def test_source_problems_are_errors_not_crashes(
    tmp_path: Path, name: str, content: bytes | None, code: str
) -> None:
    f = tmp_path / name
    if content is not None:
        f.write_bytes(content)
    a = sheet(f)
    assert await a.list_tasks("ops_sheet") == []
    assert codes(a)[0] == code
    assert a.last_coverage is not None and a.last_coverage.has_errors


async def test_rereads_when_the_file_changes(tmp_path: Path) -> None:
    f = tmp_path / "t.csv"
    f.write_text("ID,Task,Status\nT-1,A,open\n", encoding="utf-8")
    a = sheet(f, columns={"due": None, "owner": None, "depends_on": None})
    assert len(await a.list_tasks("ops_sheet")) == 1
    f.write_text("ID,Task,Status\nT-1,A,open\nT-2,B,open\n", encoding="utf-8")
    os.utime(f, ns=(1, 2_000_000_000_000_000_000))
    assert len(await a.list_tasks("ops_sheet")) == 2


# -------------------------------------------------------------------- XLSX


def workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Overview"
    tasks = wb.create_sheet("Tasks")
    tasks.append(["Client projects 2026"])  # title row above the header
    tasks.append(["ID", "Task", "Status", "Due", "Owner", "Depends On", "Budget"])
    tasks.append(
        ["P-63", "Printer proof sign-off", "waiting", datetime(2026, 11, 17), "Sam", None, 400]
    )
    tasks.append(["L-1", "Client launch", "open", datetime(2026, 11, 18), "sam", "P-63", 9000])
    tasks.append(["L-2", "Launch mailing", "todo", "=WORKDAY(D4,2)", "Sam", "L-1", 0])
    for r in range(10, 300):  # formatted but empty rows at the bottom
        tasks.cell(row=r, column=1).fill = PatternFill("solid", fgColor="FFFF00")
    wb.save(path)


async def test_xlsx_header_row_dates_formulas_and_blank_formatted_rows(tmp_path: Path) -> None:
    f = tmp_path / "client-projects.xlsx"
    workbook(f)
    a = sheet(f, sheet="Tasks", header_row=2)
    tasks = {t.ref.id: t for t in await a.list_tasks("ops_sheet")}
    assert set(tasks) == {"P-63", "L-1", "L-2"}
    assert tasks["P-63"].status is TaskStatus.BLOCKED and tasks["P-63"].due == date(2026, 11, 17)
    # Written by a script, so the formula has no cached value: reported, not read as "no date".
    assert codes(a) == ["FORMULA_WITHOUT_VALUE"]  # one clear warning, not a second "bad date"
    w = a.last_coverage.warnings[0] if a.last_coverage else None
    assert w is not None and w.location == "Tasks!row 5" and w.params["formula"] == "=WORKDAY(D4,2)"
    assert a.last_coverage is not None and a.last_coverage.rows_scanned == 3


async def test_xlsx_unknown_sheet(tmp_path: Path) -> None:
    f = tmp_path / "c.xlsx"
    workbook(f)
    a = sheet(f, sheet="Aufgaben")
    assert await a.list_tasks("ops_sheet") == []
    assert codes(a) == ["SHEET_NOT_FOUND"]
    assert a.last_coverage is not None and "Overview, Tasks" in a.last_coverage.warnings[0].message


async def test_cascade_from_vendor_to_client_launch(tmp_path: Path) -> None:
    """The 'row 63 printer proof blocks Friday's client launch' story."""
    f = tmp_path / "client-projects.xlsx"
    workbook(f)
    a = sheet(f, sheet="Tasks", header_row=2)
    g = await DependencyGraph.build(a, "ops_sheet")
    proof_late = date(2026, 11, 18)  # what if the printer proof slips 1 day?
    hit = g.impact_of(
        TaskRef(tracker="spreadsheet", project="ops_sheet", id="P-63"), proof_late, TODAY
    )
    assert [r.task.ref.id for r in hit] == ["L-1"]
    assert g.coverage is not None and not g.coverage.is_complete


# ------------------------------------------------------------ brief/config


def solo_cfg(path: Path, lang: str = "de") -> TeamConfig:
    return TeamConfig.model_validate(
        {
            "project": {
                "tracker": "spreadsheet",
                "repo": "ops_sheet",
                "leads": ["sam"],
                "tracker_options": {"path": str(path), "sheet": "Tasks", "header_row": 2},
            },
            "people": {
                "sam": {
                    "role": "owner",
                    "archetype": "reader",
                    "language": lang,
                    "channels": {"email": "sam@example.com"},
                    "brief": {"when": "07:30", "format": "email"},
                }
            },
        }
    )


async def test_solo_brief_shows_coverage_in_german(tmp_path: Path) -> None:
    f = tmp_path / "client-projects.xlsx"
    workbook(f)
    cfg = solo_cfg(f)
    adapter = build_adapter(cfg.project, env={})
    d = await collect(cfg, "sam", adapter, TODAY)
    assert [t.ref.id for t in d.overdue + d.due_soon] == ["P-63", "L-1"]  # "Sam" == "sam"
    text = render_text(d)
    assert "🧾 Nicht alles lesbar: ops_sheet (client-projects.xlsx)" in text
    assert "Tasks!Zeile 5: 'Due' enthält eine Formel ohne berechneten Wert" in text
    assert " Sie " not in text


def test_config_validates_tracker_options(tmp_path: Path) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=r"tracker_options\.colums"):
        TeamConfig.model_validate(
            {
                "project": {
                    "tracker": "spreadsheet",
                    "repo": "s",
                    "leads": ["a"],
                    "tracker_options": {"path": "x.csv", "colums": {}},
                },
                "people": {
                    "a": {"role": "x", "archetype": "reader", "channels": {"email": "a@x.io"}}
                },
            }
        )


def test_deps_cli_fails_loudly_on_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg_file = tmp_path / "team.yaml"
    cfg_file.write_text(
        "project: {tracker: spreadsheet, repo: s, leads: [a], tracker_options: {path: nope.csv}}\n"
        "people: {a: {role: x, archetype: reader, channels: {email: a@x.io}}}\n",
        encoding="utf-8",
    )
    assert main(["deps", "--config", str(cfg_file)]) == 1
    assert "SOURCE_NOT_FOUND" in capsys.readouterr().out


async def test_writes_are_refused(tmp_path: Path) -> None:
    f = tmp_path / "t.csv"
    f.write_text(CSV, encoding="utf-8")
    a = sheet(f)
    assert not a.capabilities.writes
    ref = TaskRef(tracker="spreadsheet", project="ops_sheet", id="T-02")
    with pytest.raises(ReadOnlyAdapterError):
        await a.update_fields(
            ref,
            TaskPatch(status=TaskStatus.DONE),
            AuditMeta(actor="a", channel=Channel.SYSTEM, reason="r"),
        )
    with pytest.raises(TaskNotFoundError):
        await a.get_task(TaskRef(tracker="github", project="acme/api", id="9"))


# ------------------------------------------------------------ contract


_CONTRACT_DIR = Path(tempfile.mkdtemp(prefix="agentic-pm-sheet-"))


class TestSpreadsheetContract(AdapterContract):
    project = "ops_sheet"
    existing_id = "T-02"
    missing_id = "T-999"

    async def make(self) -> TrackerAdapter:
        f = _CONTRACT_DIR / "tasks.csv"
        f.write_text(CSV, encoding="utf-8")
        return sheet(f)
