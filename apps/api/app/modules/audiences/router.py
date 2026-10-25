import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.rbac import CurrentUserDep
from app.modules.audiences.schemas import (
    AudienceIn,
    AudienceOptionOut,
    AudienceOptionsOut,
    AudienceOut,
)
from app.modules.audiences.service import Audience, AudienceOption, Audiences, AudienceType
from app.modules.users.service import CurrentUser

# Whoever may address an audience (announcements, events) may browse the targets.
PICKER_PERMISSIONS = ("announcements.publish", "events.manage")

router = APIRouter(tags=["audiences"], responses=COMMON_ERROR_RESPONSES)


async def require_publisher(user: CurrentUserDep) -> CurrentUser:
    if not any(user.has_permission(code) for code in PICKER_PERMISSIONS):
        raise AppError("auth.forbidden", 403, details={"permission": PICKER_PERMISSIONS[0]})
    return user


def parse_audience(value: AudienceIn) -> Audience:
    try:
        target = uuid.UUID(value.target_id) if value.target_id is not None else None
    except ValueError as exc:
        raise AppError("audience.invalid", 422) from exc
    return Audience(value.type, target)


def audience_out(audience: Audience, labels: dict[Audience, AudienceOption]) -> AudienceOut:
    option = labels.get(audience)
    return AudienceOut(
        type=audience.type,
        target_id=str(audience.target_id) if audience.target_id else None,
        label=option.label if option else None,
        detail=option.detail if option else None,
    )


@router.get(
    "/audiences/options",
    response_model=AudienceOptionsOut,
    operation_id="listAudienceOptions",
    summary="Faculties, specialties, groups or course offerings to address (staff)",
)
async def list_audience_options(
    _: Annotated[CurrentUser, Depends(require_publisher)],
    session: SessionDep,
    type: Annotated[AudienceType, Query()],
    q: Annotated[str, Query(max_length=100)] = "",
) -> AudienceOptionsOut:
    options = await Audiences(session).options(type, q)
    return AudienceOptionsOut(
        items=[
            AudienceOptionOut(id=str(option.id), label=option.label, detail=option.detail)
            for option in options
        ]
    )
