from pydantic import BaseModel

from app.modules.academics.models import SemesterTerm


class FinishedCourseOut(BaseModel):
    """One finished course of the signed-in student; the score is the final 0-100 result."""

    enrollment_id: str
    subject_id: str
    subject_code: str
    subject_name: str
    credits: int
    semester_year: int
    semester_term: SemesterTerm
    score: int
    passed: bool


class FinishedCourseListOut(BaseModel):
    items: list[FinishedCourseOut]
