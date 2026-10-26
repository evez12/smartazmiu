import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.modules.chat.access import ChannelAccess
from app.modules.chat.bus import ChatBus
from app.modules.chat.messages import MessageService
from app.modules.chat.models import (
    ChannelMember,
    ChannelTopic,
    MemberRole,
    Message,
    MessageClientId,
)
from app.modules.chat.partitions import partition_name
from app.modules.chat.policy import ExamWindow, NoExamWindows, Reason
from app.modules.chat.snowflake import Snowflake, created_at_of, floor_id
from app.modules.chat.tests.test_snowflake import WallClock
from app.modules.users.service import CurrentUser, UserService
from tests.test_jobs import _closed_port

from .conftest import MakeChannel, MakePerson, Person


class FixedExams:
    def __init__(self, *windows: ExamWindow) -> None:
        self.items = list(windows)

    async def windows(self, channel_ids: list[uuid.UUID], at: datetime) -> list[ExamWindow]:
        return [window for window in self.items if window.channel_id in channel_ids]


async def current(db: AsyncSession, person: Person) -> CurrentUser:
    user = await UserService(db).current(person.id)
    assert user is not None
    return user


def service(
    db: AsyncSession, app: FastAPI, *, exams: object = None, bus: Redis | None = None
) -> MessageService:
    access = ChannelAccess(db, app.state.redis, exams or NoExamWindows())  # type: ignore[arg-type]
    return MessageService(db, access, app.state.snowflake, ChatBus(bus or app.state.redis))


