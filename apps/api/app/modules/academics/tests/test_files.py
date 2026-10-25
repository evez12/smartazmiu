import io
import zipfile
from datetime import date, datetime

import pytest
from openpyxl import Workbook

from app.modules.academics import files
from app.modules.academics.files import FileEncoding, UnreadableFileError, read_table


def xlsx(rows: list[list[object]], merge: str | None = None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)
    if merge:
        sheet.merge_cells(merge)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_utf8_csv_with_bom_and_semicolons() -> None:
    data = "\ufeffCode ; name_az\r\nIQT-2101;Mikroiqtisadiyyat\r\n;\r\n\r\n".encode()
    table = read_table("fənlər.csv", data)
    assert table.encoding is FileEncoding.UTF8
    assert table.columns == ["code", "name_az"]
    assert [(row.number, row.cells) for row in table.rows] == [
        (2, {"code": "IQT-2101", "name_az": "Mikroiqtisadiyyat"})
    ]
    assert table.issues == []


def test_turkish_code_page_is_detected_for_azerbaijani_text() -> None:
    data = "code,name_az\nSOS-2104,Sosiologiya\nIQT-1201,İqtisadiyyata giriş\n".encode("cp1254")
    table = read_table("subjects.csv", data)
    assert table.encoding is FileEncoding.WINDOWS_1254
    assert table.rows[1].cells["name_az"] == "İqtisadiyyata giriş"


def test_cyrillic_code_page_is_detected_for_russian_text() -> None:
    data = "code,name_az\nIQT-2102,Статистика и эконометрика\n".encode("cp1251")
    table = read_table("subjects.csv", data)
    assert table.encoding is FileEncoding.WINDOWS_1251
    assert table.rows[0].cells["name_az"] == "Статистика и эконометрика"


def test_explicit_encoding_overrides_detection() -> None:
    data = "code,name_az\nIQT-2102,Статистика\n".encode("cp1251")
    table = read_table("subjects.csv", data, FileEncoding.WINDOWS_1254)
    assert table.encoding is FileEncoding.WINDOWS_1254
    with pytest.raises(UnreadableFileError) as caught:
        read_table("subjects.csv", data, FileEncoding.UTF8)
    assert caught.value.code == "import.encoding_mismatch"


def test_xlsx_cells_become_text_and_merged_cells_are_reported() -> None:
    data = xlsx(
        [
            ["year", "term", "starts_on", "Ends_On"],
            [2026, "Payız", datetime(2026, 9, 15), date(2027, 1, 31)],
            [2027.0, "Yaz", 46440, None],
            [2027, None, "2027-07-01", "2027-08-31"],
        ],
        merge="B3:B4",
    )
    table = read_table("Semestrlər.XLSX", data)
    assert table.encoding is None
    assert table.columns == ["year", "term", "starts_on", "ends_on"]
    assert table.rows[0].cells == {
        "year": "2026",
        "term": "Payız",
        "starts_on": "2026-09-15",
        "ends_on": "2027-01-31",
    }
    assert table.rows[1].cells["year"] == "2027"
    assert table.rows[1].cells["starts_on"] == "46440"
    assert [(issue.code, issue.row, issue.column) for issue in table.issues] == [
        ("merged_cells", 3, "term"),
        ("merged_cells", 4, "term"),
    ]


def test_merged_header_cells_are_a_file_problem() -> None:
    table = read_table("x.xlsx", xlsx([["code", None], ["MEM", "Memarlıq"]], merge="A1:B1"))
    assert [(issue.code, issue.row) for issue in table.issues] == [("merged_cells", None)]


def test_empty_files_are_reported() -> None:
    assert [issue.code for issue in read_table("x.csv", b"").issues] == ["empty_file"]
    assert [issue.code for issue in read_table("x.csv", b"code,name_az\n").issues] == ["empty_file"]


def test_row_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(files, "MAX_ROWS", 2)
    table = read_table("x.csv", b"code\nA\nB\nC\n")
    assert len(table.rows) == 2
    assert [issue.code for issue in table.issues] == ["too_many_rows"]


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("roster.pdf", b"%PDF-1.7", "import.unsupported_format"),
        ("roster.csv", b"PK\x03\x04zip", "import.unsupported_format"),
        ("roster.xlsx", b"code,name\n", "import.unsupported_format"),
        ("roster.xlsx", b"PK\x03\x04 not really a zip", "import.unreadable"),
        ("roster", b"code\n", "import.unsupported_format"),
    ],
)
def test_unreadable_uploads(name: str, data: bytes, code: str) -> None:
    with pytest.raises(UnreadableFileError) as caught:
        read_table(name, data)
    assert caught.value.code == code


def test_size_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(UnreadableFileError) as caught:
        read_table("x.csv", b"x" * (files.MAX_FILE_BYTES + 1))
    assert caught.value.code == "import.file_too_large"

    # A small archive that would expand far beyond the cap is refused before it is parsed.
    monkeypatch.setattr(files, "MAX_XLSX_UNCOMPRESSED_BYTES", 1000)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", "0" * 5000)
    with pytest.raises(UnreadableFileError) as caught:
        read_table("bomb.xlsx", buffer.getvalue())
    assert caught.value.code == "import.file_too_large"
