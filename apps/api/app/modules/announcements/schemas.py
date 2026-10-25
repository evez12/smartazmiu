import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, StringConstraints

from app.modules.announcements.models import AnnouncementStatus
from app.modules.audiences.schemas import AudienceIn, AudienceOut

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


def _utc(value: dt.datetime | None) -> dt.datetime | None:
    return value.astimezone(dt.UTC) if value is not None else None


Expiry = Annotated[AwareDatetime | None, AfterValidator(_utc)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class AnnouncementIn(_Frozen):
    title: Title
    body: Body
    """Plain text; line breaks are kept."""
    audience: AudienceIn
    expires_at: Expiry = None
    """After this moment the announcement is no longer shown; null keeps it until archived."""


class AnnouncementUpdateIn(_Frozen):
    version: int
    title: Title
    body: Body
    expires_at: Expiry = None


class AnnouncementOut(_Frozen):
    id: str
    title: str
    body: str
    status: AnnouncementStatus
    audience: AudienceOut
    published_at: dt.datetime
    expires_at: dt.datetime | None
    version: int


class AnnouncementPageOut(_Frozen):
    items: list[AnnouncementOut]
    next_before: str | None


class ManagedAnnouncementOut(AnnouncementOut):
    recipients: int
    """People the announcement reached so far, including those who joined the audience later."""


class ManagedAnnouncementPageOut(_Frozen):
    items: list[ManagedAnnouncementOut]
    total: int
    page: int
    page_size: int
