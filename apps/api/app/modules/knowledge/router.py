import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.knowledge.models import TipStatus
from app.modules.knowledge.schemas import (
    MyTipOut,
    SubjectTipsOut,
    TipEligibilityOut,
    TipIn,
    TipModerationPageOut,
    TipReviewIn,
)
from app.modules.knowledge.service import TipService
from app.modules.users.service import CurrentUser

router = APIRouter(tags=["tips"], responses=COMMON_ERROR_RESPONSES)
# Tips are moderated by the staff who handle reports (§5.5).
TipReader = Annotated[CurrentUser, Depends(require_permission("admin.reports.read"))]
TipHandler = Annotated[CurrentUser, Depends(require_permission("admin.reports.handle"))]


def get_tips(session: SessionDep) -> TipService:
    return TipService(session)


TipsDep = Annotated[TipService, Depends(get_tips)]


@router.get(
    "/tips/eligible",
    response_model=list[TipEligibilityOut],
    operation_id="listTipEligibility",
    summary="Subjects and semesters I passed, with my card's status",
)
async def eligible(user: CurrentUserDep, tips: TipsDep) -> list[TipEligibilityOut]:
    return await tips.eligible(user)


@router.get(
    "/subjects/{subject_id}/tips",
    response_model=SubjectTipsOut,
    operation_id="readSubjectTips",
    summary="The subject page: published cards aggregated (difficulty, workload, resources, top tips)",
)
async def subject_tips(
    user: CurrentUserDep, tips: TipsDep, subject_id: uuid.UUID
) -> SubjectTipsOut:
    return await tips.subject_page(user, subject_id)


@router.get(
    "/subjects/{subject_id}/tips/mine",
    response_model=list[MyTipOut],
    operation_id="listMySubjectTips",
    summary="My cards for a subject, with their moderation status",
)
async def my_tips(user: CurrentUserDep, tips: TipsDep, subject_id: uuid.UUID) -> list[MyTipOut]:
    return await tips.my_tips(user, subject_id)


@router.put(
    "/subjects/{subject_id}/tips/mine",
    response_model=MyTipOut,
    operation_id="saveMySubjectTip",
    summary="Write or edit my card for a subject and semester (goes to moderation)",
)
async def save_tip(
    user: CurrentUserDep, tips: TipsDep, subject_id: uuid.UUID, body: TipIn
) -> MyTipOut:
    return await tips.upsert(user, subject_id, body)


@router.put(
    "/tips/{tip_id}/upvote",
    response_model=int,
    operation_id="upvoteTip",
    summary="Upvote a card (idempotent); returns the new count",
)
async def upvote(user: CurrentUserDep, tips: TipsDep, tip_id: uuid.UUID) -> int:
    return await tips.upvote(user, tip_id, True)


@router.delete(
    "/tips/{tip_id}/upvote",
    response_model=int,
    operation_id="removeTipUpvote",
    summary="Take my upvote back (idempotent); returns the new count",
)
async def remove_upvote(user: CurrentUserDep, tips: TipsDep, tip_id: uuid.UUID) -> int:
    return await tips.upvote(user, tip_id, False)


@router.get(
    "/moderation/tips",
    response_model=TipModerationPageOut,
    operation_id="listTipsForModeration",
    summary="Cards to review, oldest first",
)
async def moderation_list(
    _: TipReader,
    tips: TipsDep,
    status: TipStatus | None = TipStatus.PENDING,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> TipModerationPageOut:
    items, total = await tips.moderation_page(status, offset, limit)
    return TipModerationPageOut(items=items, total=total)


@router.patch(
    "/moderation/tips/{tip_id}",
    status_code=204,
    operation_id="reviewTip",
    summary="Publish, reject, hide or restore a card",
)
async def review(actor: TipHandler, tips: TipsDep, tip_id: uuid.UUID, body: TipReviewIn) -> None:
    await tips.review(actor, tip_id, body.status, body.note)
