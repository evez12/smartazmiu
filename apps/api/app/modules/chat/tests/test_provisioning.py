import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Faculty,
    Semester,
    SemesterTerm,
    Subject,
)
from app.modules.chat.bus import user_topic
from app.modules.chat.models import Channel, ChannelMember, ChannelTopic, ChannelType, Message
from app.modules.chat.provisioning import ChannelProvisioner
from app.modules.chat.snowflake import created_at_of, floor_id
from app.modules.users.models import User, UserStatus
from app.workers import main
from tests.support import FakeJobs

Seed = Callable[..., Awaitable[None]]

AYSEL = "aysel.mammadova@smartazmiu.test"
RAMIN = "ramin.aliyev@smartazmiu.test"
LEYLA = "leyla.hasanova@smartazmiu.test"  # teaches Statistika to 765a2 and curates the group
RAUF = "rauf.mammadov@smartazmiu.test"


async def user_id(db: AsyncSession, email: str) -> uuid.UUID:
    found = await db.scalar(select(User.id).where(User.email == email))
    assert found is not None
    return found


async def offering_id(db: AsyncSession, subject: str, year: int, code: str) -> uuid.UUID:
    found = await db.scalar(
        select(CourseOffering.id)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .join(Semester, Semester.id == CourseOffering.semester_id)
        .where(Subject.code == subject, Semester.year == year, CourseOffering.code == code)
        .order_by(Semester.term == SemesterTerm.SPRING)
        .limit(1)
    )
    assert found is not None
    return found


async def course_channel(db: AsyncSession, subject: str, year: int, code: str) -> Channel:
    offering = await offering_id(db, subject, year, code)
    channel = await db.scalar(
        select(Channel)
        .where(Channel.course_offering_id == offering)
        .execution_options(populate_existing=True)
    )
    assert channel is not None
    return channel


async def community_channel(db: AsyncSession, subject: str) -> Channel:
    channel = await db.scalar(
        select(Channel)
        .join(Subject, Subject.id == Channel.subject_id)
        .where(Channel.type == ChannelType.SUBJECT_COMMUNITY, Subject.code == subject)
        .execution_options(populate_existing=True)
    )
    assert channel is not None
    return channel


async def group_channel(db: AsyncSession, code: str) -> Channel:
    channel = await db.scalar(
        select(Channel)
        .join(AcademicGroup, AcademicGroup.id == Channel.academic_group_id)
        .where(AcademicGroup.code == code)
    )
    assert channel is not None
    return channel


async def members(db: AsyncSession, channel: Channel) -> set[str]:
    rows = await db.scalars(
        select(User.email)
        .join(ChannelMember, ChannelMember.user_id == User.id)
        .where(ChannelMember.channel_id == channel.id)
    )
    return {email for email in rows if email}


async def provision(db: AsyncSession) -> Any:
    return await ChannelProvisioner(db).run()


async def test_the_registry_becomes_channels_with_members_and_topics(
    db: AsyncSession, seed: Seed, jobs: FakeJobs
) -> None:
    await seed()
    # Every applied file that can create channels or move people woke the job once.
    assert jobs.provisions == 9
    result = await provision(db)
    counts = [
        await db.scalar(select(func.count()).select_from(table)) or 0
        for table in (Subject, CourseOffering, AcademicGroup, Faculty)
    ]
    assert result.channels_created == sum(counts)

    statistics = await course_channel(db, "IQT-2102", 2026, "765a2")
    assert statistics.name == "Statistika"
    assert not statistics.is_archived
    course_members = await members(db, statistics)
    assert len(course_members) == 22 + 1
    assert {AYSEL, RAMIN, LEYLA} <= course_members
    # The teacher is in the course channel but never in the subject community (§5.1).
    community = await community_channel(db, "IQT-2102")
    community_members = await members(db, community)
    assert AYSEL in community_members
    assert LEYLA not in community_members
    assert len(community_members) == 40  # every student of 765a1 and 765a2 takes it this semester

    group = await group_channel(db, "765a2")
    assert group.name == "765a2"
    assert len(await members(db, group)) == 22 + 1  # its students and the curator

    faculty = await db.scalar(
        select(Channel).join(Faculty, Faculty.id == Channel.faculty_id).where(Faculty.code == "TIQ")
    )
    assert faculty is not None
    assert LEYLA not in await members(db, faculty)
    assert {AYSEL, RAMIN} <= await members(db, faculty)

    topics = await db.scalars(
        select(ChannelTopic.slug)
        .where(ChannelTopic.channel_id == community.id)
        .order_by(ChannelTopic.position)
    )
    assert list(topics) == ["umumi", "suallar", "materiallar", "imtahan-hazirligi", "meslehet"]
    course_topics = await db.scalars(
        select(ChannelTopic.name)
        .where(ChannelTopic.channel_id == statistics.id)
        .order_by(ChannelTopic.position)
    )
    assert list(course_topics) == ["ümumi", "suallar", "materiallar", "imtahan-hazırlığı"]
    assert not await db.scalar(
        select(func.count()).select_from(ChannelTopic).where(ChannelTopic.channel_id == group.id)
    )

    # Courses of a semester that has ended are archived read-only, with their members kept.
    past = await course_channel(db, "IKT-1101", 2025, "765a2")
    assert (past.is_archived, past.is_readonly) == (True, True)
    assert AYSEL in await members(db, past)

    # Applying twice changes nothing.
    again = await provision(db)
    assert not again.changed


