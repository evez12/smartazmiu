"""Upper/lower week parity (§6.1): computed from the semester start and the semester's override table."""

from collections.abc import Iterable
from datetime import date, timedelta

from app.modules.schedule.models import WeekParity

_FLIPPED = {WeekParity.UPPER: WeekParity.LOWER, WeekParity.LOWER: WeekParity.UPPER}


def week_start(day: date) -> date:
    return day - timedelta(days=day.isoweekday() - 1)


def parity_on(
    day: date, semester_starts_on: date, overrides: Iterable[tuple[date, WeekParity]] = ()
) -> WeekParity:
    """The week containing the semester's first day is an upper week; weeks alternate from there.

    An override restarts the alternation: from its week on, weeks alternate beginning with its parity, so a
    holiday week that "does not count" is one override on the following Monday. The latest override at or
    before ``day``'s week wins.
    """
    monday = week_start(day)
    anchor, parity = week_start(semester_starts_on), WeekParity.UPPER
    for week, override in sorted(overrides):
        if week <= monday:
            anchor, parity = week, override
    weeks = (monday - anchor).days // 7
    return parity if weeks % 2 == 0 else _FLIPPED[parity]


def takes_place(entry_parity: WeekParity, week_parity: WeekParity) -> bool:
    return entry_parity is WeekParity.EVERY or entry_parity is week_parity
