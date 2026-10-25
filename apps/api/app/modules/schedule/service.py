"""The signed-in user's classes on concrete dates: weekly entries expanded by parity, with changes applied."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from enum import StrEnum

from sqlalchemy import ColumnElement, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Semester,
    Subject,
)
from app.modules.campus.models import Building, Floor, Room
from app.modules.schedule.models import (
    ClassType,
    ScheduleChange,
    ScheduleEntry,
    ScheduleEntryGroup,
    WeekParity,
    WeekParityOverride,
)
from app.modules.schedule.parity import parity_on, takes_place
from app.modules.users.models import User


class OccurrenceStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    CHANGED = "changed"
    """Same day, but another time, room or teacher."""
    MOVED_AWAY = "moved_away"
    """Shown on the original day; the class takes place on another day."""
    MOVED_HERE = "moved_here"
    """Shown on the new day of a moved class."""


@dataclass(frozen=True, slots=True)
class RoomPlace:
    code: str
    name: str
    building_name: str
    floor_name: str


@dataclass(slots=True)
class Occurrence:
    entry_id: uuid.UUID
    day: date
    starts_at: time
    ends_at: time
    subject: Subject
    class_type: ClassType
    room: RoomPlace | None
    teachers: list[str]
    groups: list[str]
    status: OccurrenceStatus
    original_day: date
    original_starts_at: time
    moved_to: tuple[date, time, time] | None = None
    room_changed: bool = False
    teacher_changed: bool = False
    note: str = ""


@dataclass(slots=True)
class ScheduleDay:
    day: date
    parity: WeekParity | None
    """None outside every semester (holidays between terms)."""
    occurrences: list[Occurrence] = field(default_factory=list)


MAX_RANGE_DAYS = 42


def _visible_to(user_id: uuid.UUID) -> ColumnElement[bool]:
    """Entries the user attends or teaches. The filter is part of the query, never applied afterwards."""
    own_group = select(User.academic_group_id).where(User.id == user_id).scalar_subquery()
    restricted = exists().where(ScheduleEntryGroup.schedule_entry_id == ScheduleEntry.id)
    for_own_group = exists().where(
        ScheduleEntryGroup.schedule_entry_id == ScheduleEntry.id,
        ScheduleEntryGroup.academic_group_id == own_group,
    )
    attends = and_(
        exists().where(
            Enrollment.course_offering_id == ScheduleEntry.course_offering_id,
            Enrollment.user_id == user_id,
            Enrollment.status != EnrollmentStatus.DROPPED,
        ),
        or_(~restricted, for_own_group),
    )
    teaches = or_(
        ScheduleEntry.teacher_id == user_id,
        and_(
            ScheduleEntry.teacher_id.is_(None),
            exists().where(
                CourseOfferingTeacher.course_offering_id == ScheduleEntry.course_offering_id,
                CourseOfferingTeacher.teacher_id == user_id,
            ),
        ),
    )
    return or_(attends, teaches)


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def days(self, user_id: uuid.UUID, start: date, end: date) -> list[ScheduleDay]:
        """Every day from ``start`` to ``end`` inclusive, with the user's classes in time order."""
        semesters = list(
            await self.session.scalars(
                select(Semester).where(Semester.starts_on <= end, Semester.ends_on >= start)
            )
        )
        overrides: defaultdict[uuid.UUID, list[tuple[date, WeekParity]]] = defaultdict(list)
        if semesters:
            for override in await self.session.scalars(
                select(WeekParityOverride).where(
                    WeekParityOverride.semester_id.in_([s.id for s in semesters])
                )
            ):
                overrides[override.semester_id].append((override.week_starts_on, override.parity))

        visible = _visible_to(user_id)
        rows = await self.session.execute(
            select(ScheduleEntry, CourseOffering, Subject, Semester)
            .join(CourseOffering, CourseOffering.id == ScheduleEntry.course_offering_id)
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(
                ScheduleEntry.active_from <= end,
                or_(ScheduleEntry.active_until.is_(None), ScheduleEntry.active_until >= start),
                Semester.starts_on <= end,
                Semester.ends_on >= start,
                visible,
            )
        )
        entries = {
            entry.id: (entry, offering, subject, sem) for entry, offering, subject, sem in rows
        }
        # Changes: of visible entries, on or onto a day in the range, plus classes the user substitutes in.
        change_rows = await self.session.execute(
            select(ScheduleChange, ScheduleEntry, CourseOffering, Subject, Semester)
            .join(ScheduleEntry, ScheduleEntry.id == ScheduleChange.schedule_entry_id)
            .join(CourseOffering, CourseOffering.id == ScheduleEntry.course_offering_id)
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .where(
                or_(
                    ScheduleChange.occurs_on.between(start, end),
                    ScheduleChange.new_date.between(start, end),
                ),
                or_(visible, ScheduleChange.teacher_id == user_id),
            )
        )
        changes: dict[tuple[uuid.UUID, date], ScheduleChange] = {}
        # Entries the user sees only because they substitute in some of their classes: just those days.
        substitute_days: defaultdict[uuid.UUID, set[date]] = defaultdict(set)
        for change, entry, offering, subject, semester in change_rows:
            changes[(entry.id, change.occurs_on)] = change
            if entry.id not in entries or entry.id in substitute_days:
                entries[entry.id] = (entry, offering, subject, semester)
                substitute_days[entry.id].add(change.occurs_on)

        names = await self._names(
            entries.values(),
            {c.teacher_id for c in changes.values() if c.teacher_id},
            {c.room_id for c in changes.values() if c.room_id},
        )
        days = {
            day: ScheduleDay(day, self._parity(day, semesters, overrides))
            for day in _dates(start, end)
        }

        def occurrence_on(day: date, entry_id: uuid.UUID) -> Occurrence:
            entry, offering, subject, _ = entries[entry_id]
            return Occurrence(
                entry_id=entry.id,
                day=day,
                starts_at=entry.starts_at,
                ends_at=entry.ends_at,
                subject=subject,
                class_type=entry.class_type,
                room=names.rooms.get(entry.room_id) if entry.room_id else None,
                teachers=[names.people[entry.teacher_id]]
                if entry.teacher_id in names.people
                else names.offering_teachers[offering.id],
                groups=names.entry_groups.get(entry.id) or names.offering_groups[offering.id],
                status=OccurrenceStatus.SCHEDULED,
                original_day=day,
                original_starts_at=entry.starts_at,
            )

        # Regular occurrences on their own day.
        for day, schedule_day in days.items():
            for entry_id, (entry, _, _, semester) in entries.items():
                if not _occurs(entry, semester, day, overrides):
                    continue
                if entry_id in substitute_days and day not in substitute_days[entry_id]:
                    continue
                day_change = changes.get((entry_id, day))
                occurrence = occurrence_on(day, entry_id)
                if day_change is not None:
                    _apply_change(occurrence, day_change, names)
                schedule_day.occurrences.append(occurrence)

        # Classes moved onto a day in the range from any day (possibly outside it).
        for (entry_id, original_day), change in changes.items():
            if change.new_date is None or change.new_date == original_day:
                continue
            if change.new_date not in days:
                continue
            entry, _, _, semester = entries[entry_id]
            if not _occurs(entry, semester, original_day, overrides):
                continue
            occurrence = occurrence_on(original_day, entry_id)
            _apply_change(occurrence, change, names)
            if occurrence.moved_to is None:
                continue
            occurrence.day, occurrence.starts_at, occurrence.ends_at = occurrence.moved_to
            occurrence.moved_to = None
            occurrence.status = OccurrenceStatus.MOVED_HERE
            days[change.new_date].occurrences.append(occurrence)

        for schedule_day in days.values():
            schedule_day.occurrences.sort(
                key=lambda o: (
                    o.starts_at,
                    o.subject.name_az,
                    o.groups,
                    o.room.code if o.room else "",
                )
            )
        return list(days.values())

    @staticmethod
    def _parity(
        day: date,
        semesters: list[Semester],
        overrides: dict[uuid.UUID, list[tuple[date, WeekParity]]],
    ) -> WeekParity | None:
        for semester in semesters:
            if semester.starts_on <= day <= semester.ends_on:
                return parity_on(day, semester.starts_on, overrides.get(semester.id, ()))
        return None

    async def _names(
        self,
        entries: Iterable[tuple[ScheduleEntry, CourseOffering, Subject, Semester]],
        extra_people: set[uuid.UUID],
        extra_rooms: set[uuid.UUID],
    ) -> "_Names":
        rows = list(entries)
        names = _Names()
        offering_ids = {offering.id for _, offering, _, _ in rows}
        entry_ids = {entry.id for entry, _, _, _ in rows}
        people = {entry.teacher_id for entry, _, _, _ in rows if entry.teacher_id} | extra_people
        rooms = {entry.room_id for entry, _, _, _ in rows if entry.room_id} | extra_rooms
        if offering_ids:
            for offering_id, name in await self.session.execute(
                select(CourseOfferingTeacher.course_offering_id, User.display_name)
                .join(User, User.id == CourseOfferingTeacher.teacher_id)
                .where(CourseOfferingTeacher.course_offering_id.in_(offering_ids))
                .order_by(User.family_name, User.given_name)
            ):
                names.offering_teachers[offering_id].append(name)
            for offering_id, code in await self.session.execute(
                select(CourseOfferingGroup.course_offering_id, AcademicGroup.code)
                .join(AcademicGroup, AcademicGroup.id == CourseOfferingGroup.academic_group_id)
                .where(CourseOfferingGroup.course_offering_id.in_(offering_ids))
                .order_by(AcademicGroup.code)
            ):
                names.offering_groups[offering_id].append(code)
        if entry_ids:
            for entry_id, code in await self.session.execute(
                select(ScheduleEntryGroup.schedule_entry_id, AcademicGroup.code)
                .join(AcademicGroup, AcademicGroup.id == ScheduleEntryGroup.academic_group_id)
                .where(ScheduleEntryGroup.schedule_entry_id.in_(entry_ids))
                .order_by(AcademicGroup.code)
            ):
                names.entry_groups.setdefault(entry_id, []).append(code)
        if people:
            names.people = {
                user_id: name
                for user_id, name in await self.session.execute(
                    select(User.id, User.display_name).where(User.id.in_(people))
                )
            }
        if rooms:
            for room, floor, building in await self.session.execute(
                select(Room, Floor, Building)
                .join(Floor, Floor.id == Room.floor_id)
                .join(Building, Building.id == Floor.building_id)
                .where(Room.id.in_(rooms))
            ):
                names.rooms[room.id] = RoomPlace(
                    room.code, room.name_az, building.name_az, floor.name_az
                )
        return names


