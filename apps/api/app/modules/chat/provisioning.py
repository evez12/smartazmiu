"""Channels and memberships derived from the academic registry (§5.1, D-030, D-061).

Every step is one set-based statement that compares the registry with the stored state and changes only the
difference, so a run that finds nothing to do writes nothing, and ARQ's at-least-once delivery is harmless
(§13.5). Runs are serialised by a transaction-level advisory lock.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    Boolean,
    ColumnElement,
    Select,
    and_,
    delete,
    exists,
    func,
    literal,
    literal_column,
    select,
    text,
    true,
    union,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import column, values

from app.core.time import baku_today
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Faculty,
    Semester,
    Specialty,
    Subject,
)
from app.modules.chat.models import (
    PROVISIONED_TYPES,
    Channel,
    ChannelMember,
    ChannelTopic,
    ChannelType,
    MemberRole,
)
from app.modules.chat.topics import DEFAULT_TOPICS
from app.modules.users.models import PersonType, User, UserStatus

# Arbitrary but fixed: "chat" in ASCII.
PROVISIONING_LOCK = 0x63686174

Pair = tuple[uuid.UUID, uuid.UUID]


@dataclass
class ProvisioningResult:
    channels_created: int = 0
    added: list[Pair] = field(default_factory=list)
    """(channel_id, user_id) memberships created."""
    removed: list[Pair] = field(default_factory=list)
    """(channel_id, user_id) memberships revoked; their sockets must be unsubscribed (§5.9)."""
    state_changed: list[uuid.UUID] = field(default_factory=list)
    """Channels archived or reopened."""

    @property
    def changed(self) -> bool:
        return bool(self.channels_created or self.added or self.removed or self.state_changed)


def _type(kind: ChannelType) -> ColumnElement[ChannelType]:
    return literal(kind, Channel.__table__.c.type.type)


def desired_members() -> Select[tuple[uuid.UUID, uuid.UUID]]:
    """(channel_id, user_id) for every provisioned channel that is not archived, from the registry.

    Course channel: students of the offering's groups with an enrollment that is not dropped, plus its teachers.
    Subject community: active enrollees of the subject in any group, no teachers. Academic group: its students and
    its curator. Faculty: the students of its groups. Only active accounts are members (§13.1).
    """
    active = User.status == UserStatus.ACTIVE
    student = User.person_type == PersonType.STUDENT
    open_channel = ~Channel.is_archived

    course_students = (
        select(Channel.id, Enrollment.user_id)
        .join(Enrollment, Enrollment.course_offering_id == Channel.course_offering_id)
        .join(User, User.id == Enrollment.user_id)
        .join(
            CourseOfferingGroup,
            and_(
                CourseOfferingGroup.course_offering_id == Channel.course_offering_id,
                CourseOfferingGroup.academic_group_id == User.academic_group_id,
            ),
        )
        .where(
            Channel.type == ChannelType.COURSE_OFFERING,
            open_channel,
            Enrollment.status != EnrollmentStatus.DROPPED,
            active,
        )
    )
    course_teachers = (
        select(Channel.id, CourseOfferingTeacher.teacher_id)
        .join(
            CourseOfferingTeacher,
            CourseOfferingTeacher.course_offering_id == Channel.course_offering_id,
        )
        .join(User, User.id == CourseOfferingTeacher.teacher_id)
        .where(Channel.type == ChannelType.COURSE_OFFERING, open_channel, active)
    )
    community = (
        select(Channel.id, Enrollment.user_id)
        .join(CourseOffering, CourseOffering.subject_id == Channel.subject_id)
        .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
        .join(User, User.id == Enrollment.user_id)
        .where(
            Channel.type == ChannelType.SUBJECT_COMMUNITY,
            open_channel,
            Enrollment.status == EnrollmentStatus.ACTIVE,
            active,
        )
    )
    group_students = (
        select(Channel.id, User.id)
        .join(User, User.academic_group_id == Channel.academic_group_id)
        .where(Channel.type == ChannelType.ACADEMIC_GROUP, open_channel, student, active)
    )
    group_curators = (
        select(Channel.id, AcademicGroup.curator_id)
        .join(AcademicGroup, AcademicGroup.id == Channel.academic_group_id)
        .join(User, User.id == AcademicGroup.curator_id)
        .where(Channel.type == ChannelType.ACADEMIC_GROUP, open_channel, active)
    )
    faculty_students = (
        select(Channel.id, User.id)
        .join(Specialty, Specialty.faculty_id == Channel.faculty_id)
        .join(AcademicGroup, AcademicGroup.specialty_id == Specialty.id)
        .join(User, User.academic_group_id == AcademicGroup.id)
        .where(Channel.type == ChannelType.FACULTY, open_channel, student, active)
    )
    combined = union(
        course_students,
        course_teachers,
        community,
        group_students,
        group_curators,
        faculty_students,
    ).subquery()
    return select(combined.c[0].label("channel_id"), combined.c[1].label("user_id"))


class ChannelProvisioner:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self) -> ProvisioningResult:
        """Creates missing channels and topics, syncs memberships, archives ended course channels; commits."""
        await self.session.execute(select(func.pg_advisory_xact_lock(PROVISIONING_LOCK)))
        result = ProvisioningResult()
        result.channels_created = await self._upsert_channels()
        await self._ensure_topics()
        # Members first: a channel created for a semester that has already ended gets its members once, then
        # it is archived and its membership stays as it was (D-061).
        result.added, result.removed = await self._sync_members()
        result.state_changed = await self._sync_archive()
        await self.session.commit()
        return result

    async def _upsert_channels(self) -> int:
        course = ChannelType.COURSE_OFFERING
        community = ChannelType.SUBJECT_COMMUNITY
        group = ChannelType.ACADEMIC_GROUP
        faculty = ChannelType.FACULTY
        # The selected columns differ per type, hence Any.
        sources: list[tuple[ChannelType, str, list[str], Any]] = [
            (
                course,
                "course_offering_id",
                ["subject_id", "course_offering_id"],
                select(_type(course), Subject.name_az, Subject.id, CourseOffering.id).join(
                    Subject, Subject.id == CourseOffering.subject_id
                ),
            ),
            (
                community,
                "subject_id",
                ["subject_id"],
                select(_type(community), Subject.name_az, Subject.id),
            ),
            (
                group,
                "academic_group_id",
                ["academic_group_id"],
                select(_type(group), AcademicGroup.code, AcademicGroup.id),
            ),
            (
                faculty,
                "faculty_id",
                ["faculty_id"],
                select(_type(faculty), Faculty.name_az, Faculty.id),
            ),
        ]
        created = 0
        for kind, key, columns, rows in sources:
            insert_rows = insert(Channel).from_select(
                ["type", "name", *columns], rows, include_defaults=False
            )
            # A renamed subject, group or faculty renames its channel; unchanged rows are not written. The
            # partial-index predicate is a constant so PostgreSQL can infer the index (an enum value, never input).
            upsert = insert_rows.on_conflict_do_update(
                index_elements=[key],
                index_where=text(f"type = '{kind.value}'"),
                set_={"name": insert_rows.excluded.name},
                where=Channel.name.is_distinct_from(insert_rows.excluded.name),
            ).returning(literal_column("xmax::text = '0'", Boolean))
            # xmax is 0 for a freshly inserted row; a renamed row carries the updating transaction.
            created += sum(1 for inserted in await self.session.scalars(upsert) if inserted)
        return created

    async def _ensure_topics(self) -> None:
        for kind, topics in DEFAULT_TOPICS.items():
            defaults = values(
                column("slug", ChannelTopic.__table__.c.slug.type),
                column("name", ChannelTopic.__table__.c.name.type),
                column("position", ChannelTopic.__table__.c.position.type),
                name="defaults",
            ).data([(topic.slug, topic.name, position) for position, topic in enumerate(topics)])
            await self.session.execute(
                insert(ChannelTopic)
                .from_select(
                    ["channel_id", "slug", "name", "position", "is_default"],
                    select(
                        Channel.id,
                        defaults.c.slug,
                        defaults.c.name,
                        defaults.c.position,
                        true(),
                    )
                    .select_from(Channel)
                    .join(defaults, true())
                    .where(Channel.type == kind),
                    include_defaults=False,
                )
                .on_conflict_do_nothing(index_elements=["channel_id", "slug"])
            )

    async def _sync_members(self) -> tuple[list[Pair], list[Pair]]:
        desired = desired_members().subquery()
        added = await self.session.execute(
            insert(ChannelMember)
            .from_select(
                ["channel_id", "user_id", "role"],
                select(
                    desired.c.channel_id,
                    desired.c.user_id,
                    literal(MemberRole.MEMBER, ChannelMember.__table__.c.role.type),
                ).where(
                    ~exists().where(
                        ChannelMember.channel_id == desired.c.channel_id,
                        ChannelMember.user_id == desired.c.user_id,
                    )
                ),
                include_defaults=False,
            )
            .on_conflict_do_nothing()
            .returning(ChannelMember.channel_id, ChannelMember.user_id)
        )
        added_pairs = [(channel_id, user_id) for channel_id, user_id in added]

        still_desired = desired_members().subquery()
        provisioned_open = select(Channel.id).where(
            Channel.type.in_(PROVISIONED_TYPES), ~Channel.is_archived
        )
        removed = await self.session.execute(
            delete(ChannelMember)
            .where(
                ChannelMember.channel_id.in_(provisioned_open),
                ~exists().where(
                    still_desired.c.channel_id == ChannelMember.channel_id,
                    still_desired.c.user_id == ChannelMember.user_id,
                ),
            )
            .returning(ChannelMember.channel_id, ChannelMember.user_id)
        )
        return added_pairs, [(channel_id, user_id) for channel_id, user_id in removed]

    async def _sync_archive(self) -> list[uuid.UUID]:
        """A course channel is archived and read-only once its semester has ended (Baku calendar, §5.1)."""
        ended = (
            select(CourseOffering.id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(Semester.ends_on < baku_today())
        )
        should_archive = Channel.course_offering_id.in_(ended)
        rows = await self.session.scalars(
            update(Channel)
            .where(
                Channel.type == ChannelType.COURSE_OFFERING,
                Channel.is_archived.is_distinct_from(should_archive),
            )
            .values(is_archived=should_archive, is_readonly=should_archive)
            .returning(Channel.id)
        )
        return list(rows)
