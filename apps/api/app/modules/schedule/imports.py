"""Import specifications for the timetable, its per-date changes and week parity overrides.

A timetable file describes the complete weekly schedule of every offering it mentions: entries of those offerings
that are missing from the file are removed. While a semester runs, edits take effect from the day of the import;
earlier weeks keep the timetable that applied then (DECISIONS D-041).
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Any

from sqlalchemy import delete, select, tuple_

from app.core.text import normalize_az
from app.core.time import baku_today
from app.modules.academics import parsing
from app.modules.academics.importers import TERMS, ImportRun, ImportSpec, ParsedRow
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    ImportKind,
    Semester,
    Subject,
)
from app.modules.academics.parsing import CellError, Column
from app.modules.campus.models import Room
from app.modules.schedule.models import (
    ClassType,
    ScheduleChange,
    ScheduleEntry,
    ScheduleEntryGroup,
    WeekParity,
    WeekParityOverride,
)
from app.modules.schedule.notifications import notify_changes
from app.modules.schedule.parity import parity_on, takes_place
from app.modules.users.models import PersonType, User

PARITIES = {
    "every": WeekParity.EVERY,
    "her hefte": WeekParity.EVERY,
    "upper": WeekParity.UPPER,
    "ust": WeekParity.UPPER,
    "lower": WeekParity.LOWER,
    "alt": WeekParity.LOWER,
}
CLASS_TYPES = {
    **{class_type.value: class_type for class_type in ClassType},
    "muhazire": ClassType.LECTURE,
    "laboratoriya": ClassType.LABORATORY,
}
CANCEL, CHANGE = "cancel", "change"
CHANGE_ACTIONS = {"cancel": CANCEL, "legv": CANCEL, "change": CHANGE, "deyisiklik": CHANGE}

_OFFERING_COLUMNS = (
    Column("subject_code", parsing.code()),
    Column("year", parsing.integer(2000, 2100)),
    Column("term", parsing.choice(TERMS)),
    Column("offering_code", parsing.code(64), required=False),
    Column("group_codes", parsing.code_list(), required=False, default=[]),
)


def _upper_or_lower(value: str) -> WeekParity:
    parity = parsing.choice(PARITIES)(value)
    if parity is WeekParity.EVERY:
        raise CellError("invalid_choice")
    return WeekParity(parity)


def _change_action(value: str) -> str:
    try:
        return CHANGE_ACTIONS[normalize_az(value).folded]
    except KeyError as exc:
        raise CellError("invalid_choice") from exc


def is_running(semester: Semester, today: date) -> bool:
    return semester.starts_on < today <= semester.ends_on


@dataclass(slots=True)
class OfferingInfo:
    offering: CourseOffering
    semester: Semester
    group_ids: set[uuid.UUID]
    teacher_ids: set[uuid.UUID]


class Catalogue:
    """Everything a schedule row may refer to, loaded with one query per table."""

    def __init__(self) -> None:
        self.subjects: dict[str, Subject] = {}
        self.semesters: dict[tuple[int, Any], Semester] = {}
        self.offerings: defaultdict[tuple[uuid.UUID, uuid.UUID], list[OfferingInfo]] = defaultdict(
            list
        )
        self.groups: dict[str, AcademicGroup] = {}
        self.rooms: dict[str, Room] = {}
        self.people: dict[str, User] = {}
        self.overrides: defaultdict[uuid.UUID, list[tuple[date, WeekParity]]] = defaultdict(list)

    @classmethod
    async def load(cls, run: ImportRun, rows: list[ParsedRow]) -> "Catalogue":
        catalogue = cls()
        values = [row.values for row in rows]
        catalogue.subjects = await run.lookup(
            Subject, Subject.code, (v["subject_code"] for v in values)
        )
        catalogue.semesters = await run.semesters(rows)
        catalogue.groups = await run.lookup(
            AcademicGroup, AcademicGroup.code, (c for v in values for c in v["group_codes"])
        )
        catalogue.rooms = await run.lookup(Room, Room.code, (v.get("room_code") for v in values))
        catalogue.people = await run.lookup(
            User, User.university_id, (v.get("teacher_id") for v in values)
        )

        semester_ids = {semester.id for semester in catalogue.semesters.values()}
        pairs = [
            (subject.id, semester.id)
            for subject in catalogue.subjects.values()
            for semester in catalogue.semesters.values()
        ]
        if not pairs:
            return catalogue
        offerings = list(
            await run.session.scalars(
                select(CourseOffering).where(
                    tuple_(CourseOffering.subject_id, CourseOffering.semester_id).in_(pairs)
                )
            )
        )
        by_id = {
            offering.id: OfferingInfo(
                offering,
                next(s for s in catalogue.semesters.values() if s.id == offering.semester_id),
                set(),
                set(),
            )
            for offering in offerings
        }
        if by_id:
            for offering_id, group_id in await run.session.execute(
                select(
                    CourseOfferingGroup.course_offering_id, CourseOfferingGroup.academic_group_id
                ).where(CourseOfferingGroup.course_offering_id.in_(by_id))
            ):
                by_id[offering_id].group_ids.add(group_id)
            for offering_id, teacher_id in await run.session.execute(
                select(
                    CourseOfferingTeacher.course_offering_id, CourseOfferingTeacher.teacher_id
                ).where(CourseOfferingTeacher.course_offering_id.in_(by_id))
            ):
                by_id[offering_id].teacher_ids.add(teacher_id)
        for info in by_id.values():
            catalogue.offerings[(info.offering.subject_id, info.offering.semester_id)].append(info)
        for override in await run.session.scalars(
            select(WeekParityOverride).where(WeekParityOverride.semester_id.in_(semester_ids))
        ):
            catalogue.overrides[override.semester_id].append(
                (override.week_starts_on, override.parity)
            )
        return catalogue

    def offering(self, run: ImportRun, row: ParsedRow) -> OfferingInfo | None:
        """The offering a row refers to, or None after reporting why it cannot be determined."""
        values = row.values
        subject = self.subjects.get(values["subject_code"])
        if subject is None:
            run.error(row, "unknown_reference", "subject_code")
            return None
        semester = self.semesters.get((values["year"], values["term"]))
        if semester is None:
            run.error(row, "unknown_reference", "year")
            return None
        if any(code not in self.groups for code in values["group_codes"]):
            run.error(row, "unknown_reference", "group_codes")
            return None
        candidates = self.offerings[(subject.id, semester.id)]
        wanted_groups = {self.groups[code].id for code in values["group_codes"]}
        if values["offering_code"] is not None:
            matches = [c for c in candidates if c.offering.code == values["offering_code"]]
        else:
            matches = [c for c in candidates if wanted_groups <= c.group_ids]
        if not matches:
            run.error(row, "unknown_reference", "offering_code")
            return None
        if len(matches) > 1:
            run.error(row, "ambiguous_offering", "offering_code")
            return None
        if not wanted_groups <= matches[0].group_ids:
            run.error(row, "group_not_in_offering", "group_codes")
            return None
        return matches[0]

    def entry_groups(self, info: OfferingInfo, row: ParsedRow) -> frozenset[uuid.UUID]:
        """The row's groups; naming every group of the offering is the same as naming none."""
        groups = frozenset(self.groups[code].id for code in row.values["group_codes"])
        return frozenset() if groups == info.group_ids else groups

    def room(self, run: ImportRun, row: ParsedRow) -> tuple[bool, uuid.UUID | None]:
        code = row.values.get("room_code")
        if code is None:
            return True, None
        room = self.rooms.get(code)
        if room is None:
            run.error(row, "unknown_reference", "room_code")
            return False, None
        return True, room.id

    def teacher(self, run: ImportRun, row: ParsedRow) -> tuple[bool, uuid.UUID | None]:
        university_id = row.values.get("teacher_id")
        if university_id is None:
            return True, None
        person = self.people.get(university_id)
        if person is None:
            run.error(row, "unknown_reference", "teacher_id")
            return False, None
        if person.person_type is not PersonType.TEACHER:
            run.error(row, "not_a_teacher", "teacher_id")
            return False, None
        return True, person.id

    def parity(self, semester: Semester, day: date) -> WeekParity:
        return parity_on(day, semester.starts_on, self.overrides[semester.id])


