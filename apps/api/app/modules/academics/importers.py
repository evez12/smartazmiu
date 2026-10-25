"""One import specification per entity kind: columns, natural key and the upsert against the database.

``process`` runs the same code for the preview (``write=False``) and the apply step, so a preview can never
disagree with what apply does. Rows are matched by natural keys (codes, university IDs); a row that is
missing from a file is never deleted or changed (DECISIONS D-031).
"""

import uuid
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

from sqlalchemy import delete, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.ids import uuid7
from app.core.text import search_key
from app.modules.academics import parsing
from app.modules.academics.files import Table
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Faculty,
    ImportKind,
    InstructionLanguage,
    Semester,
    SemesterTerm,
    Specialty,
    Subject,
)
from app.modules.academics.parsing import CellError, Column
from app.modules.users.models import PersonType, User, UserStatus

Entity = TypeVar("Entity")

MAX_STORED_ISSUES = 1000

TERMS = {
    "fall": SemesterTerm.FALL,
    "payiz": SemesterTerm.FALL,
    "spring": SemesterTerm.SPRING,
    "yaz": SemesterTerm.SPRING,
    "summer": SemesterTerm.SUMMER,
    "yay": SemesterTerm.SUMMER,
}
LANGUAGES = {language.value: language for language in InstructionLanguage}
PERSON_STATUSES = {
    "active": UserStatus.ACTIVE,
    "aktiv": UserStatus.ACTIVE,
    "inactive": UserStatus.INACTIVE,
    "deaktiv": UserStatus.INACTIVE,
}
ENROLLMENT_STATUSES = {status.value: status for status in EnrollmentStatus}


@dataclass(frozen=True, slots=True)
class RowIssue:
    code: str
    row: int | None = None
    """Excel row number; None for problems with the file as a whole (header, encoding, size)."""
    column: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"row": self.row, "column": self.column, "code": self.code}


@dataclass(slots=True)
class ParsedRow:
    number: int
    values: dict[str, Any]


class ImportRun:
    """One pass over a file: collected issues, change counts, and whether changes are written."""

    def __init__(self, session: AsyncSession, *, write: bool) -> None:
        self.session = session
        self.write = write
        self.issues: list[RowIssue] = []
        self.counts: Counter[str] = Counter(created=0, updated=0, unchanged=0)

    def error(self, row: ParsedRow, code: str, column: str | None = None) -> None:
        self.issues.append(RowIssue(code, row.number, column))

    def create(self, entity: Entity) -> Entity:
        self.counts["created"] += 1
        if self.write:
            self.session.add(entity)
        return entity

    def update(self, entity: object, fields: dict[str, Any]) -> None:
        changed = {name: value for name, value in fields.items() if getattr(entity, name) != value}
        self.counts["updated" if changed else "unchanged"] += 1
        if self.write:
            for name, value in changed.items():
                setattr(entity, name, value)

    def upsert(
        self, existing: Entity | None, model: type[Entity], fields: dict[str, Any], **keys: Any
    ) -> Entity:
        """Update ``existing`` or create ``model(**keys, **fields)``; ``keys`` are the natural key."""
        if existing is None:
            return self.create(model(**keys, **fields))
        self.update(existing, fields)
        return existing

    async def lookup(
        self, model: type[Entity], column: InstrumentedAttribute[Any], values: Iterable[Any]
    ) -> dict[Any, Entity]:
        wanted = {value for value in values if value is not None}
        if not wanted:
            return {}
        rows = await self.session.scalars(select(model).where(column.in_(wanted)))
        return {getattr(entity, column.key): entity for entity in rows}

    async def semesters(
        self, rows: Sequence[ParsedRow]
    ) -> dict[tuple[int, SemesterTerm], Semester]:
        years = {row.values["year"] for row in rows}
        if not years:
            return {}
        semesters = await self.session.scalars(select(Semester).where(Semester.year.in_(years)))
        return {(semester.year, semester.term): semester for semester in semesters}


