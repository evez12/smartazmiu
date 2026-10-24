from pydantic import BaseModel, ConfigDict

from app.modules.users.models import UserStatus


class MeResponse(BaseModel):
    """The signed-in user's own account. Contact details are omitted until a screen needs them."""

    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str
    given_name: str
    family_name: str
    status: UserStatus
    roles: list[str]
    permissions: list[str]
