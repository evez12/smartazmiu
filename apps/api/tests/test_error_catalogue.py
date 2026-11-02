"""Every error code a coursework, community or attendance service raises has a localized message (D-094)."""

import re
from pathlib import Path

import pytest

from app.core.i18n import ERROR_MESSAGES, SUPPORTED_LANGUAGES, negotiate_language

MODULES = Path(__file__).parents[1] / "app" / "modules"
CODE = re.compile(r'AppError\(\s*"([a-z_]+\.[a-z_]+)"')
# submission_blocker() returns these suffixes, and the service raises them as ``assignments.<suffix>``.
AZERBAIJANI_ONLY = re.compile("[əƏğĞıİşŞ]")
CYRILLIC = re.compile("[а-яА-Я]")
BLOCKERS = ("not_student", "not_available", "graded", "closed")


@pytest.mark.parametrize("module", ["assignments", "quizzes", "community", "attendance", "exams"])
def test_every_raised_code_has_an_azerbaijani_english_and_russian_message(module: str) -> None:
    raised = {
        code
        for path in (MODULES / module).glob("*.py")
        for code in CODE.findall(path.read_text(encoding="utf-8"))
    }
    assert raised, module
    missing = sorted(code for code in raised if code not in ERROR_MESSAGES)
    assert missing == []
    assert all({"az", "en", "ru"} <= ERROR_MESSAGES[code].keys() for code in raised)


def test_every_submission_blocker_has_a_message() -> None:
    assert all(f"assignments.{blocker}" in ERROR_MESSAGES for blocker in BLOCKERS)


def test_every_code_has_all_three_languages_and_keeps_the_azerbaijani_letters_out_of_the_others() -> (
    None
):
    assert ERROR_MESSAGES
    for code, texts in ERROR_MESSAGES.items():
        assert set(texts) == set(SUPPORTED_LANGUAGES), code
        assert not AZERBAIJANI_ONLY.search(texts["en"]), code
        assert not AZERBAIJANI_ONLY.search(texts["ru"]), code
        assert CYRILLIC.search(texts["ru"]), code


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "az"),
        ("ru-RU,ru;q=0.9,en;q=0.8", "ru"),
        ("en-GB,en;q=0.9", "en"),
        ("de-DE,de;q=0.9", "az"),
        ("ru;q=0.5,en;q=0.9", "en"),
    ],
)
def test_the_language_follows_accept_language(header: str | None, expected: str) -> None:
    assert negotiate_language(header) == expected
