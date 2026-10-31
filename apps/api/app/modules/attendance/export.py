"""Attendance report as CSV or XLSX: one row per student, one column per meeting (D-094)."""

import codecs
import csv
import io

from openpyxl import Workbook

from app.core.time import BAKU
from app.modules.attendance.schemas import AttendanceReportOut

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Spreadsheet programs run cells that start with these as formulas; names and titles are typed by people.
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _safe(text: str) -> str:
    return f"'{text}" if text.startswith(_FORMULA_STARTS) else text


def _table(report: AttendanceReportOut) -> list[list[str | int | float]]:
    header: list[str | int | float] = ["Ad", "Tələbə nömrəsi", "Qrup", "İştirak", "Ümumi", "Faiz"]
    header += [
        _safe(f"{meeting.opened_at.astimezone(BAKU).date().isoformat()} {meeting.title}".strip())
        for meeting in report.sessions
    ]
    rows = [header]
    for row in report.rows:
        rows.append(
            [
                _safe(row.display_name),
                row.university_id or "",
                row.group or "",
                row.attended,
                row.total,
                round(row.rate * 100, 1),
                *("+" if mark else "-" for mark in row.marks),
            ]
        )
    return rows


def to_csv(report: AttendanceReportOut) -> bytes:
    out = io.StringIO()
    csv.writer(out, lineterminator="\r\n").writerows(_table(report))
    # The byte-order mark makes Excel open the file as UTF-8, so Azerbaijani letters survive.
    return codecs.BOM_UTF8 + out.getvalue().encode()


def to_xlsx(report: AttendanceReportOut) -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Davamiyyət"
    for row in _table(report):
        sheet.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