@dataclass(slots=True)
class _Names:
    offering_teachers: defaultdict[uuid.UUID, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    offering_groups: defaultdict[uuid.UUID, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    entry_groups: dict[uuid.UUID, list[str]] = field(default_factory=dict)
    people: dict[uuid.UUID, str] = field(default_factory=dict)
    rooms: dict[uuid.UUID, RoomPlace] = field(default_factory=dict)


def _dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _occurs(
    entry: ScheduleEntry,
    semester: Semester,
    day: date,
    overrides: dict[uuid.UUID, list[tuple[date, WeekParity]]],
) -> bool:
    if entry.weekday != day.isoweekday():
        return False
    if not semester.starts_on <= day <= semester.ends_on:
        return False
    if day < entry.active_from or (entry.active_until is not None and day > entry.active_until):
        return False
    return takes_place(
        entry.week_parity, parity_on(day, semester.starts_on, overrides.get(semester.id, ()))
    )


def _apply_change(occurrence: Occurrence, change: ScheduleChange, names: _Names) -> None:
    occurrence.note = change.note
    if change.cancelled:
        occurrence.status = OccurrenceStatus.CANCELLED
        return
    if change.room_id is not None:
        occurrence.room = names.rooms.get(change.room_id)
        occurrence.room_changed = True
    if change.teacher_id is not None and change.teacher_id in names.people:
        occurrence.teachers = [names.people[change.teacher_id]]
        occurrence.teacher_changed = True
    starts_at = change.new_starts_at or occurrence.starts_at
    ends_at = change.new_ends_at or occurrence.ends_at
    if change.new_date is not None and change.new_date != occurrence.original_day:
        # The original day keeps the original time, pointing to where the class went.
        occurrence.status = OccurrenceStatus.MOVED_AWAY
        occurrence.moved_to = (change.new_date, starts_at, ends_at)
    else:
        occurrence.status = OccurrenceStatus.CHANGED
        occurrence.starts_at, occurrence.ends_at = starts_at, ends_at
