"""Import of the exam timetable (§6.1, D-097).

One row is one exam of one offering, keyed by the offering and its start. Rows that collide with another exam
for the same students, the same offering or the same room are accepted and reported as warnings in the preview:
staff may have planned the overlap (a split sitting), and the product cannot know.
"""

import uuid
from collections import defaultdict
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import select

from app.core.time import BAKU
from app.modules.academics import parsing
from app.modules.academics.importers import ImportRun, ImportSpec, ParsedRow, RowIssue
from app.modules.academics.models import CourseOfferingGroup, ImportKind
from app.modules.academics.parsing import Column
from app.modules.exams.models import ExamSlot
from app.modules.exams.service import MAX_DURATION
from app.modules.schedule.imports import _OFFERING_COLUMNS, Catalogue


def _baku(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=BAKU)


class ExamSlotsImport(ImportSpec):
    kind = ImportKind.EXAM_SLOTS
    columns = (
        *_OFFERING_COLUMNS,
        Column("date", parsing.calendar_date),
        Column("starts_at", parsing.clock_time),
        Column("ends_at", parsing.clock_time),
        Column("room_code", parsing.code(), required=False),
    )
    unique = (
        ("subject_code", "year", "term", "offering_code", "group_codes", "date", "starts_at"),
    )

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        if values["ends_at"] <= values["starts_at"]:
            return [("times_out_of_order", "ends_at")]
        window = _baku(values["date"], values["ends_at"]) - _baku(
            values["date"], values["starts_at"]
        )
        if window > MAX_DURATION:
            return [("window_too_long", "ends_at")]
        return []

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        catalogue = await Catalogue.load(run, rows)
        resolved: list[tuple[ParsedRow, uuid.UUID, uuid.UUID | None, datetime, datetime]] = []
        for row in rows:
            info = catalogue.offering(run, row)
            room_ok, room_id = catalogue.room(run, row)
            if info is None or not room_ok:
                continue
            values = row.values
            resolved.append(
                (
                    row,
                    info.offering.id,
                    room_id,
                    _baku(values["date"], values["starts_at"]),
                    _baku(values["date"], values["ends_at"]),
                )
            )
        if not resolved:
            return

        offering_ids = {offering_id for _, offering_id, *_ in resolved}
        existing = {
            (slot.course_offering_id, slot.starts_at): slot
            for slot in await run.session.scalars(
                select(ExamSlot).where(ExamSlot.course_offering_id.in_(offering_ids))
            )
        }
        for row, offering_id, room_id, starts_at, ends_at in resolved:
            fields = {
                "ends_at": ends_at,
                "room_code": row.values["room_code"],
                "room_id": room_id,
            }
            run.upsert(
                existing.get((offering_id, starts_at)),
                ExamSlot,
                fields,
                course_offering_id=offering_id,
                starts_at=starts_at,
            )
            run.exam_offerings.add(offering_id)
        await self._warn(run, resolved)

    async def _warn(
        self,
        run: ImportRun,
        resolved: list[tuple[ParsedRow, uuid.UUID, uuid.UUID | None, datetime, datetime]],
    ) -> None:
        first = min(starts for *_, starts, _ in resolved)
        last = max(ends for *_, ends in resolved)
        others = list(
            await run.session.scalars(
                select(ExamSlot).where(ExamSlot.starts_at < last, ExamSlot.ends_at > first)
            )
        )
        offerings = {slot.course_offering_id for slot in others} | {r[1] for r in resolved}
        groups: defaultdict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for offering_id, group_id in await run.session.execute(
            select(
                CourseOfferingGroup.course_offering_id, CourseOfferingGroup.academic_group_id
            ).where(CourseOfferingGroup.course_offering_id.in_(offerings))
        ):
            groups[offering_id].add(group_id)

        # What the database holds, minus what this file rewrites, plus what this file adds.
        rewritten = {(r[1], r[3]) for r in resolved}
        pool: list[tuple[uuid.UUID, datetime, datetime, str | None]] = [
            (slot.course_offering_id, slot.starts_at, slot.ends_at, slot.room_code)
            for slot in others
            if (slot.course_offering_id, slot.starts_at) not in rewritten
        ]
        added = [(r[1], r[3], r[4], r[0].values["room_code"]) for r in resolved]
        for index, (row, offering_id, _, starts_at, ends_at) in enumerate(resolved):
            room = row.values["room_code"]
            seen: set[str] = set()
            for other_offering, other_start, other_end, other_room in [
                *pool,
                *(a for i, a in enumerate(added) if i != index),
            ]:
                if not (other_start < ends_at and other_end > starts_at):
                    continue
                if other_offering == offering_id:
                    seen.add("overlaps_offering")
                elif groups[offering_id] & groups[other_offering]:
                    seen.add("overlaps_group")
                if room and other_room == room:
                    seen.add("overlaps_room")
            for code in sorted(seen):
                run.warnings.append(RowIssue(code, row.number, "starts_at"))
