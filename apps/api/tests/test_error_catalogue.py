"""Every error code a coursework, community or attendance service raises has a localized message (D-094)."""

import re
from pathlib import Path

import pytest

from app.core.i18n import ERROR_MESSAGES

MODULES = Path(__file__).parents[1] / "app" / "modules"
CODE = re.compile(r'AppError\(\s*"([a-z_]+\.[a-z_]+)"')
# submission_blocker() returns these suffixes, and the service raises them as ``assignments.<suffix>``.
BLOCKERS = ("not_student", "not_available", "graded", "closed")


@pytest.mark.parametrize("module", ["assignments", "quizzes", "community", "attendance"])
def test_every_raised_code_has_an_azerbaijani_and_english_message(module: str) -> None:
    raised = {
        code
        for path in (MODULES / module).glob("*.py")
        for code in CODE.findall(path.read_text(encoding="utf-8"))
    }
    assert raised, module
    missing = sorted(code for code in raised if code not in ERROR_MESSAGES)
    assert missing == []
    assert all({"az", "en"} <= ERROR_MESSAGES[code].keys() for code in raised)


def test_every_submission_blocker_has_a_message() -> None:
    assert all(f"assignments.{blocker}" in ERROR_MESSAGES for blocker in BLOCKERS)
