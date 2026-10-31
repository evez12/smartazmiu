"""Quizzes: offering-scoped building, timed attempts with server-authoritative expiry, auto-grading of closed
questions, teacher scoring of open ones, and statistics (§6.1, §13.2, D-092)."""

import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.academics.coursework import (
    CourseRole,
    attending,
    course_role,
    offering_labels,
    teaching,
)
from app.modules.academics.models import AcademicGroup, CourseOfferingTeacher
from app.modules.assignments.schemas import StudentOut
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.quizzes.models import (
    AttemptStatus,
    QuestionType,
    Quiz,
    QuizAttempt,
    QuizQuestion,
)
from app.modules.quizzes.schemas import (
    AnswersIn,
    AttemptListOut,
    AttemptOut,
    AttemptReviewOut,
    AttemptRowOut,
    AttemptSummaryOut,
    DistributionBucket,
    ManagerQuestionOut,
    ManualScoresIn,
    QuestionCreateIn,
    QuestionOut,
    QuestionStats,
    QuizCreateIn,
    QuizDetailOut,
    QuizStatsOut,
    QuizSummaryOut,
)
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

MANAGE = "quizzes.manage"
MAX_QUESTIONS = 100
MAX_SHORT_ANSWER = 2_000
EXPIRY_GRACE = timedelta(seconds=3)
"""Answers that reach the server this long after the time limit still count: the request left in time."""
LIST_LIMIT = 200


def _same_answer(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list) and isinstance(actual, list):
        return sorted(expected, key=str) == sorted(actual, key=str)
    return bool(expected == actual)


def auto_grade(questions: list[QuizQuestion], answers: dict[str, Any]) -> tuple[int, int]:
    """Points for the closed questions, and the maximum of the whole quiz. Open questions are scored by a
    teacher (§6, "auto-grading (non-open)")."""
    score = 0
    maximum = sum(question.points for question in questions)
    for question in questions:
        if question.type is QuestionType.SHORT_ANSWER:
            continue
        if _same_answer(question.correct_answer, answers.get(str(question.id))):
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


