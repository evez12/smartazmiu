"""A stand-in cabinet with made-up but plausible Azerbaijani data (D-010), used until the real API is described.

Every eight-digit student ID has a record, derived from the ID alone, so seeded and throwaway accounts alike get
a stable transcript without any fixture file. Tests steer it through the ``set_*`` / ``drop`` / ``break_*`` methods.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.modules.academics.models import SemesterTerm
from app.modules.cabinet.provider import (
    AppealStatus,
    CabinetAppeal,
    CabinetAppeals,
    CabinetGrade,
    CabinetGrades,
    CabinetNotFoundError,
    CabinetSemesterSummary,
    CabinetTranscript,
    CabinetUnavailableError,
)

PASS_MARK = 51
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class _Course:
    code: str
    name: str
    credits: int


# The courses of the sample data's finished terms (infra/seed/academics/subjects.csv).
CURRICULUM: dict[tuple[int, SemesterTerm], tuple[_Course, ...]] = {
    (2025, SemesterTerm.FALL): (
        _Course("SOS-1101", "Azərbaycan tarixi", 5),
        _Course("XDL-1101", "Xarici dildə işgüzar və akademik kommunikasiya-1", 4),
        _Course("RIY-1101", "Xətti cəbr və riyazi analiz", 8),
        _Course("IKT-1101", "İKT-baza kompyuter bilikləri", 8),
        _Course("KAR-1101", "Karyera planlaşması-1", 5),
    ),
    (2026, SemesterTerm.SPRING): (
        _Course("SOS-1202", "Azərbaycan dilində işgüzar və akademik kommunikasiya", 4),
        _Course("XDL-1202", "Xarici dildə işgüzar və akademik kommunikasiya-2", 3),
        _Course("IQT-1201", "İqtisadiyyata giriş", 6),
        _Course("RIY-1202", "Ehtimal nəzəriyyəsi və riyazi statistika", 8),
        _Course("KAR-1202", "Karyera planlaşması-2", 9),
    ),
}

SPECIALTY_NAMES = ("İqtisadiyyat", "Menecment", "Maliyyə", "Mühasibat uçotu")


def _is_student_id(university_id: str) -> bool:
    return len(university_id) == 8 and university_id.isascii() and university_id.isdigit()


def _rng(seed: str) -> random.Random:
    # Stable made-up data, not anything secret.
    return random.Random(seed)  # noqa: S311


def weighted_average(rows: list[tuple[int, int]]) -> Decimal | None:
    """Credit-weighted mean of ``(credits, score)``, half-up to two places."""
    credits = sum(credit for credit, _ in rows)
    if credits == 0:
        return None
    mean = Decimal(sum(credit * score for credit, score in rows)) / Decimal(credits)
    return mean.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class FakeCabinetProvider:
    def __init__(self) -> None:
        self._unavailable = False
        self._missing: set[str] = set()
        self._impostors: set[str] = set()
        self._scores: dict[tuple[str, str], int] = {}

    # --- steering, for tests and demos ----------------------------------------------------------
    def break_connection(self, broken: bool = True) -> None:
        self._unavailable = broken

    def drop(self, university_id: str) -> None:
        """The cabinet no longer knows this person."""
        self._missing.add(university_id)

    def answer_for_someone_else(self, university_id: str) -> None:
        self._impostors.add(university_id)

    def set_score(self, university_id: str, subject_code: str, score: int) -> None:
        self._scores[(university_id, subject_code)] = score

    # --- CabinetProvider ------------------------------------------------------------------------
    async def grades(self, university_id: str) -> CabinetGrades:
        self._check(university_id)
        return CabinetGrades(self._answered_id(university_id), tuple(self._grades(university_id)))

    async def transcript(self, university_id: str) -> CabinetTranscript:
        self._check(university_id)
        grades = self._grades(university_id)
        summaries = []
        for (year, term), courses in CURRICULUM.items():
            rows = [g for g in grades if (g.semester_year, g.semester_term) == (year, term)]
            summaries.append(
                CabinetSemesterSummary(
                    semester_year=year,
                    semester_term=term,
                    credits_attempted=sum(course.credits for course in courses),
                    credits_earned=sum(g.credits for g in rows if g.passed),
                    average=weighted_average([(g.credits, g.score) for g in rows]),
                )
            )
        rng = _rng(university_id)
        return CabinetTranscript(
            university_id=self._answered_id(university_id),
            specialty_name=rng.choice(SPECIALTY_NAMES),
            credits_earned=sum(s.credits_earned for s in summaries),
            cumulative_average=weighted_average([(g.credits, g.score) for g in grades]),
            semesters=tuple(summaries),
        )

    async def appeals(self, university_id: str) -> CabinetAppeals:
        self._check(university_id)
        grades = self._grades(university_id)
        rng = _rng(f"appeal:{university_id}")
        items: list[CabinetAppeal] = []
        # A failed course is the likeliest reason to ask for a review of the exam paper.
        for grade in grades:
            if grade.passed and rng.random() > 0.04:
                continue
            if not grade.passed and rng.random() > 0.6:
                continue
            submitted = date(grade.semester_year + 1, 2, 3) + timedelta(days=rng.randint(0, 6))
            status = rng.choice(list(AppealStatus))
            items.append(
                CabinetAppeal(
                    reference=f"MQ-{grade.semester_year}-{university_id[-4:]}-{len(items) + 1}",
                    subject_code=grade.subject_code,
                    semester_year=grade.semester_year,
                    semester_term=grade.semester_term,
                    status=status,
                    submitted_on=submitted,
                    decided_on=None
                    if status in (AppealStatus.SUBMITTED, AppealStatus.UNDER_REVIEW)
                    else submitted + timedelta(days=rng.randint(3, 10)),
                )
            )
        return CabinetAppeals(self._answered_id(university_id), tuple(items))

    # --- internals ------------------------------------------------------------------------------
    def _check(self, university_id: str) -> None:
        if self._unavailable:
            raise CabinetUnavailableError("the fake cabinet is switched off")
        if university_id in self._missing or not _is_student_id(university_id):
            raise CabinetNotFoundError(university_id)

    def _answered_id(self, university_id: str) -> str:
        if university_id in self._impostors:
            return str(int(university_id) + 1).zfill(8)
        return university_id

    def _grades(self, university_id: str) -> list[CabinetGrade]:
        rng = _rng(university_id)
        grades = []
        for (year, term), courses in CURRICULUM.items():
            for course in courses:
                # Mostly 60-95; about one result in twenty is a fail that needs a retake.
                score = rng.randint(30, 50) if rng.random() < 0.05 else rng.randint(60, 98)
                score = self._scores.get((university_id, course.code), score)
                grades.append(
                    CabinetGrade(
                        subject_code=course.code,
                        subject_name=course.name,
                        credits=course.credits,
                        semester_year=year,
                        semester_term=term,
                        score=score,
                        passed=score >= PASS_MARK,
                    )
                )
        return grades
