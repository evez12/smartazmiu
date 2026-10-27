"""Knowledge in channels (§5.3, Sprint 9): pins and the "Faydalı" collection, polls, saved messages, verified
answers and the moderator view of anonymous questions. Every action goes through the channel policy first, so a
non-member gets the same 404 as for a message that does not exist (ADR 0004)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.academics.models import CourseOfferingTeacher
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.access import ChannelAccess, deny
from app.modules.chat.bus import ChatBus, channel_topic
from app.modules.chat.lookup import find_message
from app.modules.chat.mentions import SUBJECT_TYPE, subject_id
from app.modules.chat.models import (
    Channel,
    ChannelType,
    Message,
    PinnedMessage,
    Poll,
    PollOption,
    PollVote,
    SavedMessage,
)
from app.modules.chat.payloads import enrich, message_payload, with_authors
from app.modules.chat.policy import Action
from app.modules.chat.schemas import AuthorOut, MessageOut
from app.modules.mentorship.models import MentorProfile
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.users.models import User
from app.modules.users.profile import photo_url
from app.modules.users.service import CurrentUser

MAX_PINS = 50
MAX_OPTIONS = 10
STAFF_ROLES = frozenset({"staff", "admin"})


def validate_poll(options: list[str], closes_at: datetime | None) -> list[str]:
    """Checked before the question is sent, so a refused poll leaves no message behind."""
    cleaned = [option.strip() for option in options]
    if (
        len(cleaned) < 2
        or len(cleaned) > MAX_OPTIONS
        or any(not option or len(option) > 200 for option in cleaned)
        or len(set(cleaned)) != len(cleaned)
    ):
        raise AppError("chat.poll_invalid_options", 422, details={"max": MAX_OPTIONS})
    if closes_at is not None and closes_at <= utc_now():
        raise AppError("chat.poll_invalid_deadline", 422)
    return cleaned


@dataclass(frozen=True, slots=True)
class Capabilities:
    can_pin: bool
    can_verify: bool
    can_see_anonymous: bool


@dataclass(frozen=True, slots=True)
class SavedItem:
    message_id: int
    channel_id: uuid.UUID
    channel_name: str | None
    saved_at: datetime
    message: MessageOut | None
    """None once the message was deleted or the person lost access to its channel."""


class CurationService:
    def __init__(self, session: AsyncSession, access: ChannelAccess, bus: ChatBus) -> None:
        self.session = session
        self.access = access
        self.bus = bus

    # --- capabilities --------------------------------------------------------------------------------------

    async def capabilities(self, user: CurrentUser, channel_id: uuid.UUID) -> Capabilities:
        state = await self.access.state(user, channel_id)
        if not state.is_member:
            return Capabilities(False, False, False)
        channel = await self.session.get(Channel, channel_id)
        assert channel is not None
        staff = bool(user.roles & STAFF_ROLES)
        moderates = state.privileged or staff
        return Capabilities(
            # In a DM both people curate their own conversation.
            can_pin=moderates or channel.type is ChannelType.DM,
            can_verify=await self._verifier(user.id, channel),
            can_see_anonymous=moderates,
        )

    async def _verifier(self, user_id: uuid.UUID, channel: Channel) -> bool:
        """Teachers of the offering in a course channel, guides of the subject in its community (§5.3)."""
        if channel.type is ChannelType.COURSE_OFFERING and channel.course_offering_id:
            return bool(
                await self.session.scalar(
                    select(
                        exists().where(
                            CourseOfferingTeacher.course_offering_id == channel.course_offering_id,
                            CourseOfferingTeacher.teacher_id == user_id,
                        )
                    )
                )
            )
        if channel.type is ChannelType.SUBJECT_COMMUNITY and channel.subject_id:
            return bool(
                await self.session.scalar(
                    select(
                        exists().where(
                            MentorProfile.user_id == user_id,
                            MentorProfile.subject_id == channel.subject_id,
                            MentorProfile.revoked_at.is_(None),
                        )
                    )
                )
            )
        return False

    async def _readable(self, user: CurrentUser, message_id: int, *, lock: bool = False) -> Message:
        message = await find_message(self.session, message_id, lock=lock)
        if message is None or message.deleted_at is not None:
            raise AppError("chat.message_not_found", 404)
        if not (await self.access.decide(user, message.channel_id, Action.READ)).allowed:
            raise AppError("chat.message_not_found", 404)
        return message

    async def _broadcast(self, message: Message) -> None:
        payload = await message_payload(self.session, message.id, None)
        if payload is not None:
            await self.bus.publish(
                channel_topic(message.channel_id),
                "message.updated",
                payload.model_dump(mode="json"),
            )

    async def _own(self, message: Message, viewer: uuid.UUID) -> MessageOut:
        payload = await message_payload(self.session, message.id, viewer)
        assert payload is not None
        return payload

    # --- pins ------------------------------------------------------------------------------------------------

    async def pin(self, user: CurrentUser, channel_id: uuid.UUID, message_id: int) -> MessageOut:
        message = await self._readable(user, message_id)
        if message.channel_id != channel_id:
            raise AppError("chat.message_not_found", 404)
        if not (await self.capabilities(user, channel_id)).can_pin:
            raise AppError("chat.pin_not_allowed", 403)
        # The channel row serialises pins, so two at the limit cannot both pass the count.
        await self.session.execute(
            select(Channel.id).where(Channel.id == channel_id).with_for_update()
        )
        count = await self.session.scalar(
            select(func.count()).where(PinnedMessage.channel_id == channel_id)
        )
        already = await self.session.get(PinnedMessage, (channel_id, message_id))
        if already is None:
            if (count or 0) >= MAX_PINS:
                raise AppError("chat.pin_limit", 409, details={"max": MAX_PINS})
            self.session.add(
                PinnedMessage(channel_id=channel_id, message_id=message_id, pinned_by=user.id)
            )
        await self.session.commit()
        await self._broadcast(message)
        return await self._own(message, user.id)

    async def unpin(self, user: CurrentUser, channel_id: uuid.UUID, message_id: int) -> None:
        if not (await self.access.decide(user, channel_id, Action.READ)).allowed:
            raise AppError("chat.channel_not_found", 404)
        if not (await self.capabilities(user, channel_id)).can_pin:
            raise AppError("chat.pin_not_allowed", 403)
        await self.session.execute(
            delete(PinnedMessage).where(
                PinnedMessage.channel_id == channel_id, PinnedMessage.message_id == message_id
            )
        )
        await self.session.commit()
        message = await find_message(self.session, message_id)
        if message is not None:
            await self._broadcast(message)

    async def pins(self, user: CurrentUser, channel_id: uuid.UUID) -> list[MessageOut]:
        """The "Faydalı" collection: pinned messages that still exist, newest pin first."""
        if not (await self.access.decide(user, channel_id, Action.READ)).allowed:
            raise AppError("chat.channel_not_found", 404)
        pinned = list(
            await self.session.scalars(
                select(PinnedMessage.message_id)
                .where(PinnedMessage.channel_id == channel_id)
                .order_by(PinnedMessage.pinned_at.desc())
                .limit(MAX_PINS)
            )
        )
        if not pinned:
            return []
        rows = list(
            await self.session.execute(
                with_authors().where(
                    Message.channel_id == channel_id,
                    Message.id.in_(pinned),
                    Message.deleted_at.is_(None),
                )
            )
        )
        order = {message_id: index for index, message_id in enumerate(pinned)}
        payloads = await enrich(self.session, [tuple(row) for row in rows], user.id)  # type: ignore[misc]
        return sorted(payloads, key=lambda out: order[int(out.id)])

    # --- polls -----------------------------------------------------------------------------------------------

    async def attach_poll(
        self,
        user: CurrentUser,
        message: MessageOut,
        options: list[str],
        multi: bool,
        closes_at: datetime | None,
    ) -> MessageOut:
        """Turns a just-sent message into a poll; the message itself went through the posting policy."""
        cleaned = validate_poll(options, closes_at)
        message_id = int(message.id)
        poll = Poll(
            message_id=message_id,
            channel_id=uuid.UUID(message.channel_id),
            multi=multi,
            closes_at=closes_at,
        )
        self.session.add(poll)
        await self.session.flush()
        self.session.add_all(
            PollOption(poll_id=poll.id, text=text, position=index)
            for index, text in enumerate(cleaned)
        )
        await self.session.commit()
        stored = await find_message(self.session, message_id)
        assert stored is not None
        await self._broadcast(stored)
        return await self._own(stored, user.id)

    async def vote(
        self, user: CurrentUser, poll_id: uuid.UUID, option_ids: list[uuid.UUID]
    ) -> MessageOut:
        poll = await self.session.scalar(select(Poll).where(Poll.id == poll_id).with_for_update())
        if poll is None:
            raise AppError("chat.poll_not_found", 404)
        decision = await self.access.decide(user, poll.channel_id, Action.SEND)
        if not decision.allowed:
            if not (await self.access.decide(user, poll.channel_id, Action.READ)).allowed:
                raise AppError("chat.poll_not_found", 404)
            raise deny(decision)
        if poll.closes_at is not None and poll.closes_at <= utc_now():
            raise AppError("chat.poll_closed", 409)
        chosen = list(dict.fromkeys(option_ids))
        valid = set(
            await self.session.scalars(select(PollOption.id).where(PollOption.poll_id == poll.id))
        )
        if not chosen or not set(chosen) <= valid or (not poll.multi and len(chosen) != 1):
            raise AppError("chat.poll_invalid_vote", 422)
        # Replacing the person's votes inside the poll's row lock keeps counts exact under concurrent votes.
        await self.session.execute(
            delete(PollVote).where(PollVote.poll_id == poll.id, PollVote.user_id == user.id)
        )
        await self.session.execute(
            insert(PollVote).values(
                [{"poll_id": poll.id, "option_id": option, "user_id": user.id} for option in chosen]
            )
        )
        await self.session.commit()
        message = await find_message(self.session, poll.message_id)
        assert message is not None
        await self._broadcast(message)
        return await self._own(message, user.id)

    # --- saved messages --------------------------------------------------------------------------------------

    async def save(self, user: CurrentUser, message_id: int, saved: bool) -> MessageOut | None:
        if saved:
            message = await self._readable(user, message_id)
            await self.session.execute(
                insert(SavedMessage)
                .values(user_id=user.id, message_id=message_id, channel_id=message.channel_id)
                .on_conflict_do_nothing()
            )
            await self.session.commit()
            return await self._own(message, user.id)
        await self.session.execute(
            delete(SavedMessage).where(
                SavedMessage.user_id == user.id, SavedMessage.message_id == message_id
            )
        )
        await self.session.commit()
        return None

    async def saved(self, user: CurrentUser) -> list[SavedItem]:
        """Only the person's own list. A message they can no longer read, or that was deleted, is listed as
        unavailable without its content or channel name (§5.4)."""
        rows = list(
            await self.session.execute(
                select(SavedMessage, Channel.name)
                .join(Channel, Channel.id == SavedMessage.channel_id)
                .where(SavedMessage.user_id == user.id)
                .order_by(SavedMessage.created_at.desc())
                .limit(200)
            )
        )
        states = await self.access.states(user, list({row[0].channel_id for row in rows}))
        items = []
        for saved, channel_name in rows:
            state = states.get(saved.channel_id)
            readable = state is not None and state.is_member
            payload = (
                await message_payload(self.session, saved.message_id, user.id) if readable else None
            )
            available = payload is not None and payload.deleted_at is None
            items.append(
                SavedItem(
                    message_id=saved.message_id,
                    channel_id=saved.channel_id,
                    channel_name=channel_name if available else None,
                    saved_at=saved.created_at,
                    message=payload if available else None,
                )
            )
        return items

    # --- verified answers ------------------------------------------------------------------------------------

    async def verify(self, user: CurrentUser, message_id: int, verified: bool) -> MessageOut:
        message = await self._readable(user, message_id, lock=True)
        channel = await self.session.get(Channel, message.channel_id)
        assert channel is not None
        if not await self._verifier(user.id, channel):
            raise AppError("chat.verify_not_allowed", 403)
        if message.parent_id is None:
            # A verified answer answers something: it is a reply in a question's thread.
            raise AppError("chat.verify_needs_reply", 422)
        await self.session.execute(
            update(Message)
            .where(Message.id == message.id, Message.created_at == message.created_at)
            .values(is_verified_answer=verified, verified_by=user.id if verified else None)
            .execution_options(synchronize_session=False)
        )
        root = await find_message(self.session, message.parent_id)
        if verified and root is not None and root.author_id and root.author_id != user.id:
            await Notifier(self.session).notify(
                select(User.id).where(User.id == root.author_id),
                NotificationSpec(
                    category=NotificationCategory.CHAT,
                    kind=NotificationKind.CHAT_ANSWER_VERIFIED,
                    subject_type=SUBJECT_TYPE,
                    subject_id=subject_id(message.id),
                    dedupe_key=f"chat.verified:{message.id}",
                    title=channel.name,
                    link=f"/chat/{channel.id}?thread={root.id}",
                ),
            )
        await self.session.commit()
        await self.session.refresh(message)
        await self._broadcast(message)
        return await self._own(message, user.id)

    # --- anonymous questions ---------------------------------------------------------------------------------

    async def anonymous_author(self, user: CurrentUser, message_id: int) -> AuthorOut:
        """The real author of an anonymous question, for the channel's moderators and staff; every look is
        audited (§5.3)."""
        message = await self._readable(user, message_id)
        if not message.is_anonymous:
            raise AppError("chat.message_not_found", 404)
        if not (await self.capabilities(user, message.channel_id)).can_see_anonymous:
            raise AppError("chat.anonymous_author_hidden", 403)
        author = await self.session.get(User, message.author_id) if message.author_id else None
        if author is None:
            raise AppError("chat.user_not_found", 404)
        record_audit(
            self.session,
            AuditAction.MESSAGE_AUTHOR_REVEALED,
            actor_id=user.id,
            target_type="message",
            target_id=str(message.id),
        )
        await self.session.commit()
        return AuthorOut(
            id=str(author.id), display_name=author.display_name, photo_url=photo_url(author)
        )