class ImportSpec(ABC):
    kind: ClassVar[ImportKind]
    columns: ClassVar[tuple[Column, ...]]
    unique: ClassVar[tuple[tuple[str, ...], ...]]
    """Column combinations that must not repeat within a file; the first is the natural key."""

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        """Fill derived values and check rules spanning several cells; returns (code, column) issues."""
        return []

    @abstractmethod
    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None: ...

    def template(self) -> str:
        return ",".join(column.name for column in self.columns)


async def process(
    spec: ImportSpec, table: Table, session: AsyncSession, *, write: bool
) -> ImportRun:
    run = ImportRun(session, write=write)
    run.issues.extend(RowIssue(issue.code, issue.row, issue.column) for issue in table.issues)
    if not _check_header(spec, table, run) or not table.rows:
        return run

    rows: list[ParsedRow] = []
    for raw in table.rows:
        values: dict[str, Any] = {}
        problems: list[tuple[str, str]] = []
        for column in spec.columns:
            cell = raw.cells.get(column.name, "")
            if not cell:
                if column.required:
                    problems.append(("required", column.name))
                values[column.name] = column.default
                continue
            try:
                values[column.name] = column.parse(cell)
            except CellError as exc:
                problems.append((exc.code, column.name))
        if not problems:
            problems = spec.prepare(values)
        run.issues.extend(RowIssue(code, raw.number, name) for code, name in problems)
        if not problems:
            rows.append(ParsedRow(raw.number, values))

    flagged_rows = {issue.row for issue in table.issues}
    rows = [row for row in _drop_duplicates(spec, rows, run) if row.number not in flagged_rows]
    if rows:
        await spec.apply(run, rows)
    return run


def _check_header(spec: ImportSpec, table: Table, run: ImportRun) -> bool:
    if not table.columns:
        return False
    known = {column.name for column in spec.columns}
    issues = [
        RowIssue("missing_column", column=column.name)
        for column in spec.columns
        if column.required and column.name not in table.columns
    ]
    issues += [
        RowIssue("unknown_column", column=name)
        for name in table.columns
        if name and name not in known
    ]
    issues += [
        RowIssue("duplicate_column", column=name)
        for name, count in Counter(table.columns).items()
        if name and count > 1
    ]
    run.issues.extend(issues)
    return not issues


def _drop_duplicates(spec: ImportSpec, rows: list[ParsedRow], run: ImportRun) -> list[ParsedRow]:
    kept: list[ParsedRow] = []
    seen: list[set[tuple[Any, ...]]] = [set() for _ in spec.unique]
    for row in rows:
        duplicate_of = None
        for index, columns in enumerate(spec.unique):
            key = tuple(_hashable(row.values[name]) for name in columns)
            if key in seen[index]:
                duplicate_of = columns[0]
                break
        if duplicate_of is not None:
            run.error(row, "duplicate_in_file", duplicate_of)
            continue
        for index, columns in enumerate(spec.unique):
            seen[index].add(tuple(_hashable(row.values[name]) for name in columns))
        kept.append(row)
    return kept


def _hashable(value: Any) -> Any:
    return tuple(value) if isinstance(value, list) else value


# --- Structure ----------------------------------------------------------------------------------


class FacultiesImport(ImportSpec):
    kind = ImportKind.FACULTIES
    columns = (
        Column("code", parsing.code()),
        Column("name_az", parsing.text(200)),
        Column("name_en", parsing.text(200), required=False, default=""),
    )
    unique = (("code",),)

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        existing = await run.lookup(Faculty, Faculty.code, (row.values["code"] for row in rows))
        for row in rows:
            values = row.values
            fields = {"name_az": values["name_az"], "name_en": values["name_en"]}
            run.upsert(existing.get(values["code"]), Faculty, fields, code=values["code"])


class SpecialtiesImport(ImportSpec):
    kind = ImportKind.SPECIALTIES
    columns = (
        Column("code", parsing.code()),
        Column("faculty_code", parsing.code()),
        Column("name_az", parsing.text(200)),
        Column("name_en", parsing.text(200), required=False, default=""),
    )
    unique = (("code",),)

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        faculties = await run.lookup(
            Faculty, Faculty.code, (r.values["faculty_code"] for r in rows)
        )
        existing = await run.lookup(Specialty, Specialty.code, (r.values["code"] for r in rows))
        for row in rows:
            values = row.values
            faculty = faculties.get(values["faculty_code"])
            if faculty is None:
                run.error(row, "unknown_reference", "faculty_code")
                continue
            fields = {
                "faculty_id": faculty.id,
                "name_az": values["name_az"],
                "name_en": values["name_en"],
            }
            run.upsert(existing.get(values["code"]), Specialty, fields, code=values["code"])


