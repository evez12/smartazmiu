"""Sending, editing, deleting, history, threads and read markers, shared by the REST endpoints and the WebSocket
gateway (§5.9): both call the same methods, so both get the same authorisation (ADR 0004)."""

import re
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.jobs import JobQueue
from app.core.time import utc_now
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.access import ChannelAccess, deny
from app.modules.chat.attachments import AttachmentService
from app.modules.chat.blocked_terms import BlockedTermService
from app.modules.chat.bus import ChatBus, channel_topic, user_topic
from app.modules.chat.lookup import find_message
from app.modules.chat.mentions import MentionService, ParsedMentions, parse
from app.modules.chat.models import (
    BlockedTermAction,
    Channel,
    ChannelRead,
    ChannelTopic,
    ChannelType,
    Message,
    MessageClientId,
    MessageModeration,
    ThreadLock,
)
from app.modules.chat.payloads import enrich, message_payload, with_authors
from app.modules.chat.policy import Action, Reason
from app.modules.chat.schemas import MessageOut, Notice
from app.modules.chat.search import body_vector
from app.modules.chat.snowflake import Snowflake, SnowflakeUnavailableError, created_at_of
from app.modules.users.service import CurrentUser

ANONYMOUS_TOPIC = "suallar"

logger = structlog.get_logger(__name__)