def clean_answers(questions: list[QuizQuestion], raw: dict[str, Any]) -> dict[str, Any]:
    """Keeps only answers that fit their question; anything else is a client error, not a lower score."""
    by_id = {str(question.id): question for question in questions}
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        question = by_id.get(key)
        if question is None:
            raise AppError("quizzes.invalid_answers", 422)
        ids = {option["id"] for option in question.options}
        if value is None:
            continue
        if question.type is QuestionType.MCQ:
            ok = isinstance(value, str) and value in ids
        elif question.type is QuestionType.MULTI_SELECT:
            ok = (
                isinstance(value, list)
                and len(set(value)) == len(value)
                and all(isinstance(item, str) and item in ids for item in value)
            )
        else:
            ok = isinstance(value, str) and len(value) <= MAX_SHORT_ANSWER
        if not ok:
            raise AppError("quizzes.invalid_answers", 422)
        cleaned[key] = value
    return cleaned


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- who sees what -----------------------------------------------------------------------

    def _managed(self, user: CurrentUser) -> ColumnElement[bool]:
        if user.has_permission(MANAGE):
            return true()
        return Quiz.course_offering_id.in_(teaching(user))

    def _visible(self, user: CurrentUser) -> ColumnElement[bool]:
        """Managers see every quiz of their offerings; students see published ones that have opened."""
        opened = and_(
            Quiz.course_offering_id.in_(attending(user)),
            Quiz.published_at.is_not(None),
            or_(Quiz.available_from.is_(None), Quiz.available_from <= utc_now()),
        )
        return or_(self._managed(user), opened)

    async def _quiz(self, user: CurrentUser, quiz_id: uuid.UUID) -> tuple[Quiz, CourseRole]:
        quiz = await self.session.scalar(
            select(Quiz).where(Quiz.id == quiz_id, self._visible(user))
        )
        if quiz is None:
            raise AppError("quizzes.not_found", 404)
        role = await course_role(self.session, user, quiz.course_offering_id, MANAGE)
        assert role is not None
        return quiz, role

    async def _managed_quiz(self, user: CurrentUser, quiz_id: uuid.UUID) -> Quiz:
        quiz, role = await self._quiz(user, quiz_id)
        if role != "manager":
            raise AppError("auth.forbidden", 403)
        return quiz

    async def _questions(self, quiz_id: uuid.UUID) -> list[QuizQuestion]:
        return list(
            await self.session.scalars(
                select(QuizQuestion)
                .where(QuizQuestion.quiz_id == quiz_id)
                .order_by(QuizQuestion.position)
            )
        )

    # --- reading -----------------------------------------------------------------------------

    async def quizzes(
        self, user: CurrentUser, offering_id: uuid.UUID | None
    ) -> list[QuizSummaryOut]:
        query = select(Quiz).where(self._visible(user))
        if offering_id is not None:
            query = query.where(Quiz.course_offering_id == offering_id)
        quizzes = list(
            await self.session.scalars(
                query.order_by(Quiz.created_at.desc(), Quiz.id.desc()).limit(LIST_LIMIT)
            )
        )
        return await self._summaries(user, quizzes)

    async def _summaries(self, user: CurrentUser, quizzes: list[Quiz]) -> list[QuizSummaryOut]:
        if not quizzes:
            return []
        ids = [quiz.id for quiz in quizzes]
        offerings = await offering_labels(
            self.session, {quiz.course_offering_id for quiz in quizzes}
        )
        managed = (
            {quiz.course_offering_id for quiz in quizzes}
            if user.has_permission(MANAGE)
            else set(
                await self.session.scalars(
                    teaching(user).where(
                        CourseOfferingTeacher.course_offering_id.in_(
                            {quiz.course_offering_id for quiz in quizzes}
                        )
                    )
                )
            )
        )
        counts = {
            quiz_id: total
            for quiz_id, total in await self.session.execute(
                select(QuizQuestion.quiz_id, func.count())
                .where(QuizQuestion.quiz_id.in_(ids))
                .group_by(QuizQuestion.quiz_id)
            )
        }
        mine: dict[uuid.UUID, list[QuizAttempt]] = {quiz_id: [] for quiz_id in ids}
        for attempt in await self.session.scalars(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id.in_(ids), QuizAttempt.student_id == user.id
            )
        ):
            mine[attempt.quiz_id].append(attempt)
        attempted = {
            quiz_id: total
            for quiz_id, total in await self.session.execute(
                select(QuizAttempt.quiz_id, func.count(func.distinct(QuizAttempt.student_id)))
                .where(QuizAttempt.quiz_id.in_(ids))
                .group_by(QuizAttempt.quiz_id)
            )
        }
        result = []
        for quiz in quizzes:
            manages = quiz.course_offering_id in managed
            percents = [
                round(100 * a.score / a.max_score)
                for a in mine[quiz.id]
                if a.score is not None and a.max_score
            ]
            result.append(
                QuizSummaryOut(
                    id=str(quiz.id),
                    offering=offerings[quiz.course_offering_id],
                    title=quiz.title,
                    available_from=quiz.available_from,
                    deadline=quiz.deadline,
                    time_limit_seconds=quiz.time_limit_seconds,
                    max_attempts=quiz.max_attempts,
                    published=quiz.published_at is not None,
                    question_count=counts.get(quiz.id, 0),
                    can_manage=manages,
                    attempts_used=None if manages else len(mine[quiz.id]),
                    best_percent=None if manages or not percents else max(percents),
                    students_attempted=attempted.get(quiz.id, 0) if manages else None,
                )
            )
        return result

    def _attempt_summary(
        self, attempt: QuizAttempt, questions: list[QuizQuestion]
    ) -> AttemptSummaryOut:
        return AttemptSummaryOut(
            id=str(attempt.id),
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            score=attempt.score,
            max_score=attempt.max_score,
            pending_review=self._pending_review(attempt, questions),
        )

    @staticmethod
    def _pending_review(attempt: QuizAttempt, questions: list[QuizQuestion]) -> bool:
        if attempt.status is AttemptStatus.IN_PROGRESS:
            return False
        return any(
            question.type is QuestionType.SHORT_ANSWER
            and str(question.id) not in attempt.manual_scores
            for question in questions
        )

    @staticmethod
    def _student_question(question: QuizQuestion) -> QuestionOut:
        return QuestionOut(
            id=str(question.id),
            position=question.position,
            type=question.type,
            prompt=question.prompt,
            points=question.points,
            options=question.options,
            is_required=question.is_required,
        )

    @staticmethod
    def _manager_question(question: QuizQuestion) -> ManagerQuestionOut:
        return ManagerQuestionOut(
            **QuizService._student_question(question).model_dump(),
            correct_answer=question.correct_answer,
        )

    async def detail(self, user: CurrentUser, quiz_id: uuid.UUID) -> QuizDetailOut:
        quiz, role = await self._quiz(user, quiz_id)
        questions = await self._questions(quiz.id)
        summary = (await self._summaries(user, [quiz]))[0]
        attempts: list[AttemptSummaryOut] = []
        blocked: str | None = None
        if role != "manager":
            await self._finalize_expired(quiz.id, user.id)
            rows = await self.session.scalars(
                select(QuizAttempt)
                .where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id)
                .order_by(QuizAttempt.attempt_number)
            )
            attempts = [self._attempt_summary(a, questions) for a in rows]
            blocked = self._start_blocker(quiz, role, attempts)
        return QuizDetailOut(
            **summary.model_dump(),
            instructions=quiz.instructions,
            can_start=role == "student" and blocked is None,
            start_blocked=None if role != "student" else blocked,
            my_attempts=attempts,
            questions=[self._manager_question(q) for q in questions] if role == "manager" else None,
        )

    def _start_blocker(
        self, quiz: Quiz, role: CourseRole, attempts: list[AttemptSummaryOut]
    ) -> str | None:
        now = utc_now()
        if quiz.available_from and now < quiz.available_from:
            return "not_available"
        if quiz.deadline and now > quiz.deadline:
            return "closed"
        finished = [a for a in attempts if a.status is not AttemptStatus.IN_PROGRESS]
        if len(finished) >= quiz.max_attempts and not any(
            a.status is AttemptStatus.IN_PROGRESS for a in attempts
        ):
            return "attempt_limit_reached"
        return None

    # --- building ----------------------------------------------------------------------------

    async def create(self, user: CurrentUser, data: QuizCreateIn) -> QuizDetailOut:
        role = await course_role(self.session, user, data.course_offering_id, MANAGE)
        if role != "manager":
            raise AppError("quizzes.offering_not_found", 404)
        quiz = Quiz(**data.model_dump(), created_by=user.id)
        self.session.add(quiz)
        await self.session.flush()
        record_audit(
            self.session,
            AuditAction.QUIZ_CREATED,
            actor_id=user.id,
            target_type="quiz",
            target_id=quiz.id,
            details={"course_offering_id": str(data.course_offering_id)},
        )
        await self.session.commit()
        return await self.detail(user, quiz.id)

    async def _unpublished(self, user: CurrentUser, quiz_id: uuid.UUID) -> Quiz:
        quiz = await self._managed_quiz(user, quiz_id)
        locked = await self.session.get(Quiz, quiz.id, with_for_update=True)
        assert locked is not None
        if locked.published_at is not None:
            # Students may already be answering; questions of a published quiz do not change.
            raise AppError("quizzes.already_published", 409)
        return locked

    async def add_question(
        self, user: CurrentUser, quiz_id: uuid.UUID, data: QuestionCreateIn
    ) -> QuizDetailOut:
        quiz = await self._unpublished(user, quiz_id)
        count = await self.session.scalar(
            select(func.count()).select_from(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)
        )
        if (count or 0) >= MAX_QUESTIONS:
            raise AppError("quizzes.too_many_questions", 422)
        position = (
            await self.session.scalar(
                select(func.coalesce(func.max(QuizQuestion.position), 0)).where(
                    QuizQuestion.quiz_id == quiz.id
                )
            )
            or 0
        ) + 1
        self.session.add(
            QuizQuestion(
                quiz_id=quiz.id,
                position=position,
                type=data.type,
                prompt=data.prompt.strip(),
                points=data.points,
                options=[option.model_dump() for option in data.options],
                correct_answer=data.correct_answer,
                is_required=data.is_required,
            )
        )
        await self.session.commit()
        return await self.detail(user, quiz_id)

    async def delete_question(
        self, user: CurrentUser, quiz_id: uuid.UUID, question_id: uuid.UUID
    ) -> QuizDetailOut:
        quiz = await self._unpublished(user, quiz_id)
        question = await self.session.get(QuizQuestion, question_id)
        if question is None or question.quiz_id != quiz.id:
            raise AppError("quizzes.question_not_found", 404)
        await self.session.delete(question)
        await self.session.commit()
        return await self.detail(user, quiz_id)

    async def publish(self, user: CurrentUser, quiz_id: uuid.UUID) -> QuizDetailOut:
        quiz = await self._unpublished(user, quiz_id)
        if not await self._questions(quiz.id):
            raise AppError("quizzes.no_questions", 409)
        quiz.published_at = utc_now()
        record_audit(
            self.session,
            AuditAction.QUIZ_PUBLISHED,
            actor_id=user.id,
            target_type="quiz",
            target_id=quiz.id,
        )
        await self.session.commit()
        return await self.detail(user, quiz_id)

    # --- attempts ----------------------------------------------------------------------------

    async def _finalize_expired(
        self, quiz_id: uuid.UUID | None = None, student_id: uuid.UUID | None = None
    ) -> int:
        """Closes attempts whose time ran out with the answers saved so far (§6.1); idempotent."""
        query = select(QuizAttempt).where(
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
            QuizAttempt.expires_at.is_not(None),
            QuizAttempt.expires_at <= utc_now(),
        )
        if quiz_id is not None:
            query = query.where(QuizAttempt.quiz_id == quiz_id)
        if student_id is not None:
            query = query.where(QuizAttempt.student_id == student_id)
        attempts = list(await self.session.scalars(query.with_for_update(skip_locked=True)))
        for attempt in attempts:
            await self._finalize(attempt, auto=True)
        if attempts:
            await self.session.commit()
        return len(attempts)

    async def finalize_expired(self) -> int:
        return await self._finalize_expired()

    async def _finalize(self, attempt: QuizAttempt, *, auto: bool) -> None:
        questions = await self._questions(attempt.quiz_id)
        score, maximum = auto_grade(questions, attempt.answers)
        attempt.status = AttemptStatus.AUTO_SUBMITTED if auto else AttemptStatus.SUBMITTED
        attempt.submitted_at = (
            min(utc_now(), attempt.expires_at) if attempt.expires_at else utc_now()
        )
        attempt.score = score + sum(attempt.manual_scores.values())
        attempt.max_score = maximum

    async def _student_quiz(self, user: CurrentUser, quiz_id: uuid.UUID) -> Quiz:
        quiz, role = await self._quiz(user, quiz_id)
        if role != "student":
            raise AppError("quizzes.not_a_student", 403)
        return quiz

    def _attempt_out(self, attempt: QuizAttempt, questions: list[QuizQuestion]) -> AttemptOut:
        running = attempt.status is AttemptStatus.IN_PROGRESS
        return AttemptOut(
            **self._attempt_summary(attempt, questions).model_dump(),
            quiz_id=str(attempt.quiz_id),
            expires_at=attempt.expires_at,
            answers=attempt.answers,
            questions=[self._student_question(q) for q in questions] if running else None,
            server_time=utc_now(),
        )

    async def start(self, user: CurrentUser, quiz_id: uuid.UUID) -> AttemptOut:
        quiz = await self._student_quiz(user, quiz_id)
        # One start at a time per quiz: two quick clicks resume the attempt instead of using two.
        await self.session.get(Quiz, quiz.id, with_for_update=True)
        await self._finalize_expired(quiz.id, user.id)
        questions = await self._questions(quiz.id)
        running = await self.session.scalar(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.student_id == user.id,
                QuizAttempt.status == AttemptStatus.IN_PROGRESS,
            )
        )
        if running is not None:
            return self._attempt_out(running, questions)
        now = utc_now()
        if quiz.available_from and now < quiz.available_from:
            raise AppError("quizzes.not_available", 409)
        if quiz.deadline and now > quiz.deadline:
            raise AppError("quizzes.expired", 409)
        used = await self.session.scalar(
            select(func.count())
            .select_from(QuizAttempt)
            .where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id)
        )
        if (used or 0) >= quiz.max_attempts:
            raise AppError("quizzes.attempt_limit_reached", 409)
        attempt = QuizAttempt(
            quiz_id=quiz.id,
            student_id=user.id,
            attempt_number=(used or 0) + 1,
            started_at=now,
            expires_at=attempt_expiry(now, quiz.time_limit_seconds, quiz.deadline),
        )
        self.session.add(attempt)
        await self.session.commit()
        return self._attempt_out(attempt, questions)

    async def _own_attempt(self, user: CurrentUser, attempt_id: uuid.UUID) -> QuizAttempt:
        attempt = await self.session.scalar(
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id, QuizAttempt.student_id == user.id)
            .with_for_update()
        )
        if attempt is None:
            raise AppError("quizzes.attempt_not_found", 404)
        return attempt

    async def attempt(self, user: CurrentUser, attempt_id: uuid.UUID) -> AttemptOut:
        attempt = await self._own_attempt(user, attempt_id)
        if (
            attempt.status is AttemptStatus.IN_PROGRESS
            and attempt.expires_at
            and attempt.expires_at <= utc_now()
        ):
            await self._finalize(attempt, auto=True)
            await self.session.commit()
        return self._attempt_out(attempt, await self._questions(attempt.quiz_id))

    async def save(self, user: CurrentUser, attempt_id: uuid.UUID, data: AnswersIn) -> AttemptOut:
        return await self._record(user, attempt_id, data, submit=False)

    async def submit(self, user: CurrentUser, attempt_id: uuid.UUID, data: AnswersIn) -> AttemptOut:
        return await self._record(user, attempt_id, data, submit=True)

    async def _record(
        self, user: CurrentUser, attempt_id: uuid.UUID, data: AnswersIn, *, submit: bool
    ) -> AttemptOut:
        attempt = await self._own_attempt(user, attempt_id)
        questions = await self._questions(attempt.quiz_id)
        if attempt.status is not AttemptStatus.IN_PROGRESS:
            raise AppError("quizzes.attempt_closed", 409)
        now = utc_now()
        late = attempt.expires_at is not None and now > attempt.expires_at + EXPIRY_GRACE
        if late:
            # The timer is the server's: what arrives after it is not counted, what was saved before is.
            await self._finalize(attempt, auto=True)
        else:
            attempt.answers = clean_answers(questions, data.answers)
            if submit:
                await self._finalize(attempt, auto=False)
        await self.session.commit()
        if late:
            raise AppError("quizzes.time_is_up", 409)
        return self._attempt_out(attempt, questions)

    # --- the teacher's side ------------------------------------------------------------------

    async def attempts(self, user: CurrentUser, quiz_id: uuid.UUID) -> AttemptListOut:
        quiz = await self._managed_quiz(user, quiz_id)
        await self._finalize_expired(quiz.id)
        questions = await self._questions(quiz.id)
        rows = await self.session.execute(
            select(QuizAttempt, User, AcademicGroup.code)
            .join(User, User.id == QuizAttempt.student_id)
            .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
            .where(QuizAttempt.quiz_id == quiz.id)
            .order_by(User.display_name, QuizAttempt.attempt_number)
        )
        return AttemptListOut(
            items=[
                AttemptRowOut(
                    **self._attempt_summary(attempt, questions).model_dump(),
                    student=StudentOut(
                        id=str(person.id), display_name=person.display_name, group_code=group
                    ),
                )
                for attempt, person, group in rows
            ]
        )

    async def review(self, user: CurrentUser, attempt_id: uuid.UUID) -> AttemptReviewOut:
        attempt = await self.session.get(QuizAttempt, attempt_id)
        if attempt is None:
            raise AppError("quizzes.attempt_not_found", 404)
        await self._managed_quiz(user, attempt.quiz_id)
        questions = await self._questions(attempt.quiz_id)
        person = await self.session.get(User, attempt.student_id)
        assert person is not None
        group = (
            await self.session.scalar(
                select(AcademicGroup.code).where(AcademicGroup.id == person.academic_group_id)
            )
            if person.academic_group_id
            else None
        )
        return AttemptReviewOut(
            **self._attempt_summary(attempt, questions).model_dump(),
            student=StudentOut(
                id=str(person.id), display_name=person.display_name, group_code=group
            ),
            quiz_id=str(attempt.quiz_id),
            answers=attempt.answers,
            manual_scores={k: int(v) for k, v in attempt.manual_scores.items()},
            questions=[self._manager_question(q) for q in questions],
        )

    async def score_open_questions(
        self, user: CurrentUser, attempt_id: uuid.UUID, data: ManualScoresIn
    ) -> AttemptReviewOut:
        attempt = await self.session.get(QuizAttempt, attempt_id, with_for_update=True)
        if attempt is None:
            raise AppError("quizzes.attempt_not_found", 404)
        await self._managed_quiz(user, attempt.quiz_id)
        if attempt.status is AttemptStatus.IN_PROGRESS:
            raise AppError("quizzes.attempt_not_finished", 409)
        questions = {str(q.id): q for q in await self._questions(attempt.quiz_id)}
        scores: dict[str, int] = {}
        for key, points in data.scores.items():
            question = questions.get(key)
            if question is None or question.type is not QuestionType.SHORT_ANSWER:
                raise AppError("quizzes.not_an_open_question", 422)
            if not 0 <= points <= question.points:
                raise AppError("quizzes.points_out_of_range", 422)
            scores[key] = points
        attempt.manual_scores = {**attempt.manual_scores, **scores}
        auto, maximum = auto_grade(list(questions.values()), attempt.answers)
        attempt.score = auto + sum(attempt.manual_scores.values())
        attempt.max_score = maximum
        # Scores are personal data (§5.4): the audit entry names the attempt, not the points.
        record_audit(
            self.session,
            AuditAction.QUIZ_GRADED,
            actor_id=user.id,
            target_type="quiz_attempt",
            target_id=attempt.id,
            details={"quiz_id": str(attempt.quiz_id)},
        )
        await self.session.commit()
        return await self.review(user, attempt_id)

    async def stats(self, user: CurrentUser, quiz_id: uuid.UUID) -> QuizStatsOut:
        quiz = await self._managed_quiz(user, quiz_id)
        await self._finalize_expired(quiz.id)
        questions = await self._questions(quiz.id)
        attempts = list(
            await self.session.scalars(
                select(QuizAttempt).where(
                    QuizAttempt.quiz_id == quiz.id,
                    QuizAttempt.status != AttemptStatus.IN_PROGRESS,
                )
            )
        )
        percents = [
            round(100 * a.score / a.max_score)
            for a in attempts
            if a.score is not None and a.max_score
        ]
        buckets = Counter(
            "0–50" if p <= 50 else "51–70" if p <= 70 else "71–90" if p <= 90 else "91–100"
            for p in percents
        )
        closed = [q for q in questions if q.type is not QuestionType.SHORT_ANSWER]
        return QuizStatsOut(
            submitted_attempts=len(attempts),
            students=len({a.student_id for a in attempts}),
            average_percent=round(sum(percents) / len(percents)) if percents else None,
            distribution=[
                DistributionBucket(label=label, count=buckets[label])
                for label in ("0–50", "51–70", "71–90", "91–100")
            ],
            questions=[
                QuestionStats(
                    question_id=str(q.id),
                    position=q.position,
                    prompt=q.prompt,
                    type=q.type,
                    correct_percent=(
                        round(
                            100
                            * sum(
                                _same_answer(q.correct_answer, a.answers.get(str(q.id)))
                                for a in attempts
                            )
                            / len(attempts)
                        )
                        if attempts and q in closed
                        else None
                    ),
                )
                for q in questions
            ],
            pending_review=sum(1 for a in attempts if self._pending_review(a, questions)),
        )
