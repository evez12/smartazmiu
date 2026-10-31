import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep
from app.modules.quizzes.schemas import (
    AnswersIn,
    AttemptListOut,
    AttemptOut,
    AttemptReviewOut,
    ManualScoresIn,
    QuestionCreateIn,
    QuizCreateIn,
    QuizDetailOut,
    QuizListOut,
    QuizStatsOut,
)
from app.modules.quizzes.service import QuizService

router = APIRouter(tags=["quizzes"], responses=COMMON_ERROR_RESPONSES)


def get_quizzes(session: SessionDep) -> QuizService:
    return QuizService(session)


QuizzesDep = Annotated[QuizService, Depends(get_quizzes)]


@router.get("/quizzes", response_model=QuizListOut, operation_id="listQuizzes")
async def list_quizzes(
    user: CurrentUserDep,
    service: QuizzesDep,
    offering_id: Annotated[uuid.UUID | None, Query()] = None,
) -> QuizListOut:
    return QuizListOut(items=await service.quizzes(user, offering_id))


@router.post("/quizzes", response_model=QuizDetailOut, status_code=201, operation_id="createQuiz")
async def create_quiz(
    user: CurrentUserDep, service: QuizzesDep, body: QuizCreateIn
) -> QuizDetailOut:
    return await service.create(user, body)


@router.get("/quizzes/{quiz_id}", response_model=QuizDetailOut, operation_id="getQuiz")
async def get_quiz(user: CurrentUserDep, service: QuizzesDep, quiz_id: uuid.UUID) -> QuizDetailOut:
    return await service.detail(user, quiz_id)


@router.post(
    "/quizzes/{quiz_id}/questions",
    response_model=QuizDetailOut,
    status_code=201,
    operation_id="addQuizQuestion",
)
async def add_question(
    user: CurrentUserDep, service: QuizzesDep, quiz_id: uuid.UUID, body: QuestionCreateIn
) -> QuizDetailOut:
    return await service.add_question(user, quiz_id, body)


@router.delete(
    "/quizzes/{quiz_id}/questions/{question_id}",
    response_model=QuizDetailOut,
    operation_id="deleteQuizQuestion",
)
async def delete_question(
    user: CurrentUserDep, service: QuizzesDep, quiz_id: uuid.UUID, question_id: uuid.UUID
) -> QuizDetailOut:
    return await service.delete_question(user, quiz_id, question_id)


@router.post("/quizzes/{quiz_id}/publish", response_model=QuizDetailOut, operation_id="publishQuiz")
async def publish_quiz(
    user: CurrentUserDep, service: QuizzesDep, quiz_id: uuid.UUID
) -> QuizDetailOut:
    return await service.publish(user, quiz_id)


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=AttemptOut,
    status_code=201,
    operation_id="startQuizAttempt",
    summary="Start an attempt, or resume the one in progress",
)
async def start_attempt(
    user: CurrentUserDep, service: QuizzesDep, quiz_id: uuid.UUID
) -> AttemptOut:
    return await service.start(user, quiz_id)


@router.get(
    "/quizzes/{quiz_id}/attempts",
    response_model=AttemptListOut,
    operation_id="listQuizAttempts",
    summary="Every attempt of the quiz, for the people who manage the offering",
)
async def list_attempts(
    user: CurrentUserDep, service: QuizzesDep, quiz_id: uuid.UUID
) -> AttemptListOut:
    return await service.attempts(user, quiz_id)


@router.get("/quizzes/{quiz_id}/stats", response_model=QuizStatsOut, operation_id="getQuizStats")
async def get_stats(user: CurrentUserDep, service: QuizzesDep, quiz_id: uuid.UUID) -> QuizStatsOut:
    return await service.stats(user, quiz_id)


@router.get("/quiz-attempts/{attempt_id}", response_model=AttemptOut, operation_id="getQuizAttempt")
async def get_attempt(
    user: CurrentUserDep, service: QuizzesDep, attempt_id: uuid.UUID
) -> AttemptOut:
    return await service.attempt(user, attempt_id)


@router.patch(
    "/quiz-attempts/{attempt_id}",
    response_model=AttemptOut,
    operation_id="saveQuizAnswers",
    summary="Save the answers so far; answers that arrive after the time limit are not counted",
)
async def save_answers(
    user: CurrentUserDep, service: QuizzesDep, attempt_id: uuid.UUID, body: AnswersIn
) -> AttemptOut:
    return await service.save(user, attempt_id, body)


@router.post(
    "/quiz-attempts/{attempt_id}/submit",
    response_model=AttemptOut,
    operation_id="submitQuizAttempt",
)
async def submit_attempt(
    user: CurrentUserDep, service: QuizzesDep, attempt_id: uuid.UUID, body: AnswersIn
) -> AttemptOut:
    return await service.submit(user, attempt_id, body)


@router.get(
    "/quiz-attempts/{attempt_id}/review",
    response_model=AttemptReviewOut,
    operation_id="reviewQuizAttempt",
)
async def review_attempt(
    user: CurrentUserDep, service: QuizzesDep, attempt_id: uuid.UUID
) -> AttemptReviewOut:
    return await service.review(user, attempt_id)


@router.put(
    "/quiz-attempts/{attempt_id}/open-question-scores",
    response_model=AttemptReviewOut,
    operation_id="scoreOpenQuestions",
)
async def score_open_questions(
    user: CurrentUserDep, service: QuizzesDep, attempt_id: uuid.UUID, body: ManualScoresIn
) -> AttemptReviewOut:
    return await service.score_open_questions(user, attempt_id, body)
