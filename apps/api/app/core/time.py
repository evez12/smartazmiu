from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

# All timestamps are stored in UTC; calendar decisions (current semester, "today") use Baku time (§1.3).
BAKU = ZoneInfo("Asia/Baku")


def utc_now() -> datetime:
    return datetime.now(UTC)


def baku_today() -> date:
    return datetime.now(BAKU).date()