class SubjectsImport(ImportSpec):
    kind = ImportKind.SUBJECTS
    columns = (
        Column("code", parsing.code()),
        Column("faculty_code", parsing.code()),
        Column("name_az", parsing.text(255)),
        Column("name_en", parsing.text(255), required=False, default=""),
        Column("credits", parsing.integer(0, 60)),
    )
    unique = (("code",),)

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        faculties = await run.lookup(
            Faculty, Faculty.code, (r.values["faculty_code"] for r in rows)
        )
        existing = await run.lookup(Subject, Subject.code, (r.values["code"] for r in rows))
        for row in rows:
            values = row.values
            faculty = faculties.get(values["faculty_code"])
            if faculty is None:
                run.error(row, "unknown_reference", "faculty_code")
                continue
            fields = {
                "faculty_id": faculty.id,
                "name_az": values["name_az"],
                "name_en": values["name_en"],
                "credits": values["credits"],
            }
            run.upsert(existing.get(values["code"]), Subject, fields, code=values["code"])


class SemestersImport(ImportSpec):
    kind = ImportKind.SEMESTERS
    columns = (
        Column("year", parsing.integer(2000, 2100)),
        Column("term", parsing.choice(TERMS)),
        Column("starts_on", parsing.calendar_date),
        Column("ends_on", parsing.calendar_date),
    )
    unique = (("year", "term"),)

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        if values["ends_on"] <= values["starts_on"]:
            return [("dates_out_of_order", "ends_on")]
        return []

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        existing = await run.semesters(rows)
        for row in rows:
            values = row.values
            fields = {"starts_on": values["starts_on"], "ends_on": values["ends_on"]}
            run.upsert(
                existing.get((values["year"], values["term"])),
                Semester,
                fields,
                year=values["year"],
                term=values["term"],
            )


class GroupsImport(ImportSpec):
    kind = ImportKind.GROUPS
    columns = (
        Column("code", parsing.code()),
        Column("specialty_code", parsing.code()),
        Column("admission_year", parsing.integer(1990, 2100)),
        Column("language", parsing.choice(LANGUAGES)),
        Column("curator_id", parsing.university_id, required=False),
    )
    unique = (("code",),)

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        specialties = await run.lookup(
            Specialty, Specialty.code, (r.values["specialty_code"] for r in rows)
        )
        curators = await run.lookup(
            User, User.university_id, (r.values["curator_id"] for r in rows)
        )
        existing = await run.lookup(
            AcademicGroup, AcademicGroup.code, (r.values["code"] for r in rows)
        )
        for row in rows:
            values = row.values
            specialty = specialties.get(values["specialty_code"])
            if specialty is None:
                run.error(row, "unknown_reference", "specialty_code")
                continue
            curator_id = None
            if values["curator_id"] is not None:
                curator = curators.get(values["curator_id"])
                if curator is None:
                    run.error(row, "unknown_reference", "curator_id")
                    continue
                if curator.person_type is not PersonType.TEACHER:
                    run.error(row, "not_a_teacher", "curator_id")
                    continue
                curator_id = curator.id
            fields = {
                "specialty_id": specialty.id,
                "admission_year": values["admission_year"],
                "language": values["language"],
                "curator_id": curator_id,
            }
            run.upsert(existing.get(values["code"]), AcademicGroup, fields, code=values["code"])


# --- People ---------------------------------------------------------------------------------------


