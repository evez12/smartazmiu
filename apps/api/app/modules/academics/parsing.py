"""Cell parsers for import columns. Each returns the typed value or raises ``CellError`` with a stable code."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from app.core.text import normalize_az


class CellError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


Parser = Callable[[str], Any]


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    parse: Parser
    required: bool = True
    default: Any = None


_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+/-]*")
_UNIVERSITY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{2,31}")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# Letters of any script, joined by single spaces, hyphens or apostrophes ("Əli-Heydər", "O'Neil").
_PERSON_NAME = re.compile(r"[^\W\d_]+(?:[ '’-][^\W\d_]+)*")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DOTTED_DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_EXCEL_SERIAL = re.compile(r"\d{4,6}(?:\.\d+)?")
# U+FFFD and control characters appear when a file was decoded with the wrong code page; a "?"
# inside a word is what Excel writes for a letter the code page lacks (cp1254 has no "ə").
_BROKEN_TEXT = re.compile("[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|[^\\W\\d_]\\?|\\?[^\\W\\d_]")


def code(max_length: int = 20) -> Parser:
    def parse(value: str) -> str:
        if len(value) > max_length:
            raise CellError("too_long")
        if not _CODE.fullmatch(value):
            raise CellError("invalid_format")
        return value

    return parse


def code_list(max_length: int = 20) -> Parser:
    """Codes separated by ";" or ","; duplicates collapse, order is kept."""
    single = code(max_length)

    def parse(value: str) -> list[str]:
        items = [item.strip() for item in re.split(r"[;,]", value) if item.strip()]
        if not items:
            raise CellError("required")
        return list(dict.fromkeys(single(item) for item in items))

    return parse


def university_id(value: str) -> str:
    if not _UNIVERSITY_ID.fullmatch(value):
        raise CellError("invalid_format")
    return value


def university_id_list(value: str) -> list[str]:
    items = [item.strip() for item in re.split(r"[;,]", value) if item.strip()]
    return list(dict.fromkeys(university_id(item) for item in items))


def text(max_length: int) -> Parser:
    def parse(value: str) -> str:
        if _BROKEN_TEXT.search(value):
            raise CellError("invalid_characters")
        if len(value) > max_length:
            raise CellError("too_long")
        return value

    return parse


def person_name(value: str) -> str:
    if _BROKEN_TEXT.search(value) or not _PERSON_NAME.fullmatch(value):
        # Most often "?" where a code page had no "ə" (see FileEncoding.WINDOWS_1254).
        raise CellError("invalid_characters")
    if len(value) > 100:
        raise CellError("too_long")
    return value


def email(value: str) -> str:
    if len(value) > 320 or not _EMAIL.fullmatch(value):
        raise CellError("invalid_email")
    return value.lower()


def integer(minimum: int, maximum: int) -> Parser:
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise CellError("invalid_number") from exc
        if not minimum <= number <= maximum:
            raise CellError("out_of_range")
        return number

    return parse


def choice(options: Mapping[str, StrEnum]) -> Parser:
    """Matches case- and diacritic-insensitively, so "Payız", "payiz" and "PAYIZ" are the same value."""

    def parse(value: str) -> StrEnum:
        try:
            return options[normalize_az(value).folded]
        except KeyError as exc:
            raise CellError("invalid_choice") from exc

    return parse


_BOOLEANS = {
    "true": True,
    "false": False,
    "yes": True,
    "no": False,
    "1": True,
    "0": False,
    "beli": True,
    "xeyr": False,
}


def boolean(value: str) -> bool:
    try:
        return _BOOLEANS[normalize_az(value).folded]
    except KeyError as exc:
        raise CellError("invalid_choice") from exc


def calendar_date(value: str) -> date:
    """ISO ``2026-09-15`` or the local ``15.09.2026``; an Excel serial number is reported, not converted."""
    if match := _ISO_DATE.fullmatch(value):
        year, month, day = match.groups()
    elif match := _DOTTED_DATE.fullmatch(value):
        day, month, year = match.groups()
    elif _EXCEL_SERIAL.fullmatch(value):
        raise CellError("excel_date_serial")
    else:
        raise CellError("invalid_date")
    try:
        return date(int(year), int(month), int(day))
    except ValueError as exc:
        raise CellError("invalid_date") from exc