EntryKey = tuple[uuid.UUID, int, time, WeekParity, frozenset[uuid.UUID]]


async def _entry_groups(
    run: ImportRun, entry_ids: Iterable[uuid.UUID]
) -> defaultdict[uuid.UUID, set[uuid.UUID]]:
    ids = list(entry_ids)
    groups: defaultdict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    if ids:
        for entry_id, group_id in await run.session.execute(
            select(
                ScheduleEntryGroup.schedule_entry_id, ScheduleEntryGroup.academic_group_id
            ).where(ScheduleEntryGroup.schedule_entry_id.in_(ids))
        ):
            groups[entry_id].add(group_id)
    return groups


class WeekParityImport(ImportSpec):
    kind = ImportKind.WEEK_PARITY
    columns = (
        Column("year", parsing.integer(2000, 2100)),
        Column("term", parsing.choice(TERMS)),
        Column("week_starts_on", parsing.calendar_date),
        Column("parity", _upper_or_lower),
    )
    unique = (("year", "term", "week_starts_on"),)

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        if values["week_starts_on"].isoweekday() != 1:
            return [("not_monday", "week_starts_on")]
        return []

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        semesters = await run.semesters(rows)
        existing = {
            (o.semester_id, o.week_starts_on): o
            for o in await run.session.scalars(
                select(WeekParityOverride).where(
                    WeekParityOverride.semester_id.in_([s.id for s in semesters.values()])
                )
            )
        }
        for row in rows:
            values = row.values
            semester = semesters.get((values["year"], values["term"]))
            if semester is None:
                run.error(row, "unknown_reference", "year")
                continue
            if not semester.starts_on <= values["week_starts_on"] <= semester.ends_on:
                run.error(row, "outside_semester", "week_starts_on")
                continue
            run.upsert(
                existing.get((semester.id, values["week_starts_on"])),
                WeekParityOverride,
                {"parity": values["parity"]},
                semester_id=semester.id,
                week_starts_on=values["week_starts_on"],
            )


