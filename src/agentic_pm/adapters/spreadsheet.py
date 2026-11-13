"""Spreadsheet adapter (.xlsx / .csv), read-only: the zero-setup onboarding wedge.

A freelancer or small team keeps working in their own task sheet; agentic-pm
reads it on every run and gives the same dependency alerts and briefs as for
GitHub or OpenProject. Configured via `project.tracker_options`:

```yaml
project:
  tracker: spreadsheet
  repo: ops_sheet                 # name of this sheet, used in task references
  tracker_options:
    path: data/client-projects.xlsx   # relative to where agent-pm runs
    sheet: Tasks                      # .xlsx only; default: first sheet
    columns: {id: ID, title: Task, status: Status, due: Due, owner: Owner,
              depends_on: Depends On, estimate: Estimate}
    status_map: {in_progress: [doing], done: [shipped]}   # extends the defaults
```

Never fails silently. Every row or value it can't use is recorded with its
exact location in a `CoverageReport` (`last_coverage`), which briefs show:

1. No row-number fallbacks: rows without an ID, or with a duplicate ID, are
   skipped and reported; IDs are never invented.
2. Trailing blank rows (every mapped column empty) are ignored quietly.
3. .xlsx is read with `read_only=True, data_only=True` (cached formula
   results); formulas without a cached value are reported, not read as empty.
4. CSV is read as `utf-8-sig`, so Excel's byte-order mark can't hide the
   first header.
5. `Depends On`: `T-12` means this sheet; `github:acme/api#42` points to
   another tracker and is reported as not checkable until cross-tracker
   dependencies exist (#59).

Unknown statuses skip the row (a wrong guess could hide or invent a risk).
Unparseable dates and estimates keep the task and report the value.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentic_pm.adapters._text import HOURS_PER
from agentic_pm.adapters.base import (
    CLOSED_STATUSES,
    AuditMeta,
    Edge,
    EventHandler,
    ReadOnlyAdapterError,
    Task,
    TaskNotFoundError,
    TaskPatch,
    TaskRef,
    TaskStatus,
    Unsubscribe,
)
from agentic_pm.adapters.catalog import load_catalog
from agentic_pm.adapters.coverage import CoverageReport

DEFAULT_STATUS_MAP: dict[TaskStatus, list[str]] = {
    TaskStatus.OPEN: ["open", "todo", "to do", "new", "planned", "backlog", "offen", "geplant"],
    TaskStatus.IN_PROGRESS: ["in progress", "doing", "wip", "started", "in arbeit", "läuft"],
    TaskStatus.IN_REVIEW: ["review", "in review", "qa", "testing", "prüfung"],
    TaskStatus.BLOCKED: ["blocked", "waiting", "on hold", "stalled", "blockiert", "wartet"],
    TaskStatus.DONE: [
        "done",
        "closed",
        "complete",
        "completed",
        "shipped",
        "finished",
        "erledigt",
        "fertig",
    ],
    TaskStatus.CLOSED: ["cancelled", "canceled", "dropped", "won't do", "abgebrochen", "verworfen"],
}
_DEP_SPLIT = re.compile(r"[,;\n]+")
_OWNER_SPLIT = re.compile(r"\s*[,;/&]\s*")
_QUALIFIED = re.compile(r"^([a-z0-9_-]+):(.+)$")
_EST = re.compile(r"^\s*([\d.]+)\s*([hdw])?\s*$", re.I)
_DE_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


class SpreadsheetColumns(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = "ID"
    title: str = "Task"
    status: str = "Status"
    due: str | None = "Due"
    owner: str | None = "Owner"
    depends_on: str | None = "Depends On"
    estimate: str | None = None
    notes: str | None = None

    def optional(self) -> dict[str, str]:
        return {
            k: v
            for k in ("due", "owner", "depends_on", "estimate", "notes")
            if (v := getattr(self, k))
        }

    def mapped(self) -> list[str]:
        return [self.id, self.title, self.status, *self.optional().values()]


class SpreadsheetOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sheet: str | None = None
    header_row: int = Field(default=1, ge=1, le=50)
    columns: SpreadsheetColumns = SpreadsheetColumns()
    status_map: dict[TaskStatus, list[str]] = Field(
        default_factory=dict, description="Extra spellings per status; extends the defaults"
    )
    estimate_unit: Literal["hours", "days"] = "hours"


class _Row(BaseModel):
    task: Task
    depends_on: list[TaskRef]
    location: str


class SpreadsheetAdapter:
    name = "spreadsheet"

    def __init__(self, instance: str, options: SpreadsheetOptions) -> None:
        self.instance = instance  # project.repo: names this sheet in task references
        self.options = options
        self.path = Path(options.path)
        self.capabilities = load_catalog()["spreadsheet"].capabilities(writes=False)
        self._status: dict[str, TaskStatus] = {}
        for status, words in DEFAULT_STATUS_MAP.items():
            for w in words:
                self._status[w.lower()] = status
        for status, words in options.status_map.items():
            for w in words:
                self._status[w.strip().lower()] = status
        self._cache: tuple[tuple[int, int], dict[str, _Row], CoverageReport] | None = None
        self.last_coverage: CoverageReport | None = None
        self._handlers: list[EventHandler] = []

    # ---------------------------------------------------------------- loading

    def _load(self) -> tuple[dict[str, _Row], CoverageReport]:
        """Parse the file (cached until it changes on disk)."""
        try:
            stat = self.path.stat()
            key = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            key = (-1, -1)
        if self._cache and self._cache[0] == key and key != (-1, -1):
            rows, report = self._cache[1], self._cache[2]
        else:
            rows, report = self._parse()
            self._cache = (key, rows, report)
        self.last_coverage = report
        return rows, report

    def _parse(self) -> tuple[dict[str, _Row], CoverageReport]:
        report = CoverageReport(source=f"{self.instance} ({self.path.name})")
        where = str(self.path)
        if not self.path.exists():
            report.add("SOURCE_NOT_FOUND", where, f"File not found: {self.path}", path=self.path)
            return {}, report
        suffix = self.path.suffix.lower()
        if suffix not in (".csv", ".xlsx"):
            report.add(
                "UNSUPPORTED_FORMAT",
                where,
                f"'{suffix}' isn't supported; use .xlsx or .csv",
                suffix=suffix,
            )
            return {}, report

        rows: dict[str, _Row] = {}
        try:
            # Header problems are detected inside the iterator, so everything that
            # touches the file stays within this try (a generator body only runs
            # when it is consumed).
            source = self._csv_rows(report) if suffix == ".csv" else self._xlsx_rows(report)
            for location, values, formulas in source:
                self._handle_row(location, values, formulas, rows, report)
        except _SourceProblem:
            return {}, report
        except Exception as e:  # unreadable, locked, corrupt ...
            report.add("SOURCE_READ_ERROR", where, f"Could not read the file: {e}", error=e)
            return {}, report

        for row in rows.values():
            for dep in row.depends_on:
                local = dep.tracker == self.name and dep.project == self.instance
                if local and dep.id not in rows:
                    report.add(
                        "DANGLING_DEPENDENCY",
                        row.location,
                        f"'{row.task.ref.id}' depends on '{dep.id}', which isn't in the sheet "
                        "(or was skipped above)",
                        row.task.ref.id,
                        id=row.task.ref.id,
                        dep=dep.id,
                    )
                elif not local:
                    report.add(
                        "EXTERNAL_DEPENDENCY",
                        row.location,
                        f"'{row.task.ref.id}' depends on {dep}, which can't be checked yet "
                        "(cross-tracker dependencies: issue #59)",
                        row.task.ref.id,
                        id=row.task.ref.id,
                        dep=dep,
                    )
        return rows, report

    def _check_headers(self, headers: list[str], location: str, report: CoverageReport) -> None:
        present = {h for h in headers if h}
        cols = self.options.columns
        missing = [c for c in (cols.id, cols.title, cols.status) if c not in present]
        if missing:
            report.add(
                "MISSING_COLUMNS",
                location,
                f"Required column(s) not found: {', '.join(missing)}. "
                f"Found: {', '.join(sorted(present)) or 'nothing'}",
                missing=", ".join(missing),
                found=", ".join(sorted(present)) or "-",
            )
            raise _SourceProblem
        for key, name in cols.optional().items():
            if name not in present:
                report.add(
                    "COLUMN_NOT_FOUND",
                    location,
                    f"Column '{name}' ({key}) isn't in the sheet, so {key} is ignored. "
                    f"Set columns.{key}: null if you don't track it.",
                    column=name,
                    key=key,
                )
        seen: set[str] = set()
        for h in headers:
            if h and h in seen:
                report.add(
                    "DUPLICATE_HEADER",
                    location,
                    f"Column '{h}' appears twice; first one used",
                    column=h,
                )
            seen.add(h)

    def _csv_rows(
        self, report: CoverageReport
    ) -> Iterator[tuple[str, dict[str, Any], dict[str, Any]]]:
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            hr = self.options.header_row
            for _ in range(hr - 1):
                next(reader, None)
            headers = [h.strip() for h in next(reader, [])]
            self._check_headers(headers, f"{self.path.name}:row {hr}", report)
            for idx, raw in enumerate(reader, start=hr + 1):
                values = {}
                for i, h in enumerate(headers):
                    if h and h not in values:
                        values[h] = raw[i] if i < len(raw) else None
                yield f"{self.path.name}:row {idx}", values, {}

    def _xlsx_rows(
        self, report: CoverageReport
    ) -> Iterator[tuple[str, dict[str, Any], dict[str, Any]]]:
        import openpyxl

        wb_values = openpyxl.load_workbook(self.path, read_only=True, data_only=True)
        wb_formulas = openpyxl.load_workbook(self.path, read_only=True, data_only=False)
        try:
            name = self.options.sheet or wb_values.sheetnames[0]
            if name not in wb_values.sheetnames:
                report.add(
                    "SHEET_NOT_FOUND",
                    self.path.name,
                    f"Sheet '{name}' not found. Sheets: {', '.join(wb_values.sheetnames)}",
                    sheet=name,
                    sheets=", ".join(wb_values.sheetnames),
                )
                raise _SourceProblem
            hr = self.options.header_row
            values_iter = wb_values[name].iter_rows(min_row=hr, values_only=True)
            formula_iter = wb_formulas[name].iter_rows(min_row=hr, values_only=True)
            header = next(values_iter, None) or ()
            next(formula_iter, None)
            headers = ["" if c is None else str(c).strip() for c in header]
            self._check_headers(headers, f"{name}!row {hr}", report)
            for idx, (vals, forms) in enumerate(
                zip(values_iter, formula_iter, strict=False), start=hr + 1
            ):
                row: dict[str, Any] = {}
                raw: dict[str, Any] = {}
                for i, h in enumerate(headers):
                    if h and h not in row:
                        row[h] = vals[i] if i < len(vals) else None
                        raw[h] = forms[i] if i < len(forms) else None
                yield f"{name}!row {idx}", row, raw
        finally:
            wb_values.close()
            wb_formulas.close()

    # ------------------------------------------------------------- one row

    @staticmethod
    def _empty(v: Any) -> bool:
        return v is None or (isinstance(v, str) and not v.strip())

    @staticmethod
    def _text(v: Any) -> str:
        return "" if v is None else str(v).strip()

    def _handle_row(
        self,
        location: str,
        values: dict[str, Any],
        formulas: dict[str, Any],
        rows: dict[str, _Row],
        report: CoverageReport,
    ) -> None:
        cols = self.options.columns
        has_formula = any(
            isinstance(formulas.get(c), str) and str(formulas.get(c)).startswith("=")
            for c in cols.mapped()
        )
        if all(self._empty(values.get(c)) for c in cols.mapped()) and not has_formula:
            return  # trailing / spacer row: ignored quietly
        report.rows_scanned += 1

        for col in cols.mapped():
            f = formulas.get(col)
            if self._empty(values.get(col)) and isinstance(f, str) and f.startswith("="):
                report.add(
                    "FORMULA_WITHOUT_VALUE",
                    location,
                    f"'{col}' has a formula ({f}) without a calculated value; open and save the "
                    "file in Excel or LibreOffice so the result is stored",
                    self._text(values.get(cols.id)) or None,
                    column=col,
                    formula=f,
                )

        task_id = self._text(values.get(cols.id))
        if not task_id:
            report.add("MISSING_TASK_ID", location, "Row has content but no ID; skipped")
            return
        if task_id in rows:
            report.add(
                "DUPLICATE_TASK_ID",
                location,
                f"ID '{task_id}' already used at {rows[task_id].location}; this row skipped",
                task_id,
                id=task_id,
                first=rows[task_id].location,
            )
            return
        title = self._text(values.get(cols.title))
        if not title:
            report.add(
                "MISSING_TITLE", location, f"'{task_id}' has no title; skipped", task_id, id=task_id
            )
            return
        raw_status = self._text(values.get(cols.status))
        if not raw_status:
            report.add(
                "MISSING_STATUS",
                location,
                f"'{task_id}' has no status; skipped",
                task_id,
                id=task_id,
            )
            return
        status = self._status.get(raw_status.lower())
        if status is None:
            report.add(
                "UNKNOWN_STATUS",
                location,
                f"'{task_id}' has status '{raw_status}', which isn't mapped; skipped. "
                "Add it to status_map.",
                task_id,
                id=task_id,
                status=raw_status,
            )
            return

        due = None
        if cols.due and not self._empty(values.get(cols.due)):
            due = self._date(values.get(cols.due))
            if due is None:
                report.add(
                    "INVALID_DUE_DATE",
                    location,
                    f"'{task_id}' has due date '{values.get(cols.due)}', which isn't a date "
                    "(use YYYY-MM-DD, DD.MM.YYYY or a date cell); loaded without a deadline",
                    task_id,
                    id=task_id,
                    value=values.get(cols.due),
                )
        estimate = None
        if cols.estimate and not self._empty(values.get(cols.estimate)):
            estimate = self._estimate(values.get(cols.estimate))
            if estimate is None:
                report.add(
                    "INVALID_ESTIMATE",
                    location,
                    f"'{task_id}' has estimate '{values.get(cols.estimate)}', which isn't a "
                    "number or 4h/2d/1w; loaded without an estimate",
                    task_id,
                    id=task_id,
                    value=values.get(cols.estimate),
                )
        notes = self._text(values.get(cols.notes)) if cols.notes else ""
        owners: list[str] = []
        if cols.owner:
            owners = [o for o in _OWNER_SPLIT.split(self._text(values.get(cols.owner))) if o]
        deps: list[TaskRef] = []
        if cols.depends_on:
            for token in _DEP_SPLIT.split(self._text(values.get(cols.depends_on))):
                token = token.strip()
                if not token:
                    continue
                ref = self._dep_ref(token)
                if ref is None:
                    report.add(
                        "BAD_REFERENCE",
                        location,
                        f"'{task_id}' depends on '{token}', which isn't an ID from this sheet "
                        "or a reference like github:owner/repo#42; ignored",
                        task_id,
                        id=task_id,
                        ref=token,
                    )
                else:
                    deps.append(ref)

        rows[task_id] = _Row(
            task=Task(
                ref=TaskRef(tracker=self.name, project=self.instance, id=task_id),
                title=title,
                status=status,
                assignees=owners,
                due=due,
                estimate_hours=estimate,
                description=notes or None,
            ),
            depends_on=deps,
            location=location,
        )
        report.tasks_loaded += 1

    def _dep_ref(self, token: str) -> TaskRef | None:
        m = _QUALIFIED.match(token)
        if not m:
            return TaskRef(tracker=self.name, project=self.instance, id=token)
        prefix, rest = m.group(1), m.group(2).strip()
        if prefix == self.instance:
            return TaskRef(tracker=self.name, project=self.instance, id=rest)
        if "#" in rest:
            project, _, tid = rest.rpartition("#")
            if project and tid:
                return TaskRef(tracker=prefix, project=project, id=tid)
        return None

    @staticmethod
    def _date(v: Any) -> date | None:
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        text = str(v).strip()
        for parse in (date.fromisoformat, lambda t: datetime.fromisoformat(t).date()):
            try:
                return parse(text)
            except ValueError:
                pass
        if m := _DE_DATE.match(text):  # 13.11.2026 is unambiguous; 11/12/2026 is not
            try:
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                return None
        return None

    def _estimate(self, v: Any) -> float | None:
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            hours = float(v) * (8 if self.options.estimate_unit == "days" else 1)
            return hours if hours >= 0 else None
        m = _EST.match(str(v))
        if not m:
            return None
        num = float(m.group(1))
        unit = (m.group(2) or ("d" if self.options.estimate_unit == "days" else "h")).lower()
        return num * HOURS_PER[unit]

    # --------------------------------------------------------------- protocol

    async def list_tasks(self, project: str, *, include_closed: bool = False) -> list[Task]:
        rows, _ = self._load()
        if project != self.instance:
            return []
        return [
            r.task.model_copy(deep=True)
            for r in rows.values()
            if include_closed or r.task.status not in CLOSED_STATUSES
        ]

    async def get_task(self, ref: TaskRef) -> Task:
        rows, _ = self._load()
        row = rows.get(ref.id) if (ref.tracker, ref.project) == (self.name, self.instance) else None
        if row is None:
            raise TaskNotFoundError(str(ref))
        return row.task.model_copy(deep=True)

    async def list_dependencies(self, ref: TaskRef) -> list[Edge]:
        rows, _ = self._load()
        if ref.id not in rows:
            raise TaskNotFoundError(str(ref))
        edges = [Edge(source=d, target=ref) for d in rows[ref.id].depends_on]
        edges += [
            Edge(source=ref, target=r.task.ref)
            for r in rows.values()
            if ref in r.depends_on and r.task.ref != ref
        ]
        return edges

    async def add_comment(self, ref: TaskRef, markdown: str, meta: AuditMeta) -> None:
        raise ReadOnlyAdapterError(f"{self.path.name} is read-only for the agent")

    async def update_fields(self, ref: TaskRef, patch: TaskPatch, meta: AuditMeta) -> Task:
        raise ReadOnlyAdapterError(f"{self.path.name} is read-only for the agent")

    def subscribe(self, handler: EventHandler) -> Unsubscribe:
        # No change events from a file; the sheet is re-read on every run (#22 polling).
        self._handlers.append(handler)
        return lambda: self._handlers.remove(handler)


class _SourceProblem(Exception):
    """Internal: the source is unusable; details are already in the report."""