class _PeopleImport(ImportSpec):
    person_type: ClassVar[PersonType]
    unique = (("university_id",), ("email",))

    async def resolve(self, run: ImportRun, rows: list[ParsedRow]) -> dict[int, dict[str, Any]]:
        """Kind-specific fields per row number; rows with problems are left out after reporting them."""
        return {row.number: {} for row in rows}

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        extras = await self.resolve(run, rows)
        by_id = await run.lookup(
            User, User.university_id, (r.values["university_id"] for r in rows)
        )
        by_email = await run.lookup(User, User.email, (r.values["email"] for r in rows))
        for row in rows:
            if row.number not in extras:
                continue
            values = row.values
            user = by_id.get(values["university_id"])
            owner = by_email.get(values["email"])
            if user is not None and user.person_type is not self.person_type:
                run.error(row, "person_type_mismatch", "university_id")
                continue
            if user is None and owner is not None:
                if owner.university_id is not None:
                    # Same e-mail, different university ID: never merged (§13.1).
                    run.error(row, "email_conflict", "email")
                    continue
                # Someone who signed in before the registry import: the account gets their record.
                user = owner
            elif owner is not None and user is not None and owner.id != user.id:
                run.error(row, "email_conflict", "email")
                continue

            fields: dict[str, Any] = {
                "university_id": values["university_id"],
                "person_type": self.person_type,
                "given_name": values["given_name"],
                "family_name": values["family_name"],
                "display_name": f"{values['given_name']} {values['family_name']}",
                "status": values["status"],
                **extras[row.number],
            }
            # After the first sign-in the e-mail belongs to the identity provider (D-029).
            if user is None or user.idp_subject is None:
                fields["email"] = values["email"]
            current_email = fields.get("email", user.email if user is not None else None)
            fields["search_key"] = search_key(
                fields["given_name"], fields["family_name"], current_email, fields["university_id"]
            )
            run.upsert(user, User, fields)


_PERSON_COLUMNS = (
    Column("university_id", parsing.university_id),
    Column("family_name", parsing.person_name),
    Column("given_name", parsing.person_name),
    Column("email", parsing.email),
)
_STATUS_COLUMN = Column(
    "status", parsing.choice(PERSON_STATUSES), required=False, default=UserStatus.ACTIVE
)


class TeachersImport(_PeopleImport):
    kind = ImportKind.TEACHERS
    person_type = PersonType.TEACHER
    columns = (*_PERSON_COLUMNS, _STATUS_COLUMN)


class StudentsImport(_PeopleImport):
    kind = ImportKind.STUDENTS
    person_type = PersonType.STUDENT
    columns = (*_PERSON_COLUMNS, Column("group_code", parsing.code()), _STATUS_COLUMN)

    async def resolve(self, run: ImportRun, rows: list[ParsedRow]) -> dict[int, dict[str, Any]]:
        groups = await run.lookup(
            AcademicGroup, AcademicGroup.code, (r.values["group_code"] for r in rows)
        )
        resolved: dict[int, dict[str, Any]] = {}
        for row in rows:
            group = groups.get(row.values["group_code"])
            if group is None:
                run.error(row, "unknown_reference", "group_code")
            else:
                resolved[row.number] = {"academic_group_id": group.id}
        return resolved


# --- Teaching -------------------------------------------------------------------------------------


