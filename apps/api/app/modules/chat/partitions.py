"""Monthly partitions of ``messages`` and retention of the client-id lookup table (ADR 0002, D-058)."""

from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import delete, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import MessageClientId

logger = structlog.get_logger(__name__)

FUTURE_MONTHS = 3
CLIENT_ID_RETENTION = timedelta(days=7)
PURGE_BATCH = 5000


def _month(year: int, month: int) -> date:
    return date(year + (month - 1) // 12, (month - 1) % 12 + 1, 1)


def partition_name(month: date) -> str:
    return f"messages_y{month.year}m{month.month:02d}"


async def existing_partitions(session: AsyncSession) -> set[str]:
    rows = await session.scalars(
        text(
            "SELECT child.relname FROM pg_inherits"
            " JOIN pg_class parent ON parent.oid = pg_inherits.inhparent"
            " JOIN pg_class child ON child.oid = pg_inherits.inhrelid"
            " WHERE parent.relname = 'messages'"
        )
    )
    return set(rows)


async def ensure_partitions(session: AsyncSession, today: date | None = None) -> list[str]:
    """Creates the current month and the next three if missing; safe to run any number of times."""
    today = today or datetime.now(UTC).date()
    created = []
    existing = await existing_partitions(session)
    for offset in range(FUTURE_MONTHS + 1):
        start = _month(today.year, today.month + offset)
        end = _month(today.year, today.month + offset + 1)
        name = partition_name(start)
        if name in existing:
            continue
        # Identifiers and bounds come from dates, never from input.
        await session.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF messages"
                f" FOR VALUES FROM ('{start.isoformat()}T00:00:00+00')"
                f" TO ('{end.isoformat()}T00:00:00+00')"
            )
        )
        created.append(name)
    await session.commit()
    if created:
        logger.info("message_partitions_created", partitions=created)
    return created


async def current_partition_exists(session: AsyncSession, today: date | None = None) -> bool:
    today = today or datetime.now(UTC).date()
    return partition_name(_month(today.year, today.month)) in await existing_partitions(session)


async def purge_client_ids(session: AsyncSession, now: datetime | None = None) -> int:
    """Deletes lookup rows older than seven days in batches; a rerun finds nothing left to delete."""
    cutoff = (now or datetime.now(UTC)) - CLIENT_ID_RETENTION
    purged = 0
    while True:
        batch = (
            select(MessageClientId.channel_id, MessageClientId.client_msg_id)
            .where(MessageClientId.created_at < cutoff)
            .limit(PURGE_BATCH)
        )
        result = await session.execute(
            delete(MessageClientId).where(
                tuple_(MessageClientId.channel_id, MessageClientId.client_msg_id).in_(batch)
            )
        )
        await session.commit()
        purged += result.rowcount  # type: ignore[attr-defined]
        if result.rowcount < PURGE_BATCH:  # type: ignore[attr-defined]
            return purged