class ScheduleImport(ImportSpec):
    kind = ImportKind.SCHEDULE
    columns = (
        *_OFFERING_COLUMNS,
        Column("weekday", parsing.weekday),
        Column("starts_at", parsing.clock_time),
        Column("ends_at", parsing.clock_time),
        Column("week_parity", parsing.choice(PARITIES), required=False, default=WeekParity.EVERY),
        Column("class_type", parsing.choice(CLASS_TYPES)),
        Column("room_code", parsing.code(), required=False),
        Column("teacher_id", parsing.university_id, required=False),
    )
    unique = (
        (
            "subject_code",
            "year",
            "term",
            "offering_code",
            "group_codes",
            "weekday",
            "starts_at",
            "week_parity",
        ),
    )

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        if values["ends_at"] <= values["starts_at"]:
            return [("times_out_of_order", "ends_at")]
        return []

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        catalogue = await Catalogue.load(run, rows)
        today = baku_today()

        desired: dict[EntryKey, tuple[OfferingInfo, ParsedRow, dict[str, Any]]] = {}
        for row in rows:
            info = catalogue.offering(run, row)
            if info is None:
                continue
            room_ok, room_id = catalogue.room(run, row)
            teacher_ok, teacher_id = catalogue.teacher(run, row)
            if not (room_ok and teacher_ok):
                continue
            if teacher_id is not None and teacher_id not in info.teacher_ids:
                run.error(row, "teacher_not_in_offering", "teacher_id")
                continue
            values = row.values
            key: EntryKey = (
                info.offering.id,
                values["weekday"],
                values["starts_at"],
                values["week_parity"],
                catalogue.entry_groups(info, row),
            )
            if key in desired:
                # The same class written once with group codes and once without.
                run.error(row, "duplicate_in_file", "group_codes")
                continue
            desired[key] = (
                info,
                row,
                {
                    "ends_at": values["ends_at"],
                    "class_type": values["class_type"],
                    "room_id": room_id,
                    "teacher_id": teacher_id,
                },
            )
        if run.issues:
            return

        offerings = {info.offering.id: info for info, _, _ in desired.values()}
        current = list(
            await run.session.scalars(
                select(ScheduleEntry).where(
                    ScheduleEntry.course_offering_id.in_(offerings),
                    ScheduleEntry.active_until.is_(None),
                )
            )
        )
        groups = await _entry_groups(run, (entry.id for entry in current))
        # Offerings that never had a timetable get theirs for the whole semester: no past weeks to keep.
        scheduled_before = set(
            await run.session.scalars(
                select(ScheduleEntry.course_offering_id)
                .where(ScheduleEntry.course_offering_id.in_(offerings))
                .distinct()
            )
        )
        existing = {
            (
                e.course_offering_id,
                e.weekday,
                e.starts_at,
                e.week_parity,
                frozenset(groups[e.id]),
            ): e
            for e in current
        }

        for key, (info, _, fields) in desired.items():
            entry = existing.pop(key, None)
            if entry is not None and all(getattr(entry, k) == v for k, v in fields.items()):
                run.counts["unchanged"] += 1
                continue
            if entry is not None:
                if _keeps_history(entry, info.semester, today):
                    # Earlier weeks keep the old room/time/teacher; the edit applies from today.
                    run.counts["updated"] += 1
                    if run.write:
                        entry.active_until = today - timedelta(days=1)
                        await self._create(run, key, info, fields, today, history=True, count=False)
                else:
                    run.update(entry, fields)
                continue
            await self._create(
                run, key, info, fields, today, history=info.offering.id in scheduled_before
            )

        for entry in existing.values():
            run.counts["removed"] += 1
            if not run.write:
                continue
            semester = offerings[entry.course_offering_id].semester
            if _keeps_history(entry, semester, today):
                entry.active_until = today - timedelta(days=1)
            else:
                await run.session.execute(delete(ScheduleEntry).where(ScheduleEntry.id == entry.id))

    async def _create(
        self,
        run: ImportRun,
        key: EntryKey,
        info: OfferingInfo,
        fields: dict[str, Any],
        today: date,
        *,
        history: bool,
        count: bool = True,
    ) -> None:
        offering_id, weekday, starts_at, week_parity, group_ids = key
        semester = info.semester
        entry = ScheduleEntry(
            course_offering_id=offering_id,
            weekday=weekday,
            starts_at=starts_at,
            week_parity=week_parity,
            active_from=today if history and is_running(semester, today) else semester.starts_on,
            **fields,
        )
        if count:
            run.create(entry)
        elif run.write:
            run.session.add(entry)
        if run.write:
            await run.session.flush()
            run.session.add_all(
                ScheduleEntryGroup(schedule_entry_id=entry.id, academic_group_id=group_id)
                for group_id in group_ids
            )


