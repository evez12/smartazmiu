import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.modules.users.models import ContactVisibility, DmPolicy, PersonType, UserStatus

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")


def _plain_text(value: str) -> str:
    if _CONTROL_CHARACTERS.search(value):
        raise ValueError("control characters are not allowed")
    return value


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
    photo_url: str | None
    onboarding_done: bool
    """False until the user finishes or dismisses the first-run tour."""


class OnboardingIn(BaseModel):
    done: bool
    """True finishes the tour; false shows it again (from the profile page)."""


class ProfileOut(BaseModel):
    """The signed-in user's own profile, including their e-mail (it is their data)."""

    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str
    given_name: str
    family_name: str
    email: str | None
    university_id: str | None
    person_type: PersonType | None
    bio: str
    photo_url: str | None
    dm_policy: DmPolicy
    contact_visibility: ContactVisibility
    version: int


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1, description="Version of the profile the edit is based on")
    bio: Annotated[str, Field(max_length=300), AfterValidator(_plain_text)] | None = None
    dm_policy: DmPolicy | None = None
    contact_visibility: ContactVisibility | None = None
