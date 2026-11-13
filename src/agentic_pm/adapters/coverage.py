"""Coverage reports: "never fail silently" for loosely structured sources.

An adapter that reads a source where rows can be broken (spreadsheets, later
CSV exports or free-form databases) records every row it could not use, with
an exact location. The engine and briefs then say "coverage incomplete"
instead of presenting a partial picture as "all clear".

Adapters opt in by exposing `last_coverage` after `list_tasks()`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Severity = Literal["error", "warning"]

# error   = whole source unusable (file missing, required column missing, ...)
# warning = one row or one value skipped / degraded
ERROR_CODES = frozenset(
    {
        "SOURCE_NOT_FOUND",
        "UNSUPPORTED_FORMAT",
        "SOURCE_READ_ERROR",
        "MISSING_COLUMNS",
        "SHEET_NOT_FOUND",
    }
)


class CoverageWarning(BaseModel):
    code: str
    location: str
    message: str
    task_id: str | None = None
    params: dict[str, str] = {}

    @property
    def severity(self) -> Severity:
        return "error" if self.code in ERROR_CODES else "warning"


class CoverageReport(BaseModel):
    source: str
    rows_scanned: int = 0
    tasks_loaded: int = 0
    warnings: list[CoverageWarning] = []

    @property
    def is_complete(self) -> bool:
        return not self.warnings

    @property
    def has_errors(self) -> bool:
        return any(w.severity == "error" for w in self.warnings)

    def add(
        self,
        code: str,
        location: str,
        message: str,
        task_id: str | None = None,
        **params: object,
    ) -> None:
        self.warnings.append(
            CoverageWarning(
                code=code,
                location=location,
                message=message,
                task_id=task_id,
                params={k: str(v) for k, v in params.items()},
            )
        )