async def test_people_leave_channels_when_the_registry_moves_them(
    db: AsyncSession, seed: Seed
) -> None:
    await seed()
    await provision(db)
    aysel, ramin, leyla, rauf = [await user_id(db, e) for e in (AYSEL, RAMIN, LEYLA, RAUF)]
    statistics = await course_channel(db, "IQT-2102", 2026, "765a2")
    community = await community_channel(db, "IQT-2102")
    group = await group_channel(db, "765a2")
    past = await course_channel(db, "IKT-1101", 2025, "765a2")
    message_id = floor_id(datetime.now(UTC))
    await db.execute(
        insert(Message).values(
            id=message_id,
            created_at=created_at_of(message_id),
            channel_id=group.id,
            author_id=ramin,
            body="Sabahkı seminar 1-305 otağındadır.",
            client_msg_id=uuid.uuid4(),
        )
    )

    # A dropped enrollment leaves the course channel and the community, not the group.
    await db.execute(
        update(Enrollment)
        .where(
            Enrollment.user_id == aysel,
            Enrollment.course_offering_id == statistics.course_offering_id,
        )
        .values(status=EnrollmentStatus.DROPPED)
    )
    # A transfer to 765a1 leaves 765a2 and its course channels, and joins the new group.
    target = await db.scalar(select(AcademicGroup.id).where(AcademicGroup.code == "765a1"))
    await db.execute(update(User).where(User.id == ramin).values(academic_group_id=target))
    # A replaced teacher leaves the course channel; the newcomer joins it.
    await db.execute(
        update(CourseOfferingTeacher)
        .where(
            CourseOfferingTeacher.course_offering_id == statistics.course_offering_id,
            CourseOfferingTeacher.teacher_id == leyla,
        )
        .values(teacher_id=rauf)
    )
    await db.commit()
    result = await provision(db)

    assert AYSEL not in await members(db, statistics)
    assert AYSEL not in await members(db, community)
    assert AYSEL in await members(db, group)
    assert RAMIN not in await members(db, group)
    assert RAMIN not in await members(db, statistics)
    assert RAMIN in await members(db, await group_channel(db, "765a1"))
    assert RAMIN in await members(db, community)  # still takes Statistika, in another group now
    assert LEYLA not in await members(db, statistics)
    assert RAUF in await members(db, statistics)
    assert LEYLA in await members(db, group)  # still the curator
    # Archived channels keep their membership as it was (D-061).
    assert RAMIN in await members(db, past)
    removed = set(result.removed)
    assert {(statistics.id, aysel), (group.id, ramin), (statistics.id, leyla)} <= removed
    assert (statistics.id, rauf) in set(result.added)
    # Messages and their authors stay (§13.1).
    assert await db.scalar(select(Message.author_id).where(Message.id == message_id)) == ramin

    # An account that becomes inactive leaves every open channel.
    await db.execute(update(User).where(User.id == aysel).values(status=UserStatus.INACTIVE))
    await db.commit()
    await provision(db)
    assert AYSEL not in await members(db, group)
    assert AYSEL in await members(db, past)
    await db.execute(delete(Message).where(Message.id == message_id))
    await db.commit()


async def test_a_renamed_group_renames_its_channel_and_a_reopened_semester_unarchives(
    db: AsyncSession, seed: Seed
) -> None:
    await seed()
    await provision(db)
    await db.execute(
        update(Subject).where(Subject.code == "IQT-2102").values(name_az="Statistika-1")
    )
    await db.execute(
        update(Semester)
        .where(Semester.year == 2025, Semester.term == SemesterTerm.FALL)
        .values(ends_on=datetime(2027, 1, 31).date())
    )
    await db.commit()
    result = await provision(db)
    assert result.channels_created == 0
    assert (await course_channel(db, "IQT-2102", 2026, "765a2")).name == "Statistika-1"
    assert (await community_channel(db, "IQT-2102")).name == "Statistika-1"
    reopened = await course_channel(db, "IKT-1101", 2025, "765a2")
    assert (reopened.is_archived, reopened.is_readonly) == (False, False)
    assert reopened.id in result.state_changed


async def test_the_job_tells_connected_sockets_about_revoked_access(
    db: AsyncSession, seed: Seed, settings: Settings
) -> None:
    await seed()
    await provision(db)
    aysel = await user_id(db, AYSEL)
    statistics = await course_channel(db, "IQT-2102", 2026, "765a2")
    await db.execute(
        update(Enrollment)
        .where(
            Enrollment.user_id == aysel,
            Enrollment.course_offering_id == statistics.course_offering_id,
        )
        .values(status=EnrollmentStatus.DROPPED)
    )
    await db.commit()

    listener = Redis.from_url(str(settings.redis_url), decode_responses=True)
    pubsub = listener.pubsub()
    await pubsub.subscribe(user_topic(aysel))
    ctx: dict[str, Any] = {}
    await main.startup(ctx)
    try:
        assert await main.provision_channels(ctx) == 2  # the course channel and the community
        events = []
        for _ in range(50):
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message:
                events.append(json.loads(message["data"]))
            if len(events) == 2:
                break
            await asyncio.sleep(0)
    finally:
        await main.shutdown(ctx)
        await pubsub.aclose()
        await listener.aclose()
    assert {event["type"] for event in events} == {"membership.revoked"}
    assert str(statistics.id) in {event["data"]["channel_id"] for event in events}
