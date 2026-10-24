from fastapi import APIRouter

from app.core.rbac import CurrentUserDep
from app.modules.users.schemas import MeResponse

router = APIRouter(tags=["users"])


@router.get("/me", response_model=MeResponse, summary="Signed-in user")
async def read_me(user: CurrentUserDep) -> MeResponse:
    return MeResponse(
        id=str(user.id),
        display_name=user.display_name,
        given_name=user.given_name,
        family_name=user.family_name,
        status=user.status,
        roles=sorted(user.roles),
        permissions=sorted(user.permissions),
    )