class OfferingsImport(ImportSpec):
    kind = ImportKind.OFFERINGS
    columns = (
        Column("subject_code", parsing.code()),
        Column("year", parsing.integer(2000, 2100)),
        Column("term", parsing.choice(TERMS)),
        Column("code", parsing.code(64), required=False),
        Column("group_codes", parsing.code_list()),
        Column("teacher_ids", parsing.university_id_list, required=False, default=[]),
    )
    unique = (("subject_code", "year", "term", "code"),)

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        # A joint lecture of 765a1 and 765a2 is "765a1+765a2" unless the file names it.
        if values["code"] is None:
            values["code"] = "+".join(sorted(values["group_codes"]))
        return []

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        subjects = await run.lookup(Subject, Subject.code, (r.values["subject_code"] for r in rows))
        semesters = await run.semesters(rows)
        groups = await run.lookup(
            AcademicGroup, AcademicGroup.code, (c for r in rows for c in r.values["group_codes"])
        )
        teachers = await run.lookup(
            User, User.university_id, (t for r in rows for t in r.values["teacher_ids"])
        )

        resolved: list[tuple[ParsedRow, Subject, Semester, set[uuid.UUID], set[uuid.UUID]]] = []
        for row in rows:
            values = row.values
            subject = subjects.get(values["subject_code"])
            semester = semesters.get((values["year"], values["term"]))
            group_ids = {groups[c].id for c in values["group_codes"] if c in groups}
            teacher_users = [teachers.get(t) for t in values["teacher_ids"]]
            if subject is None:
                run.error(row, "unknown_reference", "subject_code")
            elif semester is None:
                run.error(row, "unknown_reference", "year")
            elif len(group_ids) != len(values["group_codes"]):
                run.error(row, "unknown_reference", "group_codes")
            elif any(teacher is None for teacher in teacher_users):
                run.error(row, "unknown_reference", "teacher_ids")
            elif any(
                t is not None and t.person_type is not PersonType.TEACHER for t in teacher_users
            ):
                run.error(row, "not_a_teacher", "teacher_ids")
            else:
                teacher_ids = {teacher.id for teacher in teacher_users if teacher is not None}
                resolved.append((row, subject, semester, group_ids, teacher_ids))

        keys = [
            (subject.id, semester.id, row.values["code"]) for row, subject, semester, *_ in resolved
        ]
        existing: dict[tuple[uuid.UUID, uuid.UUID, str], CourseOffering] = {}
        if keys:
            offerings = await run.session.scalars(
                select(CourseOffering).where(
                    tuple_(
                        CourseOffering.subject_id, CourseOffering.semester_id, CourseOffering.code
                    ).in_(keys)
                )
            )
            existing = {(o.subject_id, o.semester_id, o.code): o for o in offerings}
        linked_groups = await _links(run, CourseOfferingGroup.academic_group_id, existing.values())
        linked_teachers = await _links(run, CourseOfferingTeacher.teacher_id, existing.values())

        for row, subject, semester, group_ids, teacher_ids in resolved:
            offering = existing.get((subject.id, semester.id, row.values["code"]))
            if offering is None:
                offering = run.create(
                    CourseOffering(
                        id=uuid7(),
                        subject_id=subject.id,
                        semester_id=semester.id,
                        code=row.values["code"],
                    )
                )
                current_groups: set[uuid.UUID] = set()
                current_teachers: set[uuid.UUID] = set()
                if run.write:
                    # The link tables have no ORM relationship, so the offering row must exist first.
                    await run.session.flush()
            else:
                current_groups = linked_groups[offering.id]
                current_teachers = linked_teachers[offering.id]
                changed = current_groups != group_ids or current_teachers != teacher_ids
                run.counts["updated" if changed else "unchanged"] += 1
            if run.write:
                await _replace_links(
                    run,
                    CourseOfferingGroup,
                    "academic_group_id",
                    offering.id,
                    current_groups,
                    group_ids,
                )
                # A replaced teacher is unlinked; channel history stays with the chat module (§13.1).
                await _replace_links(
                    run,
                    CourseOfferingTeacher,
                    "teacher_id",
                    offering.id,
                    current_teachers,
                    teacher_ids,
                )


async def _links(
    run: ImportRun, column: InstrumentedAttribute[uuid.UUID], offerings: Iterable[CourseOffering]
) -> defaultdict[uuid.UUID, set[uuid.UUID]]:
    ids = [offering.id for offering in offerings]
    result: defaultdict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    if ids:
        model = column.class_
        rows = await run.session.execute(
            select(model.course_offering_id, column).where(model.course_offering_id.in_(ids))
        )
        for offering_id, linked_id in rows:
            result[offering_id].add(linked_id)
    return result


async def _replace_links(
    run: ImportRun,
    model: type[CourseOfferingGroup] | type[CourseOfferingTeacher],
    attribute: str,
    offering_id: uuid.UUID,
    current: set[uuid.UUID],
    desired: set[uuid.UUID],
) -> None:
    if removed := current - desired:
        await run.session.execute(
            delete(model).where(
                model.course_offering_id == offering_id, getattr(model, attribute).in_(removed)
            )
        )
    for added in desired - current:
        run.session.add(model(course_offering_id=offering_id, **{attribute: added}))


