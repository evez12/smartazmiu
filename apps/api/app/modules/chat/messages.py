"""Sending, history and read markers, shared by the REST fallback and the WebSocket gateway (§5.9)."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.chat.access import ChannelAccess
from app.modules.chat.bus import ChatBus, channel_topic, user_topic
from app.modules.chat.models import ChannelRead, ChannelTopic, Message, MessageClientId
from app.modules.chat.policy import Action, Decision, Reason
from app.modules.chat.schemas import AuthorOut, MessageOut
from app.modules.chat.search import body_vector
from app.modules.chat.snowflake import Snowflake, SnowflakeUnavailableError, created_at_of
from app.modules.users.models import User
from app.modules.users.profile import photo_url
from app.modules.users.service import CurrentUser

logger = structlog.get_logger(__name__)

MAX_BODY_LENGTH = 4000
PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
# Reconnect backfill stays well inside the seven days the duplicate-send keys are kept (D-058).
BACKFILL_WINDOW = timedelta(days=3)
BACKFILL_LIMIT = 1000


def deny(decision: Decision) -> AppError:
    """The REST form of a refusal; non-members get the same 404 as a channel that does not exist (§14)."""
    reason = decision.reason
    if reason is Reason.NOT_MEMBER or reason is None:
        return AppError("chat.channel_not_found", 404)
    details: dict[str, object] = {}
    headers = None
    if decision.until is not None:
        details["until"] = decision.until.isoformat()
    if decision.retry_after is not None:
        details["retry_after_seconds"] = decision.retry_after
        headers = {"Retry-After": str(decision.retry_after)}
    status = 429 if reason in (Reason.RATE_LIMITED, Reason.SLOW_MODE) else 403
    return AppError(reason.value, status, details=details, headers=headers)


def message_out(message: Message, author: User | None) -> MessageOut:
    return MessageOut(
        id=str(message.id),
        channel_id=str(message.channel_id),
        topic_id=str(message.topic_id) if message.topic_id else None,
        parent_id=str(message.parent_id) if message.parent_id else None,
        author=AuthorOut(
            id=str(author.id), display_name=author.display_name, photo_url=photo_url(author)
        )
        if author is not None
        else None,
        body="" if message.deleted_at else message.body,
        client_msg_id=str(message.client_msg_id),
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
    )


def _with_authors() -> Select[Message, User]:
    return select(Message, User).outerjoin(User, User.id == Message.author_id)


@dataclass(frozen=True, slots=True)
class SendOutcome:
    message: MessageOut
    created: bool
    """False when the client id had been used before and the original message was returned."""


@dataclass(frozen=True, slots=True)
class Page:
    messages: list[MessageOut]
    has_more: bool


class MessageService:
    def __init__(
        self, session: AsyncSession, access: ChannelAccess, snowflake: Snowflake, bus: ChatBus
    ) -> None:
        self.session = session
        self.access = access
        self.snowflake = snowflake
        self.bus = bus

    async def send(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        body: str,
        client_msg_id: uuid.UUID,
        topic_id: uuid.UUID | None = None,
    ) -> SendOutcome:
        """Persists the message, then publishes it; a retried client id returns the original (§13.2)."""
        if not body.strip():
            raise AppError("chat.message_empty", 422)
        if len(body) > MAX_BODY_LENGTH:
            raise AppError("chat.message_too_long", 422, details={"max_length": MAX_BODY_LENGTH})
        earlier = await self._sent_before(user, channel_id, client_msg_id)
        if earlier is not None:
            return SendOutcome(earlier, created=False)

        decision = await self.access.claim_send(user, channel_id)
        if not decision.allowed:
            raise deny(decision)
        if topic_id is not None and not await self._topic_in_channel(topic_id, channel_id):
            raise AppError("chat.topic_not_found", 422)

        for attempt in range(2):
            try:
                message_id = await self.snowflake.next_id()
            except SnowflakeUnavailableError as exc:
                logger.warning("message_id_unavailable", reason=str(exc))
                raise AppError("chat.unavailable", 503) from exc
            try:
                created = await self._insert(
                    user, channel_id, message_id, body, client_msg_id, topic_id
                )
            except IntegrityError:
                # A duplicate snowflake is the primary key's to catch; one retry with a fresh id (ADR 0002).
                await self.session.rollback()
                if attempt:
                    raise
                continue
            break
        if not created:
            again = await self._sent_before(user, channel_id, client_msg_id)
            assert again is not None
            return SendOutcome(again, created=False)

        message = await self.message(channel_id, message_id)
        assert message is not None
        await self.bus.publish(
            channel_topic(channel_id), "message.created", message.model_dump(mode="json")
        )
        return SendOutcome(message, created=True)

    async def _insert(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        message_id: int,
        body: str,
        client_msg_id: uuid.UUID,
        topic_id: uuid.UUID | None,
    ) -> bool:
        """One transaction: claim the client id, insert the message. False if a concurrent send won the claim."""
        created_at = created_at_of(message_id)
        # A concurrent send of the same client id waits here on the first one's uncommitted key (D-058).
        claimed = await self.session.scalar(
            insert(MessageClientId)
            .values(
                channel_id=channel_id,
                client_msg_id=client_msg_id,
                message_id=message_id,
                message_created_at=created_at,
            )
            .on_conflict_do_nothing(index_elements=["channel_id", "client_msg_id"])
            .returning(MessageClientId.message_id)
        )
        if claimed is None:
            await self.session.rollback()
            return False
        try:
            await self.session.execute(
                insert(Message).values(
                    id=message_id,
                    created_at=created_at,
                    channel_id=channel_id,
                    topic_id=topic_id,
                    author_id=user.id,
                    body=body,
                    body_tsv=body_vector(body),
                    client_msg_id=client_msg_id,
                )
            )
            await self.session.commit()
        except DBAPIError as exc:
            if "no partition" not in str(exc.orig):
                raise  # a duplicate id is an IntegrityError the caller retries with a fresh one
            await self.session.rollback()
            # The partition job has not run for this month; reads continue (ADR 0002).
            logger.error("message_partition_missing", month=created_at.strftime("%Y-%m"))
            raise AppError("chat.unavailable", 503) from exc
        return True

    async def _sent_before(
        self, user: CurrentUser, channel_id: uuid.UUID, client_msg_id: uuid.UUID
    ) -> MessageOut | None:
        key = await self.session.scalar(
            select(MessageClientId).where(
                MessageClientId.channel_id == channel_id,
                MessageClientId.client_msg_id == client_msg_id,
            )
        )
        if key is None:
            return None
        if not (await self.access.state(user, channel_id)).is_member:
            raise AppError("chat.channel_not_found", 404)
        found = await self.session.execute(
            _with_authors().where(
                Message.id == key.message_id, Message.created_at == key.message_created_at
            )
        )
        row = found.first()
        if row is None or row[0].author_id != user.id:
            # Someone else's client id: never hand out their message.
            raise AppError("chat.duplicate_client_id", 409)
        return message_out(row[0], row[1])

    async def _topic_in_channel(self, topic_id: uuid.UUID, channel_id: uuid.UUID) -> bool:
        found = await self.session.scalar(
            select(ChannelTopic.id).where(
                ChannelTopic.id == topic_id, ChannelTopic.channel_id == channel_id
            )
        )
        return found is not None

    async def message(self, channel_id: uuid.UUID, message_id: int) -> MessageOut | None:
        found = await self.session.execute(
            _with_authors().where(
                Message.channel_id == channel_id,
                Message.id == message_id,
                # The id fixes the partition (ADR 0002).
                Message.created_at == created_at_of(message_id),
            )
        )
        row = found.first()
        return message_out(row[0], row[1]) if row else None

    async def history(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        *,
        before: int | None = None,
        after: int | None = None,
        topic_id: uuid.UUID | None = None,
        limit: int = PAGE_SIZE,
    ) -> Page:
        """Oldest first. ``before`` pages back from a message, ``after`` forward; neither gives the latest."""
        if not (await self.access.decide(user, channel_id, Action.READ)).allowed:
            raise AppError("chat.channel_not_found", 404)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        return await self._page(
            channel_id, before=before, after=after, topic_id=topic_id, limit=limit
        )

    async def backfill(self, channel_id: uuid.UUID, after: int) -> Page:
        """What a reconnecting client missed; ``has_more`` means the gap is too large to replay (§13.2)."""
        if created_at_of(after) < utc_now() - BACKFILL_WINDOW:
            return Page([], has_more=True)
        return await self._page(channel_id, after=after, limit=BACKFILL_LIMIT)

    async def _page(
        self,
        channel_id: uuid.UUID,
        *,
        before: int | None = None,
        after: int | None = None,
        topic_id: uuid.UUID | None = None,
        limit: int,
    ) -> Page:
        query = _with_authors().where(Message.channel_id == channel_id)
        if topic_id is not None:
            query = query.where(Message.topic_id == topic_id)
        # Bounds on created_at derived from the cursor let the planner skip other months (ADR 0002).
        if before is not None:
            query = query.where(Message.id < before, Message.created_at <= created_at_of(before))
        if after is not None:
            query = query.where(Message.id > after, Message.created_at >= created_at_of(after))
        ascending = after is not None and before is None
        query = query.order_by(Message.id.asc() if ascending else Message.id.desc()).limit(
            limit + 1
        )
        rows = list(await self.session.execute(query))
        has_more = len(rows) > limit
        rows = rows[:limit]
        if not ascending:
            rows.reverse()
        return Page([message_out(message, author) for message, author in rows], has_more)

    async def mark_read(self, user: CurrentUser, channel_id: uuid.UUID, message_id: int) -> int:
        """Moves the read marker forward only (D-002) and tells the user's other tabs (§13.2)."""
        if not (await self.access.decide(user, channel_id, Action.READ)).allowed:
            raise AppError("chat.channel_not_found", 404)
        latest = await self.session.scalar(
            select(func.max(Message.id)).where(Message.channel_id == channel_id)
        )
        statement = insert(ChannelRead).values(
            channel_id=channel_id,
            user_id=user.id,
            last_read_message_id=min(message_id, latest or 0),
        )
        stored = await self.session.scalar(
            statement.on_conflict_do_update(
                index_elements=["channel_id", "user_id"],
                set_={
                    "last_read_message_id": func.greatest(
                        ChannelRead.last_read_message_id, statement.excluded.last_read_message_id
                    ),
                    "updated_at": func.now(),
                },
            ).returning(ChannelRead.last_read_message_id)
        )
        await self.session.commit()
        marker = int(stored or 0)
        await self.bus.publish(
            user_topic(user.id),
            "read.updated",
            {"channel_id": str(channel_id), "last_read_message_id": str(marker)},
        )
        return marker
