import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.core.deps import JobsDep, SessionDep, SettingsDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.audiences.router import audience_out, parse_audience
from app.modules.audiences.service import Audiences
from app.modules.events.schemas import (
    AttendeeOut,
    AttendeesOut,
    CheckInIn,
    CheckInOut,
    EventDetailsIn,
    EventIn,
    EventOut,
    EventPageOut,
    EventRoomOut,
    EventUpdateIn,
    MyRegistrationOut,
    TicketsOut,
)
from app.modules.events.service import (
    MAX_PAGE,
    EventDetails,
    EventService,
    EventView,
    Period,
    has_ticket,
)
from app.modules.events.tickets import ticket_code
from app.modules.users.service import CurrentUser

MANAGE_PERMISSION = "events.manage"
CHECK_IN_PERMISSION = "events.check_in"

router = APIRouter(tags=["events"], responses=COMMON_ERROR_RESPONSES)
Manager = Annotated[CurrentUser, Depends(require_permission(MANAGE_PERMISSION))]
Doorkeeper = Annotated[CurrentUser, Depends(require_permission(CHECK_IN_PERMISSION))]
IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key", max_length=100, description="Repeating it returns the first result"
    ),
]


def _details(body: EventDetailsIn) -> EventDetails:
    return EventDetails(
        title=body.title,
        description=body.description,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        room_code=body.room_code or None,
        location=body.location,
        capacity=body.capacity,
    )


async def _out(session: SessionDep, secret: str, views: list[EventView]) -> list[EventOut]:
    labels = await Audiences(session).labels([view.event.audience for view in views])
    items = []
    for view in views:
        event, mine = view.event, view.mine
        items.append(
            EventOut(
                id=str(event.id),
                title=event.title,
                description=event.description,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                room=EventRoomOut(code=view.room.code, name=view.room.name_az)
                if view.room
                else None,
                location=event.location,
                capacity=event.capacity,
                going=view.going,
                spots_left=max(event.capacity - view.going, 0) if event.capacity else None,
                audience=audience_out(event.audience, labels),
                status=event.status,
                version=event.version,
                my_registration=MyRegistrationOut(
                    status=mine.status,
                    ticket_code=ticket_code(secret, event.id, mine.id)
                    if has_ticket(mine, event)
                    else None,
                    checked_in_at=mine.checked_in_at,
                )
                if mine
                else None,
            )
        )
    return items


async def _one(
    session: SessionDep, settings: SettingsDep, event_id: uuid.UUID, user: CurrentUser
) -> EventOut:
    view = await EventService(session).view(
        event_id, user.id, user.has_permission(MANAGE_PERMISSION)
    )
    return (await _out(session, settings.ticket_secret, [view]))[0]


@router.get(
    "/events",
    response_model=EventPageOut,
    operation_id="listEvents",
    summary="Events announced to me (staff who manage events: all)",
)
async def list_events(
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    period: Period = Period.UPCOMING,
    registered: Annotated[bool, Query(description="Only events I registered for")] = False,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 20,
) -> EventPageOut:
    page = await EventService(session).page(
        user.id, user.has_permission(MANAGE_PERMISSION), period, registered, cursor, limit
    )
    return EventPageOut(
        items=await _out(session, settings.ticket_secret, page.items),
        next_cursor=page.next_cursor,
    )


@router.get(
    "/me/tickets",
    response_model=TicketsOut,
    operation_id="listMyTickets",
    summary="My tickets for events that have not ended",
)
async def list_my_tickets(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep
) -> TicketsOut:
    views = await EventService(session).my_tickets(user.id)
    return TicketsOut(items=await _out(session, settings.ticket_secret, views))


@router.get(
    "/events/{event_id}", response_model=EventOut, operation_id="readEvent", summary="One event"
)
async def read_event(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep, event_id: uuid.UUID
) -> EventOut:
    return await _one(session, settings, event_id, user)


