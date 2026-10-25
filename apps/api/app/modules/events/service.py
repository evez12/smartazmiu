"""Events (§6): published to an audience like announcements, with RSVP, a QR ticket per registration and
check-in at the door by staff."""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import ColumnElement, Select, exists, func, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.academics.models import AcademicGroup
from app.modules.audiences.service import Audience, Audiences, is_member, members
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.campus.models import Room
from app.modules.events import tickets
from app.modules.events.models import (
    CheckInMethod,
    Event,
    EventRecipient,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import LateJoinBudget, NotificationSpec, Notifier
from app.modules.users.models import User

SUBJECT_TYPE = "event"
MAX_PAGE = 50
# Doors open before the start; staff can check people in from then until the event ends.
CHECK_IN_OPENS = timedelta(hours=2)


class Period(StrEnum):
    UPCOMING = "upcoming"
    """Not ended yet, soonest first."""
    PAST = "past"
    """Ended, most recent first."""


@dataclass(frozen=True, slots=True)
class EventDetails:
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    room_code: str | None
    location: str
    capacity: int | None


@dataclass(frozen=True, slots=True)
class EventView:
    event: Event
    room: Room | None
    going: int
    mine: EventRegistration | None


@dataclass(frozen=True, slots=True)
class EventPage:
    items: list[EventView]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class Attendee:
    registration: EventRegistration
    name: str
    group: str | None


def _spec(event: Event, kind: NotificationKind, dedupe_key: str) -> NotificationSpec:
    return NotificationSpec(
        category=NotificationCategory.EVENTS,
        kind=kind,
        subject_type=SUBJECT_TYPE,
        subject_id=event.id,
        dedupe_key=dedupe_key,
        title=event.title,
        link=f"/events/{event.id}",
    )


def _going(event_id: uuid.UUID) -> Select[uuid.UUID]:
    return select(EventRegistration.user_id).where(
        EventRegistration.event_id == event_id,
        EventRegistration.status == RegistrationStatus.GOING,
    )


def _visible(user_id: uuid.UUID) -> ColumnElement[bool]:
    """Announced to the user, or the user registered (registrations stay visible after a transfer)."""
    return or_(
        exists().where(EventRecipient.event_id == Event.id, EventRecipient.user_id == user_id),
        exists().where(
            EventRegistration.event_id == Event.id, EventRegistration.user_id == user_id
        ),
    )


def encode_cursor(event: Event) -> str:
    raw = f"{event.starts_at.isoformat()}|{event.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        moment, _, event_id = raw.partition("|")
        return datetime.fromisoformat(moment), uuid.UUID(event_id)
    except ValueError as exc:
        raise AppError("request.invalid_cursor", 422) from exc


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Staff ---------------------------------------------------------------------------------

    async def publish(
        self,
        details: EventDetails,
        audience: Audience,
        author_id: uuid.UUID,
        idempotency_key: str | None,
    ) -> tuple[Event, bool]:
        """Publishes and announces the event to its audience; a repeated ``Idempotency-Key`` returns the first."""
        if idempotency_key:
            existing = await self.session.scalar(
                select(Event).where(
                    Event.created_by == author_id, Event.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                return existing, False
        if details.starts_at <= utc_now():
            raise AppError("events.starts_in_past", 422)
        await Audiences(self.session).validate(audience)
        event = Event(created_by=author_id, idempotency_key=idempotency_key)
        await self._apply(event, details)
        event.set_audience(audience)
        self.session.add(event)
        await self.session.flush()
        await self._add_recipients(event)
        self._audit(
            AuditAction.EVENT_PUBLISHED, author_id, event, {"audience": audience.type.value}
        )
        await self.session.commit()
        return event, True

    async def update(
        self, event_id: uuid.UUID, version: int, details: EventDetails, actor_id: uuid.UUID
    ) -> Event:
        """Changes details; people who registered hear about a new time or place. The audience is fixed."""
        event = await self._locked(event_id)
        if event.version != version:
            raise AppError("events.version_conflict", 409, details={"version": event.version})
        if event.status is EventStatus.CANCELLED:
            raise AppError("events.cancelled", 409)
        if details.capacity is not None and details.capacity < await self._going_count(event.id):
            raise AppError("events.capacity_below_registrations", 409)
        before = (event.starts_at, event.ends_at, event.room_id, event.location)
        await self._apply(event, details)
        event.version += 1
        if (event.starts_at, event.ends_at, event.room_id, event.location) != before:
            await Notifier(self.session).notify(
                _going(event.id),
                _spec(event, NotificationKind.EVENT_CHANGED, f"event:{event.id}:v{event.version}"),
            )
        self._audit(AuditAction.EVENT_EDITED, actor_id, event)
        await self.session.commit()
        return event

    async def cancel(self, event_id: uuid.UUID, actor_id: uuid.UUID) -> Event:
        """Cancels the event (tickets stop working) and tells everyone who registered; idempotent."""
        event = await self._locked(event_id)
        if event.status is EventStatus.PUBLISHED:
            event.status = EventStatus.CANCELLED
            event.cancelled_at = utc_now()
            event.version += 1
            await Notifier(self.session).notify(
                _going(event.id),
                _spec(event, NotificationKind.EVENT_CANCELLED, f"event:{event.id}:cancelled"),
            )
            self._audit(AuditAction.EVENT_CANCELLED, actor_id, event)
            await self.session.commit()
        return event

    async def _apply(self, event: Event, details: EventDetails) -> None:
        if details.ends_at <= details.starts_at:
            raise AppError("events.invalid_times", 422)
        room_id = None
        if details.room_code:
            room_id = await self.session.scalar(
                select(Room.id).where(Room.code == details.room_code)
            )
            if room_id is None:
                raise AppError("events.room_not_found", 422)
        if room_id is None and not details.location:
            raise AppError("events.location_required", 422)
        event.title, event.description = details.title, details.description
        event.starts_at, event.ends_at = details.starts_at, details.ends_at
        event.room_id, event.location, event.capacity = room_id, details.location, details.capacity

    async def _add_recipients(self, event: Event, late: LateJoinBudget | None = None) -> int:
        """Adds audience members who are not recipients yet and announces the event to exactly them; people
        added after publication (``late``) in-app only, within the budget (D-054)."""
        audience = members(event.audience).subquery()
        added = await self.session.scalars(
            insert(EventRecipient)
            .from_select(
                ["event_id", "user_id"],
                select(literal(event.id, EventRecipient.__table__.c.event_id.type), audience.c[0]),
            )
            .on_conflict_do_nothing()
            .returning(EventRecipient.user_id)
        )
        new = list(added)
        notified = late.take(new) if late else new
        if notified:
            await Notifier(self.session).notify(
                select(EventRecipient.user_id).where(
                    EventRecipient.event_id == event.id, EventRecipient.user_id.in_(notified)
                ),
                _spec(event, NotificationKind.EVENT_PUBLISHED, f"event:{event.id}"),
                deliver=late is None,
            )
        return len(new)

    async def sync_recipients(self, late: LateJoinBudget | None = None) -> int:
        """People who joined an audience hear about its events that have not ended (§6.1), soonest first,
        in-app only (D-054); idempotent."""
        late = late or LateJoinBudget()
        added = 0
        for event in await self.session.scalars(
            select(Event)
            .where(Event.status == EventStatus.PUBLISHED, Event.ends_at > utc_now())
            .order_by(Event.starts_at, Event.id)
        ):
            added += await self._add_recipients(event, late)
        await self.session.commit()
        return added

    async def attendees(self, event_id: uuid.UUID) -> tuple[Event, list[Attendee]]:
        event = await self._get(event_id)
        rows = await self.session.execute(
            select(EventRegistration, User.display_name, AcademicGroup.code)
            .join(User, User.id == EventRegistration.user_id)
            .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
            .where(
                EventRegistration.event_id == event_id,
                EventRegistration.status == RegistrationStatus.GOING,
            )
            .order_by(User.family_name, User.given_name)
        )
        return event, [Attendee(registration, name, group) for registration, name, group in rows]

    async def check_in(
        self,
        event_id: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        secret: str,
        code: str | None = None,
        registration_id: uuid.UUID | None = None,
    ) -> Attendee:
        """Admits one attendee by ticket code (scan) or by registration (manual, audited)."""
        method = CheckInMethod.SCAN if code is not None else CheckInMethod.MANUAL
        scanned = tickets.parse_ticket(code) if code is not None else None
        if code is not None:
            if scanned is None:
                raise AppError("events.ticket_invalid", 422)
            registration_id = scanned.registration_id
        registration = await self.session.scalar(
            select(EventRegistration)
            .where(EventRegistration.id == registration_id)
            .with_for_update()
        )
        if registration is None:
            raise AppError("events.ticket_invalid", 422)
        # The signature covers the registration's own event: a forged or altered code fails here, and a genuine
        # ticket for another event is reported as such below.
        if scanned is not None and not tickets.is_genuine(secret, scanned, registration.event_id):
            raise AppError("events.ticket_invalid", 422)
        if registration.event_id != event_id:
            raise AppError("events.ticket_other_event", 409)
        event = await self._get(event_id)
        if event.status is EventStatus.CANCELLED:
            raise AppError("events.cancelled", 409)
        if registration.status is not RegistrationStatus.GOING:
            raise AppError("events.ticket_cancelled", 409)
        now = utc_now()
        if not event.starts_at - CHECK_IN_OPENS <= now <= event.ends_at:
            raise AppError("events.check_in_closed", 409)
        attendee = await self._attendee(registration)
        if registration.checked_in_at is not None:
            raise AppError(
                "events.already_checked_in",
                409,
                details={
                    "checked_in_at": registration.checked_in_at.isoformat(),
                    "name": attendee.name,
                },
            )
        registration.checked_in_at, registration.checked_in_by = now, staff_id
        registration.check_in_method = method
        if method is CheckInMethod.MANUAL:
            record_audit(
                self.session,
                AuditAction.EVENT_MANUAL_CHECK_IN,
                actor_id=staff_id,
                target_type="user",
                target_id=registration.user_id,
                details={"event_id": str(event.id)},
            )
        await self.session.commit()
        return attendee

    async def _attendee(self, registration: EventRegistration) -> Attendee:
        row = (
            await self.session.execute(
                select(User.display_name, AcademicGroup.code)
                .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
                .where(User.id == registration.user_id)
            )
        ).one()
        return Attendee(registration, row[0], row[1])

    # --- Everyone --------------------------------------------------------------------------------

    async def page(
        self,
        user_id: uuid.UUID,
        manager: bool,
        period: Period,
        registered_only: bool,
        cursor: str | None,
        limit: int,
    ) -> EventPage:
        now = utc_now()
        query = select(Event)
        if not manager:
            query = query.where(_visible(user_id))
        if registered_only:
            query = query.where(
                exists().where(
                    EventRegistration.event_id == Event.id,
                    EventRegistration.user_id == user_id,
                    EventRegistration.status == RegistrationStatus.GOING,
                )
            )
        key = tuple_(Event.starts_at, Event.id)
        if period is Period.UPCOMING:
            query = query.where(Event.ends_at > now).order_by(Event.starts_at, Event.id)
            if cursor:
                query = query.where(key > tuple_(*decode_cursor(cursor)))
        else:
            query = query.where(Event.ends_at <= now).order_by(
                Event.starts_at.desc(), Event.id.desc()
            )
            if cursor:
                query = query.where(key < tuple_(*decode_cursor(cursor)))
        events = list(await self.session.scalars(query.limit(limit + 1)))
        more = len(events) > limit
        views = await self._views(events[:limit], user_id)
        return EventPage(views, encode_cursor(views[-1].event) if more else None)

    async def view(self, event_id: uuid.UUID, user_id: uuid.UUID, manager: bool) -> EventView:
        query = select(Event).where(Event.id == event_id)
        if not manager:
            query = query.where(_visible(user_id))
        event = await self.session.scalar(query)
        if event is None:
            raise AppError("request.not_found", 404)
        return (await self._views([event], user_id))[0]

    async def my_tickets(self, user_id: uuid.UUID) -> list[EventView]:
        """Registrations for events that have not ended (cancelled events stay, marked, until then)."""
        events = list(
            await self.session.scalars(
                select(Event)
                .join(EventRegistration, EventRegistration.event_id == Event.id)
                .where(
                    EventRegistration.user_id == user_id,
                    EventRegistration.status == RegistrationStatus.GOING,
                    Event.ends_at > utc_now(),
                )
                .order_by(Event.starts_at, Event.id)
            )
        )
        return await self._views(events, user_id)

    async def _views(self, events: list[Event], user_id: uuid.UUID) -> list[EventView]:
        if not events:
            return []
        ids = [event.id for event in events]
        going = dict(
            (
                await self.session.execute(
                    select(EventRegistration.event_id, func.count())
                    .where(
                        EventRegistration.event_id.in_(ids),
                        EventRegistration.status == RegistrationStatus.GOING,
                    )
                    .group_by(EventRegistration.event_id)
                )
            ).all()
        )
        mine = {
            registration.event_id: registration
            for registration in await self.session.scalars(
                select(EventRegistration).where(
                    EventRegistration.event_id.in_(ids), EventRegistration.user_id == user_id
                )
            )
        }
        room_ids = {event.room_id for event in events if event.room_id}
        rooms = (
            {
                room.id: room
                for room in await self.session.scalars(select(Room).where(Room.id.in_(room_ids)))
            }
            if room_ids
            else {}
        )
        return [
            EventView(
                event,
                rooms.get(event.room_id) if event.room_id else None,
                going.get(event.id, 0),
                mine.get(event.id),
            )
            for event in events
        ]

    async def register(self, event_id: uuid.UUID, user_id: uuid.UUID) -> EventRegistration:
        """RSVP (idempotent). The event row is locked, so concurrent registrations cannot overbook it."""
        event = await self.session.scalar(
            select(Event).where(Event.id == event_id, _visible(user_id)).with_for_update()
        )
        if event is None:
            raise AppError("request.not_found", 404)
        registration = await self.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id, EventRegistration.user_id == user_id
            )
        )
        if registration is not None and registration.status is RegistrationStatus.GOING:
            return registration
        if event.status is EventStatus.CANCELLED:
            raise AppError("events.cancelled", 409)
        if utc_now() >= event.starts_at:
            raise AppError("events.registration_closed", 409)
        if event.capacity is not None and await self._going_count(event.id) >= event.capacity:
            raise AppError("events.full", 409)
        if registration is None:
            registration = EventRegistration(event_id=event_id, user_id=user_id)
            self.session.add(registration)
        else:
            registration.status = RegistrationStatus.GOING
        await self.session.commit()
        return registration

    async def unregister(self, event_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Withdraws the RSVP (idempotent); the ticket stops working."""
        event = await self.session.scalar(
            select(Event).where(Event.id == event_id, _visible(user_id))
        )
        if event is None:
            raise AppError("request.not_found", 404)
        registration = await self.session.scalar(
            select(EventRegistration)
            .where(EventRegistration.event_id == event_id, EventRegistration.user_id == user_id)
            .with_for_update()
        )
        if registration is None or registration.status is RegistrationStatus.CANCELLED:
            return
        if registration.checked_in_at is not None:
            raise AppError("events.already_checked_in", 409)
        if utc_now() >= event.starts_at:
            raise AppError("events.registration_closed", 409)
        registration.status = RegistrationStatus.CANCELLED
        await self.session.commit()

    # --- Helpers ---------------------------------------------------------------------------------

    async def _going_count(self, event_id: uuid.UUID) -> int:
        count = await self.session.scalar(
            select(func.count()).select_from(_going(event_id).subquery())
        )
        return count or 0

    async def _get(self, event_id: uuid.UUID) -> Event:
        event = await self.session.get(Event, event_id)
        if event is None:
            raise AppError("request.not_found", 404)
        return event

    async def _locked(self, event_id: uuid.UUID) -> Event:
        event = await self.session.scalar(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        if event is None:
            raise AppError("request.not_found", 404)
        return event

    def _audit(
        self,
        action: AuditAction,
        actor_id: uuid.UUID,
        event: Event,
        details: dict[str, str] | None = None,
    ) -> None:
        record_audit(
            self.session,
            action,
            actor_id=actor_id,
            target_type=SUBJECT_TYPE,
            target_id=event.id,
            details=details,
        )


async def still_relevant(session: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Delivery-time check (§5.6). A cancellation still reaches people who registered; anything else only
    while the event has not ended and the user registered or still belongs to its audience."""
    event = await session.get(Event, event_id)
    if event is None:
        return False
    registered = bool(
        await session.scalar(
            select(
                exists().where(
                    EventRegistration.event_id == event_id,
                    EventRegistration.user_id == user_id,
                    EventRegistration.status == RegistrationStatus.GOING,
                )
            )
        )
    )
    if event.status is EventStatus.CANCELLED:
        return registered
    if event.ends_at <= utc_now():
        return False
    return registered or bool(await session.scalar(is_member(event.audience, user_id)))


def has_ticket(registration: EventRegistration | None, event: Event) -> bool:
    return (
        registration is not None
        and registration.status is RegistrationStatus.GOING
        and event.status is EventStatus.PUBLISHED
    )
