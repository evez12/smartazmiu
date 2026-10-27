import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.assignments.schemas import (
    AssignmentCreateIn,
    AssignmentGradeIn,
    AssignmentOut,
    AssignmentSubmissionIn,
    GradeOut,
    SubmissionOut,
)
from app.modules.assignments.service import AssignmentService
from app.modules.users.service import CurrentUser

router = APIRouter(tags=["assignments"], responses=COMMON_ERROR_RESPONSES)
Manager = Annotated[CurrentUser, Depends(require_permission("assignments.manage"))]
Grader = Annotated[CurrentUser, Depends(require_permission("assignments.grade"))]


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    actor: Manager, session: SessionDep, body: AssignmentCreateIn
) -> AssignmentOut:
    return AssignmentOut.model_validate(await AssignmentService(session).create(body, actor.id))


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionOut,
    status_code=201,
)
async def submit_assignment(
    user: CurrentUserDep,
    session: SessionDep,
    assignment_id: uuid.UUID,
    body: AssignmentSubmissionIn,
) -> SubmissionOut:
    return SubmissionOut.model_validate(
        await AssignmentService(session).submit(assignment_id, user.id, body)
    )


@router.post(
    "/assignment-submissions/{submission_id}/grade",
    response_model=GradeOut,
)
async def grade_assignment(
    actor: Grader,
    session: SessionDep,
    submission_id: uuid.UUID,
    body: AssignmentGradeIn,
) -> GradeOut:
    return GradeOut.model_validate(
        await AssignmentService(session).grade(submission_id, actor.id, body)
    )