def _keeps_history(entry: ScheduleEntry, semester: Semester, today: date) -> bool:
    """Whether the entry already took place this semester, so changing it must not rewrite past weeks."""
    return is_running(semester, today) and entry.active_from < today


class ScheduleChangesImport(ImportSpec):
    kind = ImportKind.SCHEDULE_CHANGES
    columns = (
        *_OFFERING_COLUMNS,
        Column("date", parsing.calendar_date),
        Column("starts_at", parsing.clock_time),
        Column("action", _change_action),
        Column("new_date", parsing.calendar_date, required=False),
        Column("new_starts_at", parsing.clock_time, required=False),
        Column("new_ends_at", parsing.clock_time, required=False),
        Column("room_code", parsing.code(), required=False),
        Column("teacher_id", parsing.university_id, required=False),
        Column("note", parsing.text(300), required=False, default=""),
    )
    unique = (
        ("subject_code", "year", "term", "offering_code", "group_codes", "date", "starts_at"),
    )

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        details = ("new_date", "new_starts_at", "new_ends_at", "room_code", "teacher_id")
        if values["action"] == CANCEL:
            return [("not_allowed_when_cancelled", name) for name in details if values[name]]
        if not any(values[name] for name in details):
            return [("change_without_details", "action")]
        if (values["new_starts_at"] is None) != (values["new_ends_at"] is None):
            missing = "new_ends_at" if values["new_ends_at"] is None else "new_starts_at"
            return [("required", missing)]
        if values["new_starts_at"] is not None and values["new_ends_at"] <= values["new_starts_at"]:
            return [("times_out_of_order", "new_ends_at")]
        return []

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        catalogue = await Catalogue.load(run, rows)
        resolved: list[tuple[ParsedRow, OfferingInfo]] = []
        for row in rows:
            info = catalogue.offering(run, row)
            if info is not None:
                resolved.append((row, info))

        offering_ids = {info.offering.id for _, info in resolved}
        entries: defaultdict[uuid.UUID, list[ScheduleEntry]] = defaultdict(list)
        if offering_ids:
            for entry in await run.session.scalars(
                select(ScheduleEntry).where(ScheduleEntry.course_offering_id.in_(offering_ids))
            ):
                entries[entry.course_offering_id].append(entry)
        groups = await _entry_groups(run, (e.id for es in entries.values() for e in es))

        matched: list[tuple[ParsedRow, ScheduleEntry, dict[str, Any]]] = []
        for row, info in resolved:
            values = row.values
            day: date = values["date"]
            semester = info.semester
            if not semester.starts_on <= day <= semester.ends_on:
                run.error(row, "outside_semester", "date")
                continue
            new_date: date | None = values["new_date"]
            if new_date is not None and not semester.starts_on <= new_date <= semester.ends_on:
                run.error(row, "outside_semester", "new_date")
                continue
            week_parity = catalogue.parity(semester, day)
            wanted_groups = catalogue.entry_groups(info, row)
            candidates = [
                entry
                for entry in entries[info.offering.id]
                if entry.weekday == day.isoweekday()
                and entry.starts_at == values["starts_at"]
                and takes_place(entry.week_parity, week_parity)
                and entry.active_from <= day
                and (entry.active_until is None or day <= entry.active_until)
                and (not values["group_codes"] or frozenset(groups[entry.id]) == wanted_groups)
            ]
            if not candidates:
                run.error(row, "no_class_on_date", "date")
                continue
            if len(candidates) > 1:
                run.error(row, "ambiguous_class", "group_codes")
                continue
            room_ok, room_id = catalogue.room(run, row)
            teacher_ok, teacher_id = catalogue.teacher(run, row)
            if not (room_ok and teacher_ok):
                continue
            cancelled = values["action"] == CANCEL
            matched.append(
                (
                    row,
                    candidates[0],
                    {
                        "cancelled": cancelled,
                        "new_date": new_date,
                        "new_starts_at": values["new_starts_at"],
                        "new_ends_at": values["new_ends_at"],
                        "room_id": room_id,
                        "teacher_id": teacher_id,
                        "note": values["note"],
                    },
                )
            )

        keys = [(entry.id, row.values["date"]) for row, entry, _ in matched]
        existing: dict[tuple[uuid.UUID, date], ScheduleChange] = {}
        if keys:
            existing = {
                (change.schedule_entry_id, change.occurs_on): change
                for change in await run.session.scalars(
                    select(ScheduleChange).where(
                        tuple_(ScheduleChange.schedule_entry_id, ScheduleChange.occurs_on).in_(keys)
                    )
                )
            }
        seen: set[tuple[uuid.UUID, date]] = set()
        touched: list[tuple[ScheduleChange, ScheduleEntry]] = []
        for row, entry, fields in matched:
            key = (entry.id, row.values["date"])
            if key in seen:
                run.error(row, "duplicate_in_file", "date")
                continue
            seen.add(key)
            previous = existing.get(key)
            differs = previous is None or any(
                getattr(previous, name) != value for name, value in fields.items()
            )
            change = run.upsert(
                previous,
                ScheduleChange,
                fields,
                schedule_entry_id=entry.id,
                occurs_on=row.values["date"],
            )
            if differs:
                touched.append((change, entry))
        if run.write and touched and not run.issues:
            # In the import's transaction: a failed apply rolls the notifications back with the data.
            await run.session.flush()
            await notify_changes(run.session, touched)