@router.post(
    "/events",
    response_model=EventOut,
    status_code=201,
    operation_id="publishEvent",
    summary="Publish an event to an audience and notify it",
)
async def publish_event(
    user: Manager,
    session: SessionDep,
    settings: SettingsDep,
    jobs: JobsDep,
    body: EventIn,
    idempotency_key: IdempotencyKey = None,
) -> EventOut:
    event, created = await EventService(session).publish(
        _details(body), parse_audience(body.audience), user.id, idempotency_key
    )
    if created:
        await jobs.dispatch_notifications()
    return await _one(session, settings, event.id, user)


@router.patch(
    "/events/{event_id}",
    response_model=EventOut,
    operation_id="updateEvent",
    summary="Change an event; registered attendees hear about a new time or place",
)
async def update_event(
    user: Manager,
    session: SessionDep,
    settings: SettingsDep,
    jobs: JobsDep,
    event_id: uuid.UUID,
    body: EventUpdateIn,
) -> EventOut:
    await EventService(session).update(event_id, body.version, _details(body), user.id)
    await jobs.dispatch_notifications()
    return await _one(session, settings, event_id, user)


@router.post(
    "/events/{event_id}/cancel",
    response_model=EventOut,
    operation_id="cancelEvent",
    summary="Cancel an event and tell registered attendees (idempotent)",
)
async def cancel_event(
    user: Manager, session: SessionDep, settings: SettingsDep, jobs: JobsDep, event_id: uuid.UUID
) -> EventOut:
    await EventService(session).cancel(event_id, user.id)
    await jobs.dispatch_notifications()
    return await _one(session, settings, event_id, user)


@router.put(
    "/events/{event_id}/registration",
    response_model=EventOut,
    operation_id="registerForEvent",
    summary="RSVP: register and receive a ticket (idempotent)",
)
async def register_for_event(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep, event_id: uuid.UUID
) -> EventOut:
    await EventService(session).register(event_id, user.id)
    return await _one(session, settings, event_id, user)


@router.delete(
    "/events/{event_id}/registration",
    response_model=EventOut,
    operation_id="cancelEventRegistration",
    summary="Withdraw my RSVP; the ticket stops working (idempotent)",
)
async def cancel_registration(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep, event_id: uuid.UUID
) -> EventOut:
    await EventService(session).unregister(event_id, user.id)
    return await _one(session, settings, event_id, user)


@router.get(
    "/events/{event_id}/attendees",
    response_model=AttendeesOut,
    operation_id="listEventAttendees",
    summary="Registered attendees and check-in state (staff at the door)",
)
async def list_attendees(_: Doorkeeper, session: SessionDep, event_id: uuid.UUID) -> AttendeesOut:
    _event, attendees = await EventService(session).attendees(event_id)
    return AttendeesOut(
        going=len(attendees),
        checked_in=sum(1 for item in attendees if item.registration.checked_in_at),
        items=[
            AttendeeOut(
                registration_id=str(item.registration.id),
                name=item.name,
                group=item.group,
                checked_in_at=item.registration.checked_in_at,
                check_in_method=item.registration.check_in_method,
            )
            for item in attendees
        ],
    )


@router.post(
    "/events/{event_id}/check-ins",
    response_model=CheckInOut,
    operation_id="checkInAttendee",
    summary="Admit an attendee by ticket code or, manually, by registration",
)
async def check_in(
    user: Doorkeeper,
    session: SessionDep,
    settings: SettingsDep,
    event_id: uuid.UUID,
    body: CheckInIn,
) -> CheckInOut:
    registration_id = None
    if body.registration_id is not None:
        try:
            registration_id = uuid.UUID(body.registration_id)
        except ValueError as exc:
            raise AppError("events.ticket_invalid", 422) from exc
    attendee = await EventService(session).check_in(
        event_id,
        user.id,
        secret=settings.ticket_secret,
        code=body.code,
        registration_id=registration_id,
    )
    registration = attendee.registration
    assert registration.checked_in_at is not None
    assert registration.check_in_method is not None
    return CheckInOut(
        name=attendee.name,
        group=attendee.group,
        checked_in_at=registration.checked_in_at,
        check_in_method=registration.check_in_method,
    )
