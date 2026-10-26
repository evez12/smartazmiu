"""The §5.7 consistency job: rows that refer to a message which no longer exists.

Tables about messages cannot have a foreign key to the partitioned ``messages`` table (ADR 0002). Services check
existence on write; this weekly job removes what slipped through (a partition dropped by retention, a manual
repair). It is idempotent: a second run finds nothing.
"""

from dataclasses import dataclass

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.snowflake import EPOCH_MS, TIMESTAMP_SHIFT

logger = structlog.get_logger(__name__)

BATCH = 5000
# Tables that carry message_id; attachments not yet sent (message_id NULL) are the orphan-upload job's.
REFERRING_TABLES = ("message_reactions", "message_mentions", "message_attachments")


def _orphans(table: str) -> str:
    # created_at is derived from the id (ADR 0002); a one-second range around it lets the planner prune
    # partitions without depending on floating-point equality.
    moment = f"to_timestamp((((r.message_id >> {TIMESTAMP_SHIFT}) + {EPOCH_MS}) / 1000.0))"
    # Only the constant names in REFERRING_TABLES are interpolated.
    return (
        f"SELECT r.ctid FROM {table} AS r WHERE r.message_id IS NOT NULL AND NOT EXISTS ("  # noqa: S608
        " SELECT 1 FROM messages AS m WHERE m.id = r.message_id"
        f" AND m.created_at BETWEEN {moment} - interval '1 second' AND {moment} + interval '1 second'"
        f") LIMIT {BATCH}"
    )


@dataclass(frozen=True, slots=True)
class ConsistencyReport:
    removed: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.removed.values())


async def remove_orphans(session: AsyncSession) -> ConsistencyReport:
    removed: dict[str, int] = {}
    for table in REFERRING_TABLES:
        count = 0
        while True:
            result = await session.execute(
                text(f"DELETE FROM {table} WHERE ctid IN ({_orphans(table)})")  # noqa: S608
            )
            await session.commit()
            deleted = int(getattr(result, "rowcount", 0) or 0)
            count += deleted
            if deleted < BATCH:
                break
        removed[table] = count
    report = ConsistencyReport(removed)
    if report.total:
        logger.warning("chat_orphans_removed", **removed)
    return report