async def test_two_concurrent_sends_of_one_client_id_make_one_message(
    engine: AsyncEngine, app: FastAPI, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    """D-058: the second send waits on the first one's key and returns the same message and ack."""
    aysel = await person()
    room = await channel(aysel)
    user = await current(db, aysel)
    client_msg_id = uuid.uuid4()
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def send() -> tuple[str, bool]:
        async with sessions() as session:
            outcome = await service(session, app).send(
                user, room, "Sual: imtahan neçədədir?", client_msg_id
            )
            return outcome.message.id, outcome.created

    first, second = await asyncio.gather(send(), send())
    assert first[0] == second[0]
    assert sorted([first[1], second[1]]) == [False, True]
    assert await db.scalar(select(func.count()).select_from(Message)) == 1
    assert await db.scalar(select(func.count()).select_from(MessageClientId)) == 1


async def test_a_message_is_kept_even_when_publishing_fails(
    app: FastAPI, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    """Redis outage (§13.5): persistence comes first, so a lost publish loses nothing."""
    aysel = await person()
    room = await channel(aysel)
    broken = Redis(host="127.0.0.1", port=_closed_port(), socket_connect_timeout=0.2)
    try:
        outcome = await service(db, app, bus=broken).send(
            await current(db, aysel), room, "Bu mesaj saxlanmalıdır.", uuid.uuid4()
        )
    finally:
        await broken.aclose()
    assert outcome.created
    stored = await db.scalar(select(Message.body).where(Message.id == int(outcome.message.id)))
    assert stored == "Bu mesaj saxlanmalıdır."
    assert await db.scalar(
        select(Message.body_tsv.op("@@")(func.to_tsquery("simple", "saxlanmalidir")))
    )


async def test_sends_fail_with_a_typed_error_when_no_id_can_be_issued(
    app: FastAPI, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel = await person()
    room = await channel(aysel)
    user = await current(db, aysel)
    # The lease is no longer confirmed (Redis A gone for more than 50 s, ADR 0002).
    lease = app.state.snowflake.lease
    confirmed = lease.confirmed_at
    lease.confirmed_at = float("-inf")
    try:
        with pytest.raises(AppError) as refused:
            await service(db, app).send(user, room, "Salam", uuid.uuid4())
        assert (refused.value.code, refused.value.status_code) == ("chat.unavailable", 503)
    finally:
        lease.confirmed_at = confirmed

    # A month without a partition (the daily job stopped): typed error, nothing half-written.
    clock = WallClock(datetime(2040, 3, 1, tzinfo=UTC))
    future = MessageService(
        db,
        ChannelAccess(db, app.state.redis, NoExamWindows()),
        Snowflake(lease, clock_ms=clock, sleep=clock.sleep),
        ChatBus(app.state.redis),
    )
    with pytest.raises(AppError) as missing:
        await future.send(user, room, "Salam", uuid.uuid4())
    assert missing.value.code == "chat.unavailable"
    assert await db.scalar(select(func.count()).select_from(MessageClientId)) == 0


async def test_bodies_topics_and_client_ids_are_checked(
    app: FastAPI, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel, ramin = await person(), await person("Ramin", "Əliyev")
    room, other = await channel(aysel, ramin), await channel(aysel, name="Başqa")
    foreign_topic = await db.scalar(
        insert(ChannelTopic)
        .values(channel_id=other, slug="umumi", name="ümumi", position=0, is_default=True)
        .returning(ChannelTopic.id)
    )
    await db.commit()
    messages = service(db, app)
    user = await current(db, aysel)
    for text_, code in (("   \n ", "chat.message_empty"), ("ə" * 4001, "chat.message_too_long")):
        with pytest.raises(AppError) as refused:
            await messages.send(user, room, text_, uuid.uuid4())
        assert refused.value.code == code
    with pytest.raises(AppError) as wrong_topic:
        await messages.send(user, room, "Salam", uuid.uuid4(), topic_id=foreign_topic)
    assert wrong_topic.value.code == "chat.topic_not_found"
    # Someone else's client id never returns their message.
    key = uuid.uuid4()
    await messages.send(user, room, "Salam", key)
    with pytest.raises(AppError) as taken:
        await messages.send(await current(db, ramin), room, "Salam", key)
    assert (taken.value.code, taken.value.status_code) == ("chat.duplicate_client_id", 409)


async def test_slow_mode_counts_per_user_and_spares_moderators(
    app: FastAPI, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel, nigar = await person(), await person("Nigar", "İsmayılova")
    room = await channel(aysel, nigar, slow_mode_seconds=30)
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.user_id == nigar.id)
        .values(role=MemberRole.MODERATOR)
    )
    await db.commit()
    access = ChannelAccess(db, app.state.redis, NoExamWindows())
    student, moderator = await current(db, aysel), await current(db, nigar)
    assert (await access.claim_send(student, room)).allowed
    second = await access.claim_send(student, room)
    assert second.reason is Reason.SLOW_MODE
    assert 0 < (second.retry_after or 0) <= 30
    assert (await access.claim_send(moderator, room)).allowed
    assert (await access.claim_send(moderator, room)).allowed


async def test_exam_windows_come_from_the_provider_and_merge(
    app: FastAPI, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel = await person()
    room = await channel(aysel)
    now = datetime.now(UTC)
    exams = FixedExams(
        ExamWindow(room, now - timedelta(minutes=10), now + timedelta(minutes=50)),
        ExamWindow(room, now - timedelta(minutes=5), now + timedelta(minutes=90)),
        ExamWindow(room, now + timedelta(hours=5), now + timedelta(hours=6)),
    )
    access = ChannelAccess(db, app.state.redis, exams)
    state = await access.state(await current(db, aysel), room)
    assert state.exam_until == now + timedelta(minutes=90)
    with pytest.raises(AppError) as refused:
        await service(db, app, exams=exams).send(
            await current(db, aysel), room, "Cavab B-dir", uuid.uuid4()
        )
    assert refused.value.code == "chat.exam_mode"
    assert refused.value.details["until"] == (now + timedelta(minutes=90)).isoformat()


async def test_history_pages_across_monthly_partitions_with_pruning(
    app: FastAPI, person: MakePerson, channel: MakeChannel, db: AsyncSession
) -> None:
    aysel = await person()
    room = await channel(aysel)
    user = await current(db, aysel)
    today = datetime.now(UTC)
    this_month = today.replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    next_month = (this_month + timedelta(days=32)).replace(day=1)
    ids = []
    for index in range(60):
        moment = (this_month if index < 30 else next_month) + timedelta(minutes=index)
        message_id = floor_id(moment) + index
        ids.append(message_id)
        await db.execute(
            insert(Message).values(
                id=message_id,
                created_at=created_at_of(message_id),
                channel_id=room,
                author_id=aysel.id,
                body=f"Mesaj {index}",
                client_msg_id=uuid.uuid4(),
            )
        )
    await db.commit()
    messages = service(db, app)
    latest = await messages.history(user, room, limit=50)
    assert [int(m.id) for m in latest.messages] == ids[10:]
    assert latest.has_more
    older = await messages.history(user, room, before=ids[10], limit=50)
    assert [int(m.id) for m in older.messages] == ids[:10]
    assert not older.has_more
    forward = await messages.history(user, room, after=ids[25], limit=10)
    assert [int(m.id) for m in forward.messages] == ids[26:36]
    # Page sizes are capped at 100, so 1,000 asked returns all 60 here without error.
    assert len((await messages.history(user, room, limit=1000)).messages) == 60

    # The created_at bound derived from the cursor confines the scan to the cursor's month (ADR 0002).
    plan = "\n".join(
        await db.scalars(
            text(
                "EXPLAIN SELECT id FROM messages WHERE channel_id = :channel AND id < :before"
                " AND created_at <= :bound ORDER BY id DESC LIMIT 51"
            ),
            {"channel": room, "before": ids[10], "bound": created_at_of(ids[10])},
        )
    )
    assert partition_name(this_month.date()) in plan
    assert partition_name(next_month.date()) not in plan
