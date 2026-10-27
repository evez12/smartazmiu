"""The channels a user sees, direct messages and blocks (§5.4, §5.8). Every list is filtered by membership inside
its SQL query (§4.2); nothing in these payloads touches grades (§5.4)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    Integer,
    and_,
    case,
    cast,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, aliased
from sqlalchemy.sql.selectable import ScalarSelect

from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingGroup,
    CourseOfferingTeacher,
    Semester,
)
from app.modules.audiences.service import TERM_NAMES
from app.modules.chat.access import ALWAYS_REACHES, ChannelAccess
from app.modules.chat.bus import ChatBus
from app.modules.chat.models import (
    Channel,
    ChannelBan,
    ChannelMember,
    ChannelRead,
    ChannelTopic,
    ChannelType,
    GlobalChatBan,
    MemberRole,
    Message,
    MessageMention,
    NotifyLevel,
    UserBlock,
)
from app.modules.chat.policy import Action, authorize
from app.modules.chat.schemas import AuthorOut, Badge, ChannelOut, PostingOut, TopicOut
from app.modules.chat.snowflake import EPOCH_MS, TIMESTAMP_SHIFT
from app.modules.mentorship.badges import guide_terms
from app.modules.mentorship.models import MentorProfile
from app.modules.users.models import DmPolicy, User, UserStatus
from app.modules.users.profile import photo_url
from app.modules.users.service import CurrentUser

# Unread counts stop at 100; the UI shows "99+" from there (§12.7).
UNREAD_CAP = 100
MAX_MEMBERS = 500
# "Shared context" for dm_policy (§5.4): the same group, course or subject community.
SHARED_CONTEXT_TYPES = (
    ChannelType.ACADEMIC_GROUP,
    ChannelType.COURSE_OFFERING,
    ChannelType.SUBJECT_COMMUNITY,
)
NEW_DM_LIMIT = RateLimit("chat_new_dm", limit=30, window_seconds=86400)


def _id_floor(moment: InstrumentedAttribute[datetime]) -> ColumnElement[int]:
    """SQL twin of ``snowflake.floor_id``: the smallest message id of ``moment``."""
    milliseconds = cast(func.floor(func.extract("epoch", moment) * 1000), BigInteger) - EPOCH_MS
    # PostgreSQL shifts a bigint by an integer only.
    return milliseconds.self_group().op("<<", return_type=BigInteger)(
        literal(TIMESTAMP_SHIFT, Integer)
    )


@dataclass(frozen=True, slots=True)
class ChannelList:
    channels: list[ChannelOut]
    blocked_user_ids: list[str]


class ChannelService:
    def __init__(self, session: AsyncSession, access: ChannelAccess, bus: ChatBus) -> None:
        self.session = session
        self.access = access
        self.bus = bus

    async def mine(self, user: CurrentUser) -> ChannelList:
        channels = await self._channels(user, None)
        blocked = await self.session.scalars(
            select(UserBlock.blocked_id).where(UserBlock.blocker_id == user.id)
        )
        return ChannelList(channels, sorted(str(user_id) for user_id in blocked))

    async def get(
        self, user: CurrentUser, channel_id: uuid.UUID
    ) -> tuple[ChannelOut, list[TopicOut], uuid.UUID | None]:
        found = await self._channels(user, channel_id)
        if not found:
            raise AppError("chat.channel_not_found", 404)
        subject_id = await self.session.scalar(
            select(Channel.subject_id).where(Channel.id == channel_id)
        )
        topics = await self.session.execute(
            select(ChannelTopic.id, ChannelTopic.slug, ChannelTopic.name)
            .where(ChannelTopic.channel_id == channel_id)
            .order_by(ChannelTopic.position)
        )
        topic_list = [TopicOut(id=str(i), slug=slug, name=name) for i, slug, name in topics]
        return found[0], topic_list, subject_id

    async def _channels(self, user: CurrentUser, only: uuid.UUID | None) -> list[ChannelOut]:
        """The user's channels with their unread counts in one query (capped, from the later of the read
        marker and the time the user joined)."""
        member = aliased(ChannelMember)
        read = aliased(ChannelRead)
        peer = aliased(User)
        since = func.greatest(
            func.coalesce(read.last_read_message_id, 0), _id_floor(member.joined_at)
        )

        def capped_count(*conditions: ColumnElement[bool]) -> ScalarSelect[int]:
            counted = (
                select(literal(1))
                .where(
                    Message.channel_id == member.channel_id,
                    Message.id > since,
                    # The id bound turned into a created_at bound lets the planner skip older months (ADR 0002).
                    Message.created_at
                    >= func.to_timestamp((since.op(">>")(TIMESTAMP_SHIFT) + EPOCH_MS) / 1000.0),
                    Message.author_id.is_distinct_from(user.id),
                    Message.deleted_at.is_(None),
                    *conditions,
                )
                .limit(UNREAD_CAP)
                .correlate(member, read)
                .subquery()
            )
            return select(func.count()).select_from(counted).scalar_subquery()

        # Replies live in their threads and are announced to the people concerned, not in the badge (D-067).
        unread = capped_count(Message.parent_id.is_(None))
        mentioned = capped_count(
            or_(
                Message.mentions_channel,
                exists().where(
                    MessageMention.message_id == Message.id, MessageMention.user_id == user.id
                ),
            )
        )
        peer_id = case(
            (Channel.user_low_id == user.id, Channel.user_high_id), else_=Channel.user_low_id
        )
        groups = (
            select(
                func.string_agg(
                    AcademicGroup.code, aggregate_order_by(literal(", "), AcademicGroup.code)
                )
            )
            .join(CourseOfferingGroup, CourseOfferingGroup.academic_group_id == AcademicGroup.id)
            .where(CourseOfferingGroup.course_offering_id == Channel.course_offering_id)
            .scalar_subquery()
        )
        query = (
            select(
                Channel,
                member.notify_level,
                member.muted_until,
                read.last_read_message_id,
                unread,
                mentioned,
                peer,
                groups,
                Semester.year,
                Semester.term,
            )
            .join(member, and_(member.channel_id == Channel.id, member.user_id == user.id))
            .outerjoin(read, and_(read.channel_id == Channel.id, read.user_id == user.id))
            .outerjoin(peer, and_(Channel.type == ChannelType.DM, peer.id == peer_id))
            .outerjoin(CourseOffering, CourseOffering.id == Channel.course_offering_id)
            .outerjoin(Semester, Semester.id == CourseOffering.semester_id)
            .where(
                ~exists().where(ChannelBan.channel_id == Channel.id, ChannelBan.user_id == user.id),
                ~exists().where(GlobalChatBan.user_id == user.id),
            )
            .order_by(Channel.type, Channel.is_archived, Channel.name, Channel.id)
        )
        if only is not None:
            query = query.where(Channel.id == only)
        rows = list(await self.session.execute(query))
        states = await self.access.states(user, [row[0].id for row in rows])
        result = []
        for channel, level, muted, last_read, count, mentions, other, codes, year, term in rows:
            decision = authorize(Action.SEND, states[channel.id])
            context = None
            if channel.type is ChannelType.COURSE_OFFERING and year is not None:
                context = f"{codes or ''} · {year} {TERM_NAMES[term]}".strip(" ·")
            result.append(
                ChannelOut(
                    id=str(channel.id),
                    type=channel.type,
                    name=other.display_name if other is not None else channel.name,
                    context=context,
                    peer=_author(other) if other is not None else None,
                    is_archived=channel.is_archived,
                    is_readonly=channel.is_readonly,
                    notify_level=level,
                    muted_until=muted,
                    unread_count=count,
                    mention_count=mentions,
                    last_read_message_id=str(last_read) if last_read is not None else None,
                    posting=PostingOut(
                        allowed=decision.allowed,
                        reason=decision.reason,
                        until=decision.until,
                        retry_after_seconds=decision.retry_after,
                    ),
                )
            )
        return result

    async def members(self, user: CurrentUser, channel_id: uuid.UUID) -> list[AuthorOut]:
        if not (await self.access.decide(user, channel_id, Action.READ)).allowed:
            raise AppError("chat.channel_not_found", 404)
        teaches = exists().where(
            CourseOfferingTeacher.teacher_id == User.id,
            CourseOfferingTeacher.course_offering_id == Channel.course_offering_id,
        )
        curates = exists().where(
            AcademicGroup.curator_id == User.id, AcademicGroup.id == Channel.academic_group_id
        )
        rows = await self.session.execute(
            select(User, teaches, curates)
            .join(ChannelMember, ChannelMember.user_id == User.id)
            .join(Channel, Channel.id == ChannelMember.channel_id)
            .where(ChannelMember.channel_id == channel_id)
            .order_by(User.display_name, User.id)
            .limit(MAX_MEMBERS)
        )
        people = list(rows)
        guides = await guide_terms(
            self.session, ((channel_id, person.id) for person, _, _ in people)
        )
        result = []
        for person, is_teacher, is_curator in people:
            author = _author(person, "teacher" if is_teacher else "curator" if is_curator else None)
            term = guides.get((channel_id, person.id))
            if author.badge is None and term is not None:
                author.badge = "guide"
                author.guide_semester = term
            result.append(author)
        return result

    async def open_dm(self, user: CurrentUser, other_id: uuid.UUID) -> tuple[ChannelOut, bool]:
        """The existing DM with ``other_id``, or a new one if ``dm_policy`` and blocks allow it (§5.4).

        A policy changed later never closes an existing DM (§13.2); sending into it is decided per message.
        """
        if other_id == user.id:
            raise AppError("chat.dm_self", 422)
        other = await self.session.get(User, other_id)
        if other is None or other.status is not UserStatus.ACTIVE:
            raise AppError("chat.user_not_found", 404)
        low, high = sorted((user.id, other_id))
        existing = await self.session.scalar(
            select(Channel.id).where(
                Channel.type == ChannelType.DM,
                Channel.user_low_id == low,
                Channel.user_high_id == high,
            )
        )
        if existing is not None:
            return (await self._channels(user, existing))[0], False
        if await self._blocked(user.id, other_id):
            raise AppError("chat.user_blocked", 403)
        # Blocked by the other person or not allowed by their policy: one answer, so a block cannot be told
        # apart from a closed inbox (§5.4).
        if await self._blocked(other_id, user.id) or not await self._policy_allows(user, other):
            raise AppError("chat.dm_unavailable", 403)
        await enforce_rate_limit(self.access.cache, NEW_DM_LIMIT, str(user.id))
        channel_id = await self.ensure_dm(user.id, other_id)
        await self.session.commit()
        await self.bus.membership_changed([(channel_id, low), (channel_id, high)], [])
        return (await self._channels(user, channel_id))[0], True

    async def ensure_dm(self, creator: uuid.UUID, other_id: uuid.UUID) -> uuid.UUID:
        """The DM of the pair, created with both members if missing; in the caller's transaction, no policy check.

        Callers decide whether the pair may talk: ``open_dm`` through ``dm_policy`` and blocks, an accepted advice
        request through the request itself (§5.2). The caller commits and announces the membership.
        """
        low, high = sorted((creator, other_id))
        statement = insert(Channel).values(
            type=ChannelType.DM, name="", user_low_id=low, user_high_id=high, created_by=creator
        )
        channel_id: uuid.UUID | None = await self.session.scalar(
            statement.on_conflict_do_update(
                index_elements=["user_low_id", "user_high_id"],
                index_where=text("type = 'dm'"),
                # A concurrent request created it first: take that one.
                set_={"user_low_id": statement.excluded.user_low_id},
            ).returning(Channel.id)
        )
        assert channel_id is not None
        await self.session.execute(
            insert(ChannelMember)
            .values(
                [
                    {"channel_id": channel_id, "user_id": person, "role": MemberRole.MEMBER}
                    for person in (low, high)
                ]
            )
            .on_conflict_do_nothing()
        )
        return channel_id

    async def _blocked(self, blocker: uuid.UUID, blocked: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(UserBlock.blocker_id == blocker, UserBlock.blocked_id == blocked)
                )
            )
        )

    async def _policy_allows(self, user: CurrentUser, other: User) -> bool:
        if user.roles & ALWAYS_REACHES:
            return True
        if other.dm_policy is DmPolicy.EVERYONE:
            return True
        if other.dm_policy is DmPolicy.SHARED_CONTEXT:
            mine = aliased(ChannelMember)
            theirs = aliased(ChannelMember)
            shared = await self.session.scalar(
                select(
                    exists().where(
                        mine.user_id == user.id,
                        theirs.user_id == other.id,
                        theirs.channel_id == mine.channel_id,
                        Channel.id == mine.channel_id,
                        Channel.type.in_(SHARED_CONTEXT_TYPES),
                        ~Channel.is_archived,
                    )
                )
            )
            return bool(shared)
        # guides_and_teachers: teachers and staff were let through above; guides of any subject pass (§5.4).
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        MentorProfile.user_id == user.id, MentorProfile.revoked_at.is_(None)
                    )
                )
            )
        )

    async def update_membership(
        self,
        user: CurrentUser,
        channel_id: uuid.UUID,
        *,
        notify_level: NotifyLevel | None,
        muted_until: datetime | None,
        set_muted: bool,
    ) -> ChannelOut:
        values: dict[str, object] = {}
        if notify_level is not None:
            values["notify_level"] = notify_level
        if set_muted:
            values["muted_until"] = muted_until
        if values:
            updated = await self.session.scalar(
                update(ChannelMember)
                .where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == user.id)
                .values(**values)
                .returning(ChannelMember.channel_id)
            )
            if updated is None:
                raise AppError("chat.channel_not_found", 404)
            await self.session.commit()
        found = await self._channels(user, channel_id)
        if not found:
            raise AppError("chat.channel_not_found", 404)
        return found[0]

    async def block(self, user: CurrentUser, other_id: uuid.UUID) -> None:
        if other_id == user.id:
            raise AppError("chat.block_self", 422)
        if await self.session.get(User, other_id) is None:
            raise AppError("chat.user_not_found", 404)
        await self.session.execute(
            insert(UserBlock)
            .values(blocker_id=user.id, blocked_id=other_id)
            .on_conflict_do_nothing()
        )
        await self.session.commit()

    async def unblock(self, user: CurrentUser, other_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(UserBlock).where(
                UserBlock.blocker_id == user.id, UserBlock.blocked_id == other_id
            )
        )
        await self.session.commit()


def _author(user: User, badge: Badge | None = None) -> AuthorOut:
    return AuthorOut(
        id=str(user.id), display_name=user.display_name, photo_url=photo_url(user), badge=badge
    )