MAX_BODY_LENGTH = 4000
PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
# Reconnect backfill stays well inside the seven days the duplicate-send keys are kept (D-058).
BACKFILL_WINDOW = timedelta(days=3)
BACKFILL_LIMIT = 1000
# The author may edit or delete a message for 15 minutes (§5.3, §13.2).
CHANGE_WINDOW = timedelta(minutes=15)
URL_PATTERN = re.compile(r"https?://[^\s<]+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SendOutcome:
    message: MessageOut
    created: bool
    """False when the client id had been used before and the original message was returned."""
    notices: list[Notice] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Page:
    messages: list[MessageOut]
    has_more: bool


@dataclass(frozen=True, slots=True)
class Thread:
    root: MessageOut
    replies: list[MessageOut]
    has_more: bool


def _check_body(body: str, *, attachments: bool = False) -> None:
    # A message may consist of attachments only.
    if not body.strip() and not attachments:
        raise AppError("chat.message_empty", 422)
    if len(body) > MAX_BODY_LENGTH:
        raise AppError("chat.message_too_long", 422, details={"max_length": MAX_BODY_LENGTH})


class MessageService:
    def __init__(
        self,
        session: AsyncSession,
        access: ChannelAccess,
        snowflake: Snowflake,
        bus: ChatBus,
        attachments: AttachmentService | None = None,
        jobs: JobQueue | None = None,
    ) -> None:
        self.session = session
        self.access = access
        self.snowflake = snowflake
        self.bus = bus
        self.attachments = attachments
        self.jobs = jobs

    async def send(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        body: str,
        client_msg_id: uuid.UUID,
        topic_id: uuid.UUID | None = None,
        parent_id: int | None = None,
        attachment_ids: list[uuid.UUID] | None = None,
        is_anonymous: bool = False,
    ) -> SendOutcome:
        """Persists the message, then publishes it; a retried client id returns the original (§13.2)."""
        attachment_ids = list(dict.fromkeys(attachment_ids or []))
        _check_body(body, attachments=bool(attachment_ids))
        earlier = await self._sent_before(user, channel_id, client_msg_id)
        if earlier is not None:
            return SendOutcome(earlier, created=False)

        if attachment_ids:
            if self.attachments is None:
                raise AppError("chat.attachments_unavailable", 503)
            attaching = await self.access.decide(user, channel_id, Action.SEND_ATTACHMENT)
            if not attaching.allowed:
                raise deny(attaching)
        if URL_PATTERN.search(body):
            linking = await self.access.decide(user, channel_id, Action.SEND_LINK)
            if not linking.allowed:
                raise deny(linking)
        decision = await self.access.claim_send(user, channel_id)
        if not decision.allowed:
            raise deny(decision)
        if topic_id is not None and not await self._topic_in_channel(topic_id, channel_id):
            raise AppError("chat.topic_not_found", 422)
        parent = await self._thread_root(channel_id, parent_id) if parent_id else None
        if is_anonymous:
            await self._check_anonymous(channel_id, topic_id, parent)
        parsed, notices = await self._mentions(user, channel_id, body)
        term_action = await BlockedTermService(self.session).check(body)
        if term_action is BlockedTermAction.REJECT:
            raise AppError("chat.message_blocked", 422)
        moderation = (
            MessageModeration.HELD
            if term_action is BlockedTermAction.HOLD
            else MessageModeration.VISIBLE
        )
        if is_anonymous:
            # Mentions would notify people in the author's name, so an anonymous question names nobody.
            parsed = ParsedMentions([], False)

        for attempt in range(2):
            try:
                message_id = await self.snowflake.next_id()
            except SnowflakeUnavailableError as exc:
                logger.warning("message_id_unavailable", reason=str(exc))
                raise AppError("chat.unavailable", 503) from exc
            try:
                created = await self._insert(
                    user,
                    channel_id,
                    message_id,
                    body,
                    client_msg_id,
                    topic_id,
                    parent,
                    parsed,
                    attachment_ids,
                    is_anonymous,
                    moderation,
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

        message = await self.message(channel_id, message_id, user.id)
        assert message is not None
        await self.bus.publish(
            user_topic(user.id)
            if moderation is MessageModeration.HELD
            else channel_topic(channel_id),
            "message.created",
            message.model_dump(mode="json"),
        )
        if attachment_ids:
            # The author's tabs also show the files being scanned, which nobody else sees yet (D-068).
            own = await self.message(channel_id, message_id, user.id)
            assert own is not None
            await self.bus.publish(
                user_topic(user.id), "message.updated", own.model_dump(mode="json")
            )
            if self.jobs is not None:
                await self.jobs.scan_attachments()
            return SendOutcome(own, created=True, notices=notices)
        return SendOutcome(message, created=True, notices=notices)

    async def _mentions(
        self, user: CurrentUser, channel_id: uuid.UUID, body: str
    ) -> tuple[ParsedMentions, list[Notice]]:
        """@channel from someone not allowed to use it is ignored and the author told (§13.2)."""
        parsed = parse(body)
        if not parsed.channel:
            return parsed, []
        if (await self.access.decide(user, channel_id, Action.MENTION_CHANNEL)).allowed:
            return parsed, []
        return ParsedMentions(parsed.user_ids, channel=False), [
            Reason.CHANNEL_MENTION_NOT_ALLOWED.value
        ]

    async def _thread_root(self, channel_id: uuid.UUID, parent_id: int) -> Message:
        """Threads are one level deep: a reply to a reply joins the root's thread (D-067)."""
        parent = await find_message(self.session, parent_id)
        if parent is not None and parent.parent_id is not None:
            parent = await find_message(self.session, parent.parent_id)
        if parent is None or parent.channel_id != channel_id or parent.deleted_at is not None:
            raise AppError("chat.parent_not_found", 422)
        if await self.session.get(ThreadLock, parent.id) is not None:
            raise AppError("chat.thread_locked", 403)
        return parent

    async def _insert(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        message_id: int,
        body: str,
        client_msg_id: uuid.UUID,
        topic_id: uuid.UUID | None,
        parent: Message | None,
        parsed: ParsedMentions,
        attachment_ids: list[uuid.UUID],
        is_anonymous: bool = False,
        moderation: MessageModeration = MessageModeration.VISIBLE,
    ) -> bool:
        """One transaction: claim the client id, insert the message and its mentions, create the notifications.
        False if a concurrent send won the claim."""
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
            message = Message(
                id=message_id,
                created_at=created_at,
                channel_id=channel_id,
                topic_id=parent.topic_id if parent is not None else topic_id,
                author_id=user.id,
                parent_id=parent.id if parent is not None else None,
                body=body,
                client_msg_id=client_msg_id,
                mentions_channel=parsed.channel,
            )
            await self.session.execute(
                insert(Message).values(
                    id=message.id,
                    created_at=message.created_at,
                    channel_id=message.channel_id,
                    topic_id=message.topic_id,
                    author_id=message.author_id,
                    parent_id=message.parent_id,
                    body=message.body,
                    body_tsv=body_vector(body) if moderation is MessageModeration.VISIBLE else None,
                    moderation=moderation,
                    client_msg_id=message.client_msg_id,
                    mentions_channel=message.mentions_channel,
                    is_anonymous=is_anonymous,
                )
            )
            if is_anonymous:
                # The real author stays known to the server and in the audit log (§5.3, D-084).
                record_audit(
                    self.session,
                    AuditAction.MESSAGE_ANONYMOUS_POSTED,
                    actor_id=user.id,
                    target_type="message",
                    target_id=str(message_id),
                    details={"channel_id": str(channel_id)},
                )
            if attachment_ids:
                assert self.attachments is not None
                try:
                    await self.attachments.claim(user, channel_id, attachment_ids, message_id)
                except AppError:
                    await self.session.rollback()
                    raise
            mentions = MentionService(self.session)
            mentioned = await mentions.record(message, parsed)
            if moderation is MessageModeration.VISIBLE:
                await mentions.notify(
                    message,
                    user,
                    mentioned=mentioned,
                    channel_wide=parsed.channel,
                    reply_to=parent.author_id if parent is not None else None,
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
            with_authors().where(
                Message.id == key.message_id, Message.created_at == key.message_created_at
            )
        )
        row = found.first()
        if row is None or row[0].author_id != user.id:
            # Someone else's client id: never hand out their message.
            raise AppError("chat.duplicate_client_id", 409)
        return (await enrich(self.session, [(row[0], row[1], row[2])], user.id))[0]

    async def _check_anonymous(
        self, channel_id: uuid.UUID, topic_id: uuid.UUID | None, parent: Message | None
    ) -> None:
        """Anonymous questions only as new posts in #suallar of a course or community channel (§5.3)."""
        allowed = (
            parent is None
            and topic_id is not None
            and await self.session.scalar(
                select(ChannelTopic.id)
                .join(Channel, Channel.id == ChannelTopic.channel_id)
                .where(
                    ChannelTopic.id == topic_id,
                    ChannelTopic.channel_id == channel_id,
                    ChannelTopic.slug == ANONYMOUS_TOPIC,
                    Channel.type.in_([ChannelType.COURSE_OFFERING, ChannelType.SUBJECT_COMMUNITY]),
                )
            )
            is not None
        )
        if not allowed:
            raise AppError("chat.anonymous_not_allowed", 422)

    async def _topic_in_channel(self, topic_id: uuid.UUID, channel_id: uuid.UUID) -> bool:
        found = await self.session.scalar(
            select(ChannelTopic.id).where(
                ChannelTopic.id == topic_id, ChannelTopic.channel_id == channel_id
            )
        )
        return found is not None

    async def message(
        self, channel_id: uuid.UUID, message_id: int, viewer: uuid.UUID | None = None
    ) -> MessageOut | None:
        out = await message_payload(self.session, message_id, viewer)
        return out if out is not None and out.channel_id == str(channel_id) else None

    async def _own_message(self, user: CurrentUser, message_id: int, action: Action) -> Message:
        """The user's own message, if the policy and the 15-minute window allow ``action`` (§13.2)."""
        message = await find_message(self.session, message_id, lock=True)
        if message is None or message.deleted_at is not None:
            raise AppError("chat.message_not_found", 404)
        decision = await self.access.decide(user, message.channel_id, action)
        if not decision.allowed:
            raise deny(decision, missing="chat.message_not_found")
        if message.author_id != user.id:
            raise AppError("chat.not_author", 403)
        if utc_now() - message.created_at > CHANGE_WINDOW:
            raise AppError(
                "chat.change_window_expired",
                403,
                details={"window_minutes": int(CHANGE_WINDOW.total_seconds() // 60)},
            )
        return message

    async def edit(self, user: CurrentUser, message_id: int, body: str) -> SendOutcome:
        """Replaces the body within the window; a verified answer loses its mark, reactions stay (§13.2)."""
        _check_body(body)
        message = await self._own_message(user, message_id, Action.EDIT)
        was_held = message.moderation is MessageModeration.HELD
        term_action = await BlockedTermService(self.session).check(body)
        if term_action is BlockedTermAction.REJECT:
            raise AppError("chat.message_blocked", 422)
        moderation = (
            MessageModeration.HIDDEN
            if message.moderation is MessageModeration.HIDDEN
            else MessageModeration.HELD
            if term_action is BlockedTermAction.HOLD
            else MessageModeration.VISIBLE
        )
        parsed, notices = await self._mentions(user, message.channel_id, body)
        # The channel flag is sticky: once @channel was sent, everyone was already told.
        parsed = ParsedMentions(parsed.user_ids, parsed.channel or message.mentions_channel)
        await self.session.execute(
            update(Message)
            .where(Message.id == message.id, Message.created_at == message.created_at)
            .values(
                body=body,
                body_tsv=body_vector(body) if moderation is MessageModeration.VISIBLE else None,
                moderation=moderation,
                edited_at=utc_now(),
                is_verified_answer=False,
                verified_by=None,
                mentions_channel=parsed.channel,
            )
            .execution_options(synchronize_session=False)
        )
        await self.session.refresh(message)
        mentions = MentionService(self.session)
        added = await mentions.record(message, parsed)
        # Only people newly named are notified; the per-message key stops repeats (§5.6).
        if moderation is MessageModeration.VISIBLE:
            reply_to = None
            if was_held and message.parent_id is not None:
                parent = await find_message(self.session, message.parent_id)
                reply_to = parent.author_id if parent is not None else None
            await mentions.notify(
                message,
                user,
                mentioned=set(parsed.user_ids) if was_held else added,
                channel_wide=parsed.channel,
                reply_to=reply_to,
            )
        await self.session.commit()
        if was_held and moderation is MessageModeration.VISIBLE:
            released = await self.message(message.channel_id, message.id)
            assert released is not None
            await self.bus.publish(
                channel_topic(message.channel_id),
                "message.created",
                released.model_dump(mode="json"),
            )
        else:
            await self.publish_update(message.channel_id, message.id)
        if moderation is not MessageModeration.VISIBLE:
            own = await self.message(message.channel_id, message.id, user.id)
            assert own is not None
            await self.bus.publish(
                user_topic(user.id), "message.updated", own.model_dump(mode="json")
            )
        out = await self.message(message.channel_id, message.id, user.id)
        assert out is not None
        return SendOutcome(out, created=True, notices=notices)

    async def publish_update(self, channel_id: uuid.UUID, message_id: int) -> None:
        """Sends the message as every member sees it (no per-reader fields) after a committed change."""
        out = await self.message(channel_id, message_id)
        if out is not None:
            await self.bus.publish(
                channel_topic(channel_id), "message.updated", out.model_dump(mode="json")
            )

    async def delete(self, user: CurrentUser, message_id: int) -> MessageOut:
        """Soft delete by the author within the window; replies stay under a placeholder (§13.2). The body is
        kept for moderation (Sprint 10) but no longer searchable or shown."""
        message = await self._own_message(user, message_id, Action.DELETE)
        channel_id = message.channel_id
        await self.session.execute(
            update(Message)
            .where(Message.id == message.id, Message.created_at == message.created_at)
            .values(deleted_at=utc_now(), body_tsv=None, is_verified_answer=False)
            .execution_options(synchronize_session=False)
        )
        # The loaded row is stale after a bulk update; the payload must show the deletion.
        self.session.expire(message)
        await self.session.commit()
        out = await self.message(channel_id, message_id)
        assert out is not None
        await self.bus.publish(
            channel_topic(channel_id),
            "message.deleted",
            {
                "id": out.id,
                "channel_id": out.channel_id,
                "parent_id": out.parent_id,
                "deleted_at": out.deleted_at.isoformat() if out.deleted_at else None,
            },
        )
        return out

    async def thread(
        self,
        user: CurrentUser,
        message_id: int,
        *,
        after: int | None = None,
        limit: int = PAGE_SIZE,
    ) -> Thread:
        """The root and its replies, oldest first; ``after`` pages forward (§5.3)."""
        root = await find_message(self.session, message_id)
        if root is None:
            raise AppError("chat.message_not_found", 404)
        if not (await self.access.decide(user, root.channel_id, Action.READ)).allowed:
            raise AppError("chat.message_not_found", 404)
        if root.parent_id is not None:
            root = await find_message(self.session, root.parent_id)
            if root is None:
                raise AppError("chat.message_not_found", 404)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        query = with_authors().where(
            Message.parent_id == root.id, Message.created_at >= root.created_at
        )
        if after is not None:
            query = query.where(Message.id > after, Message.created_at >= created_at_of(after))
        rows = [
            (row[0], row[1], row[2])
            for row in await self.session.execute(query.order_by(Message.id.asc()).limit(limit + 1))
        ]
        head = (
            await self.session.execute(
                with_authors().where(Message.id == root.id, Message.created_at == root.created_at)
            )
        ).one()
        payloads = await enrich(self.session, [(head[0], head[1], head[2]), *rows[:limit]], user.id)
        return Thread(payloads[0], payloads[1:], has_more=len(rows) > limit)

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
        """Top-level messages, oldest first; replies live in their thread. ``before`` pages back from a
        message, ``after`` forward; neither gives the latest."""
        if not (await self.access.decide(user, channel_id, Action.READ)).allowed:
            raise AppError("chat.channel_not_found", 404)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        return await self._page(
            channel_id,
            viewer=user.id,
            before=before,
            after=after,
            topic_id=topic_id,
            limit=limit,
            top_level=True,
        )

    async def backfill(self, channel_id: uuid.UUID, after: int) -> Page:
        """What a reconnecting client missed, replies included; ``has_more`` means the gap is too large to
        replay (§13.2)."""
        if created_at_of(after) < utc_now() - BACKFILL_WINDOW:
            return Page([], has_more=True)
        return await self._page(channel_id, viewer=None, after=after, limit=BACKFILL_LIMIT)

    async def _page(
        self,
        channel_id: uuid.UUID,
        *,
        viewer: uuid.UUID | None,
        before: int | None = None,
        after: int | None = None,
        topic_id: uuid.UUID | None = None,
        limit: int,
        top_level: bool = False,
    ) -> Page:
        query = with_authors().where(Message.channel_id == channel_id)
        if top_level:
            query = query.where(Message.parent_id.is_(None))
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
        rows = [(row[0], row[1], row[2]) for row in await self.session.execute(query)]
        has_more = len(rows) > limit
        rows = rows[:limit]
        if not ascending:
            rows.reverse()
        return Page(await enrich(self.session, rows, viewer), has_more)

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
