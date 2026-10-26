"""Loads what the chat policy needs (ADR 0004): one query for any number of channels, plus Redis counters."""

import uuid
from dataclasses import replace
from datetime import datetime

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import and_, case, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError
from app.core.ratelimit import RateLimit, consume
from app.core.time import utc_now
from app.modules.academics.models import CourseOfferingTeacher
from app.modules.chat.models import Channel, ChannelMember, ChannelType, MemberRole, UserBlock
from app.modules.chat.policy import (
    Action,
    ChannelState,
    Decision,
    ExamWindowProvider,
    Reason,
    authorize,
)
from app.modules.users.models import DmPolicy, RoleCode, User, UserStatus
from app.modules.users.service import CurrentUser

logger = structlog.get_logger(__name__)

# 10 messages per 10 s per user per channel (§5.5).
SEND_LIMIT = RateLimit("chat_send", limit=10, window_seconds=10)
# Teachers and staff can always write to someone, even when that person accepts no messages (§5.4).
ALWAYS_REACHES = frozenset({RoleCode.TEACHER.value, RoleCode.STAFF.value})
# Besides the offering's teachers and channel moderators, these global roles may use @channel (§5.3, D-067).
MENTION_CHANNEL_ROLES = frozenset({RoleCode.TEACHER.value, RoleCode.STAFF.value})


def deny(decision: Decision, *, missing: str = "chat.channel_not_found") -> AppError:
    """The REST form of a refusal; non-members get the same 404 as something that does not exist (§14)."""
    reason = decision.reason
    if reason is Reason.NOT_MEMBER or reason is None:
        return AppError(missing, 404)
    details: dict[str, object] = {}
    headers = None
    if decision.until is not None:
        details["until"] = decision.until.isoformat()
    if decision.retry_after is not None:
        details["retry_after_seconds"] = decision.retry_after
        headers = {"Retry-After": str(decision.retry_after)}
    status = 429 if reason in (Reason.RATE_LIMITED, Reason.SLOW_MODE) else 403
    return AppError(reason.value, status, details=details, headers=headers)


def slow_mode_key(channel_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"chat:slow:{channel_id}:{user_id}"


class ChannelAccess:
    def __init__(self, session: AsyncSession, cache: Redis, exams: ExamWindowProvider) -> None:
        self.session = session
        self.cache = cache
        self.exams = exams

    async def states(
        self, user: CurrentUser, channel_ids: list[uuid.UUID], now: datetime | None = None
    ) -> dict[uuid.UUID, ChannelState]:
        """The policy state of each existing channel; channels that do not exist are left out."""
        now = now or utc_now()
        if not channel_ids:
            return {}
        member = aliased(ChannelMember)
        peer_id = case(
            (Channel.user_low_id == user.id, Channel.user_high_id), else_=Channel.user_low_id
        )
        peer = aliased(User)
        teaches = exists().where(
            CourseOfferingTeacher.course_offering_id == Channel.course_offering_id,
            CourseOfferingTeacher.teacher_id == user.id,
        )
        i_blocked = exists().where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == peer_id)
        blocked_me = exists().where(
            UserBlock.blocker_id == peer_id, UserBlock.blocked_id == user.id
        )
        rows = await self.session.execute(
            select(
                Channel.id,
                Channel.type,
                Channel.is_archived,
                Channel.is_readonly,
                Channel.slow_mode_seconds,
                member.user_id.is_not(None),
                member.role,
                member.posting_muted_until,
                Channel.course_offering_id.is_not(None) & teaches,
                case((Channel.type == ChannelType.DM, i_blocked), else_=False),
                case((Channel.type == ChannelType.DM, blocked_me), else_=False),
                peer.dm_policy,
            )
            .outerjoin(member, and_(member.channel_id == Channel.id, member.user_id == user.id))
            .outerjoin(peer, and_(Channel.type == ChannelType.DM, peer.id == peer_id))
            .where(Channel.id.in_(channel_ids))
        )
        windows = await self.exams.windows(list(channel_ids), now)
        exam_until: dict[uuid.UUID, datetime] = {}
        for window in windows:
            if window.starts_at <= now < window.ends_at:
                # Overlapping slots merge into one window ending at the latest end (§13.4).
                exam_until[window.channel_id] = max(
                    window.ends_at, exam_until.get(window.channel_id, window.ends_at)
                )
        reaches_everyone = bool(user.roles & ALWAYS_REACHES)
        announces = bool(user.roles & MENTION_CHANNEL_ROLES)
        states: dict[uuid.UUID, ChannelState] = {}
        for (
            channel_id,
            kind,
            archived,
            readonly,
            slow_seconds,
            is_member,
            role,
            muted_until,
            is_teacher,
            user_blocked_peer,
            peer_blocked_user,
            peer_policy,
        ) in rows:
            privileged = is_teacher or role in (MemberRole.OWNER, MemberRole.MODERATOR)
            closed_dm = kind is ChannelType.DM and peer_policy is DmPolicy.NOBODY
            states[channel_id] = ChannelState(
                now=now,
                is_member=bool(is_member),
                account_active=user.status is UserStatus.ACTIVE,
                is_archived=archived,
                is_readonly=readonly,
                member_readonly=role is MemberRole.READONLY,
                exam_until=exam_until.get(channel_id),
                user_blocked_peer=bool(user_blocked_peer),
                dm_unavailable=bool(peer_blocked_user) or (closed_dm and not reaches_everyone),
                posting_muted_until=muted_until,
                slow_mode_seconds=slow_seconds,
                slow_mode_exempt=privileged,
                can_mention_channel=privileged or announces,
            )
        return states

    async def state(self, user: CurrentUser, channel_id: uuid.UUID) -> ChannelState:
        found = (await self.states(user, [channel_id])).get(channel_id)
        return found or ChannelState(now=utc_now(), is_member=False)

    async def decide(self, user: CurrentUser, channel_id: uuid.UUID, action: Action) -> Decision:
        return authorize(action, await self.state(user, channel_id))

    async def claim_send(self, user: CurrentUser, channel_id: uuid.UUID) -> Decision:
        """Authorises a new message and, if allowed, spends the slow-mode slot and one rate-limit unit."""
        state = await self.state(user, channel_id)
        decision = authorize(Action.SEND, state)
        if not decision.allowed:
            return decision
        if state.slow_mode_seconds and not state.slow_mode_exempt:
            retry = await self._claim_slow_mode(channel_id, user.id, state.slow_mode_seconds)
            state = replace(state, slow_mode_retry_after=retry)
        retry_after = await consume(self.cache, SEND_LIMIT, f"{user.id}:{channel_id}")
        return authorize(Action.SEND, replace(state, rate_limit_retry_after=retry_after))

    async def _claim_slow_mode(
        self, channel_id: uuid.UUID, user_id: uuid.UUID, seconds: int
    ) -> int | None:
        """None when the slot was free (and is now taken), else the seconds until it frees up."""
        key = slow_mode_key(channel_id, user_id)
        try:
            if await self.cache.set(key, "1", nx=True, ex=seconds):
                return None
            remaining = await self.cache.ttl(key)
        except RedisError as exc:
            # An evicted or unreachable key lets someone post slightly early, which is harmless (ADR 0004).
            logger.warning("slow_mode_unavailable", error=type(exc).__name__)
            return None
        return max(1, int(remaining))
