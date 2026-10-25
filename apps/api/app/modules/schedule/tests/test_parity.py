from datetime import date

import pytest

from app.modules.schedule.models import WeekParity
from app.modules.schedule.parity import parity_on, takes_place, week_start

UPPER, LOWER, EVERY = WeekParity.UPPER, WeekParity.LOWER, WeekParity.EVERY
# 2026 Payız starts on Tuesday 15 September.
STARTS = date(2026, 9, 15)


def test_week_starts_on_monday() -> None:
    assert week_start(date(2026, 9, 15)) == date(2026, 9, 14)
    assert week_start(date(2026, 9, 14)) == date(2026, 9, 14)
    assert week_start(date(2026, 9, 20)) == date(2026, 9, 14)


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        # The partial first week, including the Monday before the first day, is upper.
        (date(2026, 9, 14), UPPER),
        (date(2026, 9, 20), UPPER),
        # Boundary: Sunday → Monday flips.
        (date(2026, 9, 21), LOWER),
        (date(2026, 9, 27), LOWER),
        (date(2026, 9, 28), UPPER),
        (date(2026, 10, 26), UPPER),
        (date(2026, 11, 2), LOWER),
    ],
)
def test_weeks_alternate_from_the_semester_start(day: date, expected: WeekParity) -> None:
    assert parity_on(day, STARTS) is expected


def test_an_override_restarts_the_rhythm_from_its_week() -> None:
    # Without the override, the week of 16 November would be lower (week 10 of the semester).
    assert parity_on(date(2026, 11, 16), STARTS) is LOWER
    overrides = [(date(2026, 11, 16), UPPER)]

    # Weeks before the override are unchanged, up to the Sunday before it.
    assert parity_on(date(2026, 11, 9), STARTS, overrides) is UPPER
    assert parity_on(date(2026, 11, 15), STARTS, overrides) is UPPER
    # The override week and the weeks after it.
    assert parity_on(date(2026, 11, 16), STARTS, overrides) is UPPER
    assert parity_on(date(2026, 11, 22), STARTS, overrides) is UPPER
    assert parity_on(date(2026, 11, 23), STARTS, overrides) is LOWER
    assert parity_on(date(2026, 11, 30), STARTS, overrides) is UPPER


def test_the_latest_override_wins_whatever_their_order() -> None:
    overrides = [(date(2026, 12, 7), LOWER), (date(2026, 11, 16), UPPER)]
    assert parity_on(date(2026, 11, 30), STARTS, overrides) is UPPER
    assert parity_on(date(2026, 12, 7), STARTS, overrides) is LOWER
    assert parity_on(date(2026, 12, 14), STARTS, overrides) is UPPER


def test_every_week_entries_take_place_in_both_parities() -> None:
    assert takes_place(EVERY, UPPER)
    assert takes_place(EVERY, LOWER)
    assert takes_place(UPPER, UPPER)
    assert not takes_place(UPPER, LOWER)
    assert takes_place(LOWER, LOWER)
    assert not takes_place(LOWER, UPPER)