class EnrollmentsImport(ImportSpec):
    kind = ImportKind.ENROLLMENTS
    columns = (
        Column("student_id", parsing.university_id),
        Column("subject_code", parsing.code()),
        Column("year", parsing.integer(2000, 2100)),
        Column("term", parsing.choice(TERMS)),
        Column("offering_code", parsing.code(64), required=False),
        Column(
            "status",
            parsing.choice(ENROLLMENT_STATUSES),
            required=False,
            default=EnrollmentStatus.ACTIVE,
        ),
        Column("passed", parsing.boolean, required=False),
        Column("grade", parsing.integer(0, 100), required=False),
    )
    unique = (("student_id", "subject_code", "year", "term", "offering_code"),)

    def prepare(self, values: dict[str, Any]) -> list[tuple[str, str]]:
        completed = values["status"] is EnrollmentStatus.COMPLETED
        if completed and values["passed"] is None:
            return [("result_required", "passed")]
        if not completed and values["passed"] is not None:
            return [("result_not_allowed", "passed")]
        if not completed and values["grade"] is not None:
            return [("result_not_allowed", "grade")]
        return []

    async def apply(self, run: ImportRun, rows: list[ParsedRow]) -> None:
        students = await run.lookup(
            User, User.university_id, (r.values["student_id"] for r in rows)
        )
        subjects = await run.lookup(Subject, Subject.code, (r.values["subject_code"] for r in rows))
        semesters = await run.semesters(rows)

        pairs = {
            (
                subjects[r.values["subject_code"]].id,
                semesters[(r.values["year"], r.values["term"])].id,
            )
            for r in rows
            if r.values["subject_code"] in subjects
            and (r.values["year"], r.values["term"]) in semesters
        }
        offerings: defaultdict[tuple[uuid.UUID, uuid.UUID], list[CourseOffering]] = defaultdict(
            list
        )
        if pairs:
            for offering in await run.session.scalars(
                select(CourseOffering).where(
                    tuple_(CourseOffering.subject_id, CourseOffering.semester_id).in_(pairs)
                )
            ):
                offerings[(offering.subject_id, offering.semester_id)].append(offering)
        offering_groups = await _links(
            run,
            CourseOfferingGroup.academic_group_id,
            (offering for candidates in offerings.values() for offering in candidates),
        )

        resolved: list[tuple[ParsedRow, User, CourseOffering]] = []
        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for row in rows:
            values = row.values
            student = students.get(values["student_id"])
            subject = subjects.get(values["subject_code"])
            semester = semesters.get((values["year"], values["term"]))
            if student is None:
                run.error(row, "unknown_reference", "student_id")
                continue
            if student.person_type is not PersonType.STUDENT:
                run.error(row, "not_a_student", "student_id")
                continue
            if subject is None:
                run.error(row, "unknown_reference", "subject_code")
                continue
            if semester is None:
                run.error(row, "unknown_reference", "year")
                continue
            candidates = offerings[(subject.id, semester.id)]
            if values["offering_code"] is not None:
                matches = [o for o in candidates if o.code == values["offering_code"]]
            else:
                # Without a code the offering is the one taught to the student's own group.
                matches = [
                    o for o in candidates if student.academic_group_id in offering_groups[o.id]
                ]
            if not matches:
                run.error(row, "unknown_reference", "offering_code")
                continue
            if len(matches) > 1:
                run.error(row, "ambiguous_offering", "offering_code")
                continue
            if (student.id, matches[0].id) in seen:
                run.error(row, "duplicate_in_file", "student_id")
                continue
            seen.add((student.id, matches[0].id))
            resolved.append((row, student, matches[0]))

        existing: dict[tuple[uuid.UUID, uuid.UUID], Enrollment] = {}
        if seen:
            enrollments = await run.session.scalars(
                select(Enrollment).where(
                    tuple_(Enrollment.user_id, Enrollment.course_offering_id).in_(seen)
                )
            )
            existing = {(e.user_id, e.course_offering_id): e for e in enrollments}
        for row, student, offering in resolved:
            fields = {
                "status": row.values["status"],
                "passed": row.values["passed"],
                "grade": row.values["grade"],
            }
            run.upsert(
                existing.get((student.id, offering.id)),
                Enrollment,
                fields,
                user_id=student.id,
                course_offering_id=offering.id,
            )
