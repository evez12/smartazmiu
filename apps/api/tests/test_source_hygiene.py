"""Invisible characters in source survive review unnoticed; they must be written as escapes."""

import unicodedata
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def test_sources_contain_no_invisible_or_control_characters() -> None:
    offenders = [
        f"{path.relative_to(API_ROOT)}:{number}"
        for directory in ("app", "alembic", "tests")
        for path in (API_ROOT / directory).rglob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if any(unicodedata.category(char) in {"Cf", "Co", "Cc"} and char != "\t" for char in line)
    ]
    assert offenders == []
