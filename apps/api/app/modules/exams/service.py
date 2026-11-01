import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, and_, delete, exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.academics.coursework import offering_labels, teaching
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingGroup,
    Enrollment,
    EnrollmentStatus,
)
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.campus.models import Room
from app.modules.chat.bus import ChatBus
from app.modules.chat.models import Channel, ChannelType
from app.modules.exams.models import ExamSlot
from app.modules.exams.schemas import (
    ExamOverlapOut,
    ExamSlotIn,
    ExamSlotOut,
    ExamSlotUpdateIn,
)
from app.modules.users.service import CurrentUser

MANAGE = "exams.manage"
MAX_DURATION = timedelta(hours=12)


async def channels_of(session: AsyncSession, offering_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    """The course channels and subject communities whose exam mode depends on these offerings."""
    ids = set(offering_ids)
    if not ids:
        return []
    subjects = select(CourseOffering.subject_id).where(CourseOffering.id.in_(ids))
    return list(
        await session.scalars(
            select(Channel.id).where(
                or_(
                    and_(
                        Channel.type == ChannelType.COURSE_OFFERING,
                        Channel.course_offering_id.in_(ids),
                    ),
                    and_(
                        Channel.type == ChannelType.SUBJECT_COMMUNITY,
                        Channel.subject_id.in_(subjects),
                    ),
                )
            )
        )
    )


async def overlaps_of(session: AsyncSession, slot: ExamSlot) -> list[tuple[str, ExamSlot]]:
    """Exams that run at the same time as ``slot`` for the same offering, a shared group or the same room."""
    my_groups = select(CourseOfferingGroup.academic_group_id).where(
        CourseOfferingGroup.course_offering_id == slot.course_offering_id
    )
    sharing = set(
        await session.scalars(
            select(CourseOfferingGroup.course_offering_id).where(
                CourseOfferingGroup.academic_group_id.in_(my_groups)
            )
        )
    ) | {slot.course_offering_id}
    wanted: list[ColumnElement[bool]] = [ExamSlot.course_offering_id.in_(sharing)]
    if slot.room_code:
        wanted.append(ExamSlot.room_code == slot.room_code)
    others = await session.scalars(
        select(ExamSlot)
        .where(
            ExamSlot.id != slot.id,
            ExamSlot.starts_at < slot.ends_at,
            ExamSlot.ends_at > slot.starts_at,
            or_(*wanted),
        )
        .order_by(ExamSlot.starts_at)
    )
    found: list[tuple[str, ExamSlot]] = []
    for other in others:
        if other.course_offering_id == slot.course_offering_id:
            found.append(("offering", other))
        elif other.course_offering_id in sharing:
            found.append(("group", other))
        else:
            found.append(("room", other))
    return found


class ExamService:
    def __init__(self, session: AsyncSession, bus: ChatBus) -> None:
        self.session = session
        self.bus = bus

    # --- reading -----------------------------------------------------------------------------

    async def _out(self, slots: list[ExamSlot], *, with_overlaps: bool) -> list[ExamSlotOut]:
        if not slots:
            return []
        overlaps = (
            {slot.id: await overlaps_of(self.session, slot) for slot in slots}
            if with_overlaps
            else {}
        )
        offering_ids = {slot.course_offering_id for slot in slots}
        offering_ids |= {
            other.course_offering_id for pairs in overlaps.values() for _, other in pairs
        }
        labels = await offering_labels(self.session, offering_ids)
        return [
            ExamSlotOut(
                id=str(slot.id),
                offering=labels[slot.course_offering_id],
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                room_code=slot.room_code,
                overlaps=[
                    ExamOverlapOut(
                        kind=kind,
                        slot_id=str(other.id),
                        offering=labels[other.course_offering_id],
                        starts_at=other.starts_at,
                        ends_at=other.ends_at,
                    )
                    for kind, other in overlaps.get(slot.id, [])
                ],
            )
            for slot in slots
        ]

    def _mine(self, user: CurrentUser) -> object:
        enrolled = select(Enrollment.course_offering_id).where(
            Enrollment.user_id == user.id, Enrollment.status == EnrollmentStatus.ACTIVE
        )
        return or_(
            ExamSlot.course_offering_id.in_(enrolled),
            ExamSlot.course_offering_id.in_(teaching(user)),
        )

    async def my_exams(self, user: CurrentUser, limit: int = 100) -> list[ExamSlotOut]:
        """Exams of the offerings the user attends or teaches that have not ended, soonest first."""
        slots = list(
            await self.session.scalars(
                select(ExamSlot)
                .where(self._mine(user), ExamSlot.ends_at > utc_now())  # type: ignore[arg-type]
                .order_by(ExamSlot.starts_at, ExamSlot.id)
                .limit(limit)
            )
        )
        return await self._out(slots, with_overlaps=False)

    async def all_exams(self, *, include_past: bool, limit: int = 300) -> list[ExamSlotOut]:
        query = select(ExamSlot).order_by(ExamSlot.starts_at, ExamSlot.id).limit(limit)
        if not include_past:
            query = query.where(ExamSlot.ends_at > utc_now())
        return await self._out(list(await self.session.scalars(query)), with_overlaps=True)

    # --- writing -----------------------------------------------------------------------------

    async def _room(self, code: str | None) -> tuple[str | None, uuid.UUID | None]:
        if code is None or not code.strip():
            return None, None
        wanted = code.strip()
        room = await self.session.scalar(select(Room).where(Room.code == wanted))
        if room is None:
            raise AppError("exams.unknown_room", 422)
        return room.code, room.id

    @staticmethod
    def _check_window(starts_at: datetime, ends_at: datetime) -> None:
        if ends_at - starts_at > MAX_DURATION:
            raise AppError("exams.window_too_long", 422)

    async def create(self, actor: CurrentUser, body: ExamSlotIn) -> ExamSlotOut:
        self._check_window(body.starts_at, body.ends_at)
        if not await self.session.scalar(
            select(exists().where(CourseOffering.id == body.course_offering_id))
        ):
            raise AppError("exams.offering_not_found", 404)
        room_code, room_id = await self._room(body.room_code)
        slot = ExamSlot(
            course_offering_id=body.course_offering_id,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            room_code=room_code,
            room_id=room_id,
        )
        self.session.add(slot)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError("exams.duplicate", 409) from exc
        record_audit(
            self.session,
            AuditAction.EXAM_SLOT_CREATED,
            actor_id=actor.id,
            target_type="exam_slot",
            target_id=slot.id,
            details={"course_offering_id": str(slot.course_offering_id)},
        )
        await self.session.commit()
        await self._announce([slot.course_offering_id])
        return (await self._out([slot], with_overlaps=True))[0]

    async def update(
        self, actor: CurrentUser, slot_id: uuid.UUID, body: ExamSlotUpdateIn
    ) -> ExamSlotOut:
        slot = await self._slot(slot_id)
        self._check_window(body.starts_at, body.ends_at)
        room_code, room_id = await self._room(body.room_code)
        slot.starts_at, slot.ends_at = body.starts_at, body.ends_at
        slot.room_code, slot.room_id = room_code, room_id
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError("exams.duplicate", 409) from exc
        record_audit(
            self.session,
            AuditAction.EXAM_SLOT_EDITED,
            actor_id=actor.id,
            target_type="exam_slot",
            target_id=slot.id,
            details={"course_offering_id": str(slot.course_offering_id)},
        )
        await self.session.commit()
        # Exam mode is re-evaluated at once: a window that moved, or that already started, shows on open screens.
        await self._announce([slot.course_offering_id])
        return (await self._out([slot], with_overlaps=True))[0]

    async def remove(self, actor: CurrentUser, slot_id: uuid.UUID) -> None:
        slot = await self._slot(slot_id)
        offering_id = slot.course_offering_id
        record_audit(
            self.session,
            AuditAction.EXAM_SLOT_DELETED,
            actor_id=actor.id,
            target_type="exam_slot",
            target_id=slot.id,
            details={"course_offering_id": str(offering_id)},
        )
        await self.session.execute(delete(ExamSlot).where(ExamSlot.id == slot_id))
        await self.session.commit()
        await self._announce([offering_id])

    async def _slot(self, slot_id: uuid.UUID) -> ExamSlot:
        slot = await self.session.get(ExamSlot, slot_id)
        if slot is None:
            raise AppError("exams.not_found", 404)
        return slot

    async def _announce(self, offering_ids: Iterable[uuid.UUID]) -> None:
        await self.bus.channels_changed(await channels_of(self.session, offering_ids))
