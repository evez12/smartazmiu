import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.quizzes.models import (
    AttemptStatus,
    QuestionType,
    Quiz,
    QuizAttempt,
    QuizQuestion,
)
from app.modules.quizzes.schemas import AnswersIn, QuestionCreateIn, QuizCreateIn


def _same_answer(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list) and isinstance(actual, list):
        return sorted(expected, key=str) == sorted(actual, key=str)
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().casefold() == actual.strip().casefold()
    return bool(expected == actual)


def auto_grade(questions: list[QuizQuestion], answers: dict[str, Any]) -> tuple[int, int]:
    score = 0
    maximum = sum(question.points for question in questions)
    for question in questions:
        if question.type == QuestionType.SHORT_ANSWER:
            continue
        answer = answers.get(str(question.id))
        if _same_answer(question.correct_answer, answer):
            score += question.points
    return score, maximum


def attempt_expiry(
    started_at: datetime, time_limit_seconds: int | None, deadline: datetime | None
) -> datetime | None:
    limits = []
    if time_limit_seconds is not None:
        limits.append(started_at + timedelta(seconds=time_limit_seconds))
    if deadline is not None:
        limits.append(deadline)
    return min(limits) if limits else None


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: QuizCreateIn, teacher_id: uuid.UUID) -> Quiz:
        quiz = Quiz(**data.model_dump(), created_by=teacher_id)
        self.session.add(quiz)
        await self.session.flush()
        return quiz

    async def add_question(
        self, quiz_id: uuid.UUID, position: int, data: QuestionCreateIn
    ) -> QuizQuestion:
        if await self.session.get(Quiz, quiz_id) is None:
            raise AppError("quizzes.not_found", 404)
        question = QuizQuestion(quiz_id=quiz_id, position=position, **data.model_dump())
        self.session.add(question)
        await self.session.flush()
        return question

    async def start_attempt(self, quiz_id: uuid.UUID, student_id: uuid.UUID) -> QuizAttempt:
        quiz = await self.session.get(Quiz, quiz_id)
        if quiz is None:
            raise AppError("quizzes.not_found", 404)
        now = utc_now()
        if quiz.available_from and now < quiz.available_from:
            raise AppError("quizzes.not_available", 409)
        if quiz.deadline and now > quiz.deadline:
            raise AppError("quizzes.expired", 409)
        count = await self.session.scalar(
            select(QuizAttempt.attempt_number)
            .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.student_id == student_id)
            .order_by(QuizAttempt.attempt_number.desc())
            .limit(1)
        )
        attempt_number = (count or 0) + 1
        if attempt_number > quiz.max_attempts:
            raise AppError("quizzes.attempt_limit_reached", 409)
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            student_id=student_id,
            attempt_number=attempt_number,
            started_at=now,
            expires_at=attempt_expiry(now, quiz.time_limit_seconds, quiz.deadline),
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def save_answers(
        self, attempt_id: uuid.UUID, student_id: uuid.UUID, data: AnswersIn
    ) -> QuizAttempt:
        attempt = await self._owned_attempt(attempt_id, student_id)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise AppError("quizzes.attempt_closed", 409)
        attempt.answers = {str(key): value for key, value in data.answers.items()}
        if attempt.expires_at and utc_now() >= attempt.expires_at:
            await self._finalize(attempt, auto=True)
        await self.session.flush()
        return attempt

    async def submit(
        self, attempt_id: uuid.UUID, student_id: uuid.UUID, data: AnswersIn
    ) -> QuizAttempt:
        attempt = await self._owned_attempt(attempt_id, student_id)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise AppError("quizzes.attempt_closed", 409)
        attempt.answers = {str(key): value for key, value in data.answers.items()}
        await self._finalize(
            attempt, auto=bool(attempt.expires_at and utc_now() >= attempt.expires_at)
        )
        await self.session.flush()
        return attempt

    async def _owned_attempt(self, attempt_id: uuid.UUID, student_id: uuid.UUID) -> QuizAttempt:
        attempt = await self.session.scalar(
            select(QuizAttempt).where(
                QuizAttempt.id == attempt_id, QuizAttempt.student_id == student_id
            )
        )
        if attempt is None:
            raise AppError("quizzes.attempt_not_found", 404)
        return attempt

    async def _finalize(self, attempt: QuizAttempt, *, auto: bool) -> None:
        questions = list(
            await self.session.scalars(
                select(QuizQuestion).where(QuizQuestion.quiz_id == attempt.quiz_id)
            )
        )
        score, maximum = auto_grade(questions, attempt.answers)
        attempt.status = AttemptStatus.AUTO_SUBMITTED if auto else AttemptStatus.SUBMITTED
        attempt.submitted_at = utc_now()
        attempt.score = score
        attempt.max_score = maximum
