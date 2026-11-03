"""The seam to the university's personal cabinet (D-010, D-126).

The cabinet is read-only for us: a provider answers questions about one person, identified by the university ID,
and never receives anything to store. Results carry the ID they answer for, so a source that answers about
someone else is caught instead of mirrored (§13.1).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from app.core.config import Settings
from app.modules.academics.models import SemesterTerm


class CabinetError(Exception):
    """Base of what a provider may raise; anything else is a bug and is not swallowed."""


class CabinetUnavailableError(CabinetError):
    """The source could not be reached or answered with a failure. The whole sync run is abandoned (§13.5)."""


class CabinetNotFoundError(CabinetError):
    """The source knows no person with this university ID."""


class CabinetMismatchError(CabinetError):
    """The source answered about a different university ID than the one asked for."""


class AppealStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    UPHELD = "upheld"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CabinetGrade:
    subject_code: str
    subject_name: str
    credits: int
    semester_year: int
    semester_term: SemesterTerm
    score: int
    passed: bool


@dataclass(frozen=True, slots=True)
class CabinetGrades:
    university_id: str
    items: tuple[CabinetGrade, ...]


@dataclass(frozen=True, slots=True)
class CabinetSemesterSummary:
    semester_year: int
    semester_term: SemesterTerm
    credits_attempted: int
    credits_earned: int
    average: Decimal | None


@dataclass(frozen=True, slots=True)
class CabinetTranscript:
    university_id: str
    specialty_name: str
    credits_earned: int
    cumulative_average: Decimal | None
    semesters: tuple[CabinetSemesterSummary, ...]


@dataclass(frozen=True, slots=True)
class CabinetAppeal:
    reference: str
    subject_code: str
    semester_year: int
    semester_term: SemesterTerm
    status: AppealStatus
    submitted_on: date
    decided_on: date | None


@dataclass(frozen=True, slots=True)
class CabinetAppeals:
    university_id: str
    items: tuple[CabinetAppeal, ...]


class CabinetProvider(Protocol):
    """Every implementation passes ``app.modules.cabinet.tests.contract.CabinetProviderContract``."""

    async def grades(self, university_id: str) -> CabinetGrades: ...

    async def transcript(self, university_id: str) -> CabinetTranscript: ...

    async def appeals(self, university_id: str) -> CabinetAppeals: ...


class CabinetNotAvailableYetError(RuntimeError):
    """The setting names the university's own cabinet, whose API has not been described to us yet (D-010)."""


def build_provider(settings: Settings) -> CabinetProvider:
    if settings.cabinet_provider == "fake":
        from app.modules.cabinet.fake import FakeCabinetProvider

        return FakeCabinetProvider()
    raise CabinetNotAvailableYetError(
        "CABINET_PROVIDER=azmiu has no implementation yet: the cabinet's API is not known (D-010)"
    )
