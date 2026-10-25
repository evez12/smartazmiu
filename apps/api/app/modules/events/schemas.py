import datetime as dt
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.modules.audiences.schemas import AudienceIn, AudienceOut
from app.modules.events.models import CheckInMethod, EventStatus, RegistrationStatus

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]
Location = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


def _utc(value: dt.datetime) -> dt.datetime:
    return value.astimezone(dt.UTC)


Instant = Annotated[AwareDatetime, AfterValidator(_utc)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class EventDetailsIn(_Frozen):
    title: Title
    description: Description
    """Plain text; line breaks are kept."""
    starts_at: Instant
    ends_at: Instant
    room_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    """A campus room (links to the map); or describe the place in ``location``."""
    location: Location = ""
    capacity: Annotated[int, Field(ge=1, le=100_000)] | None = None
    """Null: no limit."""


class EventIn(EventDetailsIn):
    audience: AudienceIn


class EventUpdateIn(EventDetailsIn):
    version: int


class EventRoomOut(_Frozen):
    code: str
    name: str


class MyRegistrationOut(_Frozen):
    status: RegistrationStatus
    ticket_code: str | None
    """Text of the QR code; null when the registration or the event is cancelled."""
    checked_in_at: dt.datetime | None


class EventOut(_Frozen):
    id: str
    title: str
    description: str
    starts_at: dt.datetime
    ends_at: dt.datetime
    room: EventRoomOut | None
    location: str
    capacity: int | None
    going: int
    """Registrations (RSVP "going")."""
    spots_left: int | None
    """Null when there is no limit."""
    audience: AudienceOut
    status: EventStatus
    version: int
    my_registration: MyRegistrationOut | None


class EventPageOut(_Frozen):
    items: list[EventOut]
    next_cursor: str | None


class TicketsOut(_Frozen):
    items: list[EventOut]
    """Events I registered for that have not ended, soonest first; each carries its ticket."""


class AttendeeOut(_Frozen):
    registration_id: str
    name: str
    group: str | None
    checked_in_at: dt.datetime | None
    check_in_method: CheckInMethod | None


class AttendeesOut(_Frozen):
    going: int
    checked_in: int
    items: list[AttendeeOut]


class CheckInIn(_Frozen):
    code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    """The scanned or typed ticket code."""
    registration_id: str | None = None
    """For a manual check-in from the attendee list."""

    @model_validator(mode="after")
    def one_way(self) -> Self:
        if (self.code is None) == (self.registration_id is None):
            raise ValueError("Give either a ticket code or a registration id")
        return self


class CheckInOut(_Frozen):
    name: str
    group: str | None
    checked_in_at: dt.datetime
    check_in_method: CheckInMethod
