import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import Channel, ChannelType, Message, MessageClientId
from app.modules.chat.partitions import (
    current_partition_exists,
    ensure_partitions,
    existing_partitions,
    purge_client_ids,
)
from app.modules.chat.snowflake import floor_id


async def test_partitions_are_kept_three_months_ahead_idempotently(db: AsyncSession) -> None:
    created = await ensure_partitions(db, today=date(2031, 11, 15))
    try:
        assert created == [
            "messages_y2031m11",
            "messages_y2031m12",
            "messages_y2032m01",
            "messages_y2032m02",
        ]
        assert await ensure_partitions(db, today=date(2031, 11, 15)) == []
        assert await ensure_partitions(db, today=date(2031, 12, 1)) == ["messages_y2032m03"]
        assert await current_partition_exists(db, today=date(2032, 1, 31))
        assert not await current_partition_exists(db, today=date(2035, 1, 1))
    finally:
        for name in await existing_partitions(db):
            if name >= "messages_y2031":
                await db.execute(text(f"DROP TABLE {name}"))
        await db.commit()


async def test_the_running_month_exists_after_migrating(db: AsyncSession) -> None:
    assert await current_partition_exists(db)
    assert await ensure_partitions(db) == []


async def test_a_message_outside_every_partition_is_refused(db: AsyncSession) -> None:
    channel_id = await db.scalar(
        insert(Channel).values(type=ChannelType.FACULTY, name="Test").returning(Channel.id)
    )
    with pytest.raises(DBAPIError, match="no partition"):
        await db.execute(
            insert(Message).values(
                id=floor_id(datetime(2040, 1, 1, tzinfo=UTC)),
                created_at=datetime(2040, 1, 1, tzinfo=UTC),
                channel_id=channel_id,
                body="Salam",
                client_msg_id=uuid.uuid4(),
            )
        )
    await db.rollback()


async def test_client_ids_older_than_a_week_are_purged_once(db: AsyncSession) -> None:
    channel_id = await db.scalar(
        insert(Channel).values(type=ChannelType.FACULTY, name="Test").returning(Channel.id)
    )
    now = datetime.now(UTC)
    await db.execute(
        insert(MessageClientId),
        [
            {
                "channel_id": channel_id,
                "client_msg_id": uuid.uuid4(),
                "message_id": index,
                "message_created_at": now,
                "created_at": now - timedelta(days=age),
            }
            for index, age in enumerate([0, 3, 6, 8, 8, 30])
        ],
    )
    await db.commit()
    assert await purge_client_ids(db) == 3
    assert await purge_client_ids(db) == 0
    assert await db.scalar(select(func.count()).select_from(MessageClientId)) == 3
