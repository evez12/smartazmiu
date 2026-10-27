import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.quizzes.schemas import (
    AnswersIn,
    AttemptOut,
    QuestionCreateIn,
    QuestionOut,
    QuizCreateIn,
    QuizOut,
)
from app.modules.quizzes.service import QuizService
from app.modules.users.service import CurrentUser

router = APIRouter(tags=["quizzes"], responses=COMMON_ERROR_RESPONSES)
Manager = Annotated[CurrentUser, Depends(require_permission("quizzes.manage"))]


@router.post("/quizzes", response_model=QuizOut, status_code=201)
async def create_quiz(actor: Manager, session: SessionDep, body: QuizCreateIn) -> QuizOut:
    return QuizOut.model_validate(await QuizService(session).create(body, actor.id))


@router.post("/quizzes/{quiz_id}/questions", response_model=QuestionOut, status_code=201)
async def add_question(
    _: Manager,
    session: SessionDep,
    quiz_id: uuid.UUID,
    position: int,
    body: QuestionCreateIn,
) -> QuestionOut:
    return QuestionOut.model_validate(
        await QuizService(session).add_question(quiz_id, position, body)
    )


@router.post("/quizzes/{quiz_id}/attempts", response_model=AttemptOut, status_code=201)
async def start_attempt(
    user: CurrentUserDep, session: SessionDep, quiz_id: uuid.UUID
) -> AttemptOut:
    return AttemptOut.model_validate(await QuizService(session).start_attempt(quiz_id, user.id))


@router.patch("/quiz-attempts/{attempt_id}", response_model=AttemptOut)
async def save_attempt_answers(
    user: CurrentUserDep,
    session: SessionDep,
    attempt_id: uuid.UUID,
    body: AnswersIn,
) -> AttemptOut:
    return AttemptOut.model_validate(
        await QuizService(session).save_answers(attempt_id, user.id, body)
    )


@router.post("/quiz-attempts/{attempt_id}/submit", response_model=AttemptOut)
async def submit_attempt(
    user: CurrentUserDep,
    session: SessionDep,
    attempt_id: uuid.UUID,
    body: AnswersIn,
) -> AttemptOut:
    return AttemptOut.model_validate(await QuizService(session).submit(attempt_id, user.id, body))
