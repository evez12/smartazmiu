import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import RedisDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.feedback.models import FeedbackStatus
from app.modules.feedback.schemas import (
    FeedbackCreatedOut,
    FeedbackIn,
    FeedbackOut,
    FeedbackPageOut,
    FeedbackStatusIn,
)
from app.modules.feedback.service import FeedbackService
from app.modules.users.service import CurrentUser

router = APIRouter(tags=["feedback"], responses=COMMON_ERROR_RESPONSES)
FeedbackReader = Annotated[CurrentUser, Depends(require_permission("admin.feedback.read"))]
FeedbackHandler = Annotated[CurrentUser, Depends(require_permission("admin.feedback.handle"))]


def get_feedback(session: SessionDep, cache: RedisDep) -> FeedbackService:
    return FeedbackService(session, cache)


FeedbackDep = Annotated[FeedbackService, Depends(get_feedback)]


@router.post(
    "/feedback",
    response_model=FeedbackCreatedOut,
    status_code=201,
    operation_id="sendFeedback",
    summary="Send feedback to the platform team",
)
async def send_feedback(
    user: CurrentUserDep, feedback: FeedbackDep, body: FeedbackIn
) -> FeedbackCreatedOut:
    created = await feedback.create(user, body.category, body.message, body.page, body.contact_ok)
    return FeedbackCreatedOut(id=str(created.id))


@router.get(
    "/admin/feedback",
    response_model=FeedbackPageOut,
    operation_id="listFeedback",
    summary="Feedback, newest first",
)
async def list_feedback(
    _: FeedbackReader,
    feedback: FeedbackDep,
    status: FeedbackStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FeedbackPageOut:
    items, total = await feedback.page(status, offset, limit)
    return FeedbackPageOut(items=items, total=total)


@router.patch(
    "/admin/feedback/{feedback_id}",
    response_model=FeedbackOut,
    operation_id="setFeedbackStatus",
    summary="Close feedback or open it again",
)
async def set_feedback_status(
    actor: FeedbackHandler, feedback: FeedbackDep, feedback_id: uuid.UUID, body: FeedbackStatusIn
) -> FeedbackOut:
    return await feedback.set_status(actor, feedback_id, body.status)
