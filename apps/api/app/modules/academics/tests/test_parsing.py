from datetime import date
from typing import Any

import pytest

from app.modules.academics import parsing
from app.modules.academics.importers import TERMS
from app.modules.academics.models import SemesterTerm
from app.modules.academics.parsing import CellError, Parser


def code_of(parser: Parser, value: str) -> str:
    with pytest.raises(CellError) as caught:
        parser(value)
    return caught.value.code


@pytest.mark.parametrize(
    ("parser", "value", "expected"),
    [
        (parsing.code(), "765a2", "765a2"),
        (parsing.code(64), "765a1+765a2", "765a1+765a2"),
        (parsing.code_list(), "765a1; 765a2,765a1", ["765a1", "765a2"]),
        (parsing.university_id, "T-10412", "T-10412"),
        (parsing.university_id_list, "T-10412;T-10519;", ["T-10412", "T-10519"]),
        (parsing.person_name, "Əli-Heydər", "Əli-Heydər"),
        (parsing.person_name, "Нигяр", "Нигяр"),
        (parsing.email, "Aysel.Mammadova@SmartAzMIU.test", "aysel.mammadova@smartazmiu.test"),
        (parsing.integer(0, 60), "10", 10),
        (parsing.choice(TERMS), "Payız", SemesterTerm.FALL),
        (parsing.choice(TERMS), "PAYIZ", SemesterTerm.FALL),
        (parsing.choice(TERMS), "spring", SemesterTerm.SPRING),
        (parsing.boolean, "Bəli", True),
        (parsing.boolean, "0", False),
        (parsing.calendar_date, "2026-09-15", date(2026, 9, 15)),
        (parsing.calendar_date, "15.09.2026", date(2026, 9, 15)),
        (parsing.text(20), "Mülki müdafiə", "Mülki müdafiə"),
    ],
)
def test_valid_cells(parser: Parser, value: str, expected: Any) -> None:
    assert parser(value) == expected


@pytest.mark.parametrize(
    ("parser", "value", "error"),
    [
        (parsing.code(), "765 a2", "invalid_format"),
        (parsing.code(5), "IQT-2101", "too_long"),
        (parsing.code_list(), " ; ", "required"),
        (parsing.university_id, "x", "invalid_format"),
        # Excel replaced "ə" with "?" when the file was saved in the Turkish code page.
        (parsing.person_name, "M?mm?dova", "invalid_characters"),
        (parsing.person_name, "Aysel2", "invalid_characters"),
        (parsing.person_name, "A" * 101, "too_long"),
        (parsing.email, "aysel.mammadova", "invalid_email"),
        (parsing.integer(0, 60), "ten", "invalid_number"),
        (parsing.integer(0, 60), "61", "out_of_range"),
        (parsing.choice(TERMS), "qış", "invalid_choice"),
        (parsing.boolean, "bəlkə", "invalid_choice"),
        (parsing.calendar_date, "46280", "excel_date_serial"),
        (parsing.calendar_date, "2026-02-30", "invalid_date"),
        (parsing.calendar_date, "09/15/2026", "invalid_date"),
        (parsing.text(20), "Mülki m\ufffddafiə", "invalid_characters"),
        (parsing.text(5), "Mikroiqtisadiyyat", "too_long"),
    ],
)
def test_invalid_cells(parser: Parser, value: str, error: str) -> None:
    assert code_of(parser, value) == error
