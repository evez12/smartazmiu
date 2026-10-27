"""Reports (§5.4, §5.5, D-070): one per person and target, rate limited, audited; listed for staff."""

import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.time import utc_now
from app.modules.academics.models import Subject
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.chat.access import ChannelAccess
from app.modules.chat.bus import ChatBus, channel_topic, user_topic
from app.modules.chat.lookup import MAX_MESSAGE_ID, find_message
from app.modules.chat.models import (
    Channel,
    ChannelMember,
    MemberRole,
    Message,
    MessageModeration,
)
from app.modules.chat.payloads import message_payload
from app.modules.chat.policy import Action
from app.modules.chat.schemas import AuthorOut
from app.modules.knowledge.models import CourseTip, TipStatus
from app.modules.mentorship.service import readable_subject
from app.modules.reports.models import Report, ReportReason, ReportStatus, ReportTarget
from app.modules.reports.schemas import ReportedMessageOut, ReportedTipOut, ReportOut
from app.modules.users.models import User
from app.modules.users.profile import photo_url
from app.modules.users.service import CurrentUser

# Enough for someone working through a bad thread; stops a script flooding the queue (§14).
REPORT_LIMIT = RateLimit("report_create", limit=10, window_seconds=3600)
# Staff see enough of a message to judge it, not more.
EXCERPT = 1000


@dataclass(frozen=True, slots=True)
class Created:
    report: Report
    duplicate: bool


@dataclass(frozen=True, slots=True)
class ReportPage:
    items: list[ReportOut]
    total: int


def _person(user: User | None) -> AuthorOut | None:
    if user is None:
        return None
    return AuthorOut(id=str(user.id), display_name=user.display_name, photo_url=photo_url(user))


class ReportService:
    def __init__(self, session: AsyncSession, access: ChannelAccess, cache: Redis) -> None:
        self.session = session
        self.access = access
        self.cache = cache

    async def create(
        self,
        user: CurrentUser,
        target_type: ReportTarget,
        target_id: str,
        reason: ReportReason,
        note: str,
    ) -> Created:
        channel_id, normalized = await self._target(user, target_type, target_id)
        existing = await self._existing(user.id, target_type, normalized)
        if existing is not None:
            # Counted once (§5.5): the second report changes nothing and spends no rate-limit unit.
            return Created(existing, duplicate=True)
        await enforce_rate_limit(self.cache, REPORT_LIMIT, str(user.id))
        report_id = await self.session.scalar(
            insert(Report)
            .values(
                reporter_id=user.id,
                target_type=target_type,
                target_id=normalized,
                channel_id=channel_id,
                reason=reason,
                note=note.strip(),
            )
            .on_conflict_do_nothing(index_elements=["reporter_id", "target_type", "target_id"])
            .returning(Report.id)
        )
        if report_id is None:
            # A concurrent double submit won.
            raced = await self._existing(user.id, target_type, normalized)
            assert raced is not None
            return Created(raced, duplicate=True)
        # The note is the reporter's own words and stays out of the audit log (D-034).
        record_audit(
            self.session,
            AuditAction.REPORT_CREATED,
            actor_id=user.id,
            target_type="report",
            target_id=report_id,
            details={"target_type": target_type.value, "reason": reason.value},
        )
        hidden_message: Message | None = None
        if target_type is ReportTarget.MESSAGE:
            message = await find_message(self.session, int(normalized), lock=True)
            assert message is not None
            distinct = await self.session.scalar(
                select(func.count(func.distinct(Report.reporter_id))).where(
                    Report.target_type == ReportTarget.MESSAGE,
                    Report.target_id == normalized,
                )
            )
            if (
                distinct is not None
                and distinct >= 3
                and message.moderation is MessageModeration.VISIBLE
                and message.deleted_at is None
            ):
                await self.session.execute(
                    update(Message)
                    .where(Message.id == message.id, Message.created_at == message.created_at)
                    .values(moderation=MessageModeration.HIDDEN, body_tsv=None)
                )
                record_audit(
                    self.session,
                    AuditAction.MESSAGE_AUTO_HIDDEN,
                    actor_id=None,
                    target_type="message",
                    target_id=normalized,
                    details={"channel_id": str(message.channel_id)},
                )
                hidden_message = message
        await self.session.commit()
        if hidden_message is not None:
            bus = ChatBus(self.cache)
            public = await message_payload(self.session, hidden_message.id, None)
            assert public is not None
            await bus.publish(
                channel_topic(hidden_message.channel_id),
                "message.updated",
                public.model_dump(mode="json"),
            )
            if hidden_message.author_id is not None:
                own = await message_payload(
                    self.session, hidden_message.id, hidden_message.author_id
                )
                assert own is not None
                await bus.publish(
                    user_topic(hidden_message.author_id),
                    "message.updated",
                    own.model_dump(mode="json"),
                )
            moderators = await self.session.scalars(
                select(ChannelMember.user_id).where(
                    ChannelMember.channel_id == hidden_message.channel_id,
                    ChannelMember.role.in_([MemberRole.MODERATOR, MemberRole.OWNER]),
                )
            )
            for moderator_id in moderators:
                if moderator_id == hidden_message.author_id:
                    continue
                private = await message_payload(self.session, hidden_message.id, moderator_id)
                assert private is not None
                await bus.publish(
                    user_topic(moderator_id), "message.updated", private.model_dump(mode="json")
                )
        report = await self.session.get(Report, report_id)
        assert report is not None
        return Created(report, duplicate=False)

    async def _existing(
        self, reporter: uuid.UUID, target_type: ReportTarget, target_id: str
    ) -> Report | None:
        return await self.session.scalar(
            select(Report).where(
                Report.reporter_id == reporter,
                Report.target_type == target_type,
                Report.target_id == target_id,
            )
        )

    async def _target(
        self, user: CurrentUser, target_type: ReportTarget, target_id: str
    ) -> tuple[uuid.UUID | None, str]:
        """The reported thing must exist and be visible to the reporter; otherwise the same 404 as for
        something that does not exist, so reports cannot probe channels or accounts (§14)."""
        if target_type is ReportTarget.MESSAGE:
            if not target_id.isdigit() or not 0 < int(target_id) <= MAX_MESSAGE_ID:
                raise AppError("reports.target_not_found", 404)
            message = await find_message(self.session, int(target_id))
            if message is None:
                raise AppError("reports.target_not_found", 404)
            if not (await self.access.decide(user, message.channel_id, Action.READ)).allowed:
                raise AppError("reports.target_not_found", 404)
            if message.author_id == user.id:
                raise AppError("reports.own_content", 422)
            return message.channel_id, str(message.id)
        if target_type is ReportTarget.TIP:
            try:
                tip_id = uuid.UUID(target_id)
            except ValueError as exc:
                raise AppError("reports.target_not_found", 404) from exc
            tip = await self.session.get(CourseTip, tip_id)
            if tip is None or tip.status is not TipStatus.PUBLISHED:
                raise AppError("reports.target_not_found", 404)
            try:
                await readable_subject(
                    self.session, user, tip.subject_id, "reports.target_not_found"
                )
            except AppError as exc:
                raise AppError("reports.target_not_found", 404) from exc
            if tip.author_id == user.id:
                raise AppError("reports.own_content", 422)
            return None, str(tip.id)
        try:
            person_id = uuid.UUID(target_id)
        except ValueError as exc:
            raise AppError("reports.target_not_found", 404) from exc
        if person_id == user.id:
            raise AppError("reports.own_content", 422)
        if await self.session.get(User, person_id) is None:
            raise AppError("reports.target_not_found", 404)
        return None, str(person_id)

    async def page(self, status: ReportStatus | None, offset: int, limit: int) -> ReportPage:
        query = select(Report)
        count = select(func.count()).select_from(Report)
        if status is not None:
            query = query.where(Report.status == status)
            count = count.where(Report.status == status)
        reports = list(
            await self.session.scalars(
                query.order_by(Report.created_at.desc(), Report.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return ReportPage(await self._out(reports), int(await self.session.scalar(count) or 0))

    async def set_status(
        self, actor: CurrentUser, report_id: uuid.UUID, status: ReportStatus
    ) -> ReportOut:
        report = await self.session.get(Report, report_id, with_for_update=True)
        if report is None:
            raise AppError("reports.not_found", 404)
        if report.status is not status:
            previous = report.status
            report.status = status
            reopened = status is ReportStatus.OPEN
            report.handled_by = None if reopened else actor.id
            report.handled_at = None if reopened else utc_now()
            record_audit(
                self.session,
                AuditAction.REPORT_HANDLED,
                actor_id=actor.id,
                target_type="report",
                target_id=report.id,
                details={"from": previous.value, "to": status.value},
            )
            await self.session.commit()
        return (await self._out([report]))[0]

    async def _out(self, reports: list[Report]) -> list[ReportOut]:
        if not reports:
            return []
        message_ids = [int(r.target_id) for r in reports if r.target_type is ReportTarget.MESSAGE]
        messages: dict[str, tuple[Message, str]] = {}
        for message_id in message_ids:
            found = await find_message(self.session, message_id)
            if found is not None:
                name = await self.session.scalar(
                    select(Channel.name).where(Channel.id == found.channel_id)
                )
                messages[str(message_id)] = (found, name or "")
        people_ids = {r.reporter_id for r in reports} | {r.handled_by for r in reports}
        people_ids |= {
            uuid.UUID(r.target_id) for r in reports if r.target_type is ReportTarget.USER
        }
        people_ids |= {found.author_id for found, _ in messages.values()}
        tips: dict[str, tuple[CourseTip, str]] = {}
        for report in reports:
            if report.target_type is ReportTarget.TIP:
                tip = await self.session.get(CourseTip, uuid.UUID(report.target_id))
                if tip is not None:
                    subject_name = await self.session.scalar(
                        select(Subject.name_az).where(Subject.id == tip.subject_id)
                    )
                    tips[report.target_id] = (tip, subject_name or "")
                    people_ids.add(tip.author_id)
        people_ids.discard(None)
        people = {
            person.id: person
            for person in await self.session.scalars(select(User).where(User.id.in_(people_ids)))
        }
        other = aliased(Report)
        grouped = await self.session.execute(
            select(other.target_id, func.count(func.distinct(other.reporter_id)))
            .where(other.target_id.in_([r.target_id for r in reports]))
            .group_by(other.target_id)
        )
        counts = {target: count for target, count in grouped}
        result = []
        for report in reports:
            message_out = None
            reported = None
            tip_out = None
            if report.target_type is ReportTarget.MESSAGE:
                pair = messages.get(report.target_id)
                if pair is not None:
                    message, channel_name = pair
                    author = people.get(message.author_id) if message.author_id else None
                    reported = _person(author)
                    message_out = ReportedMessageOut(
                        id=str(message.id),
                        channel_id=str(message.channel_id),
                        channel_name=channel_name,
                        author=reported,
                        body=message.body[:EXCERPT],
                        deleted=message.deleted_at is not None,
                        created_at=message.created_at,
                    )
            elif report.target_type is ReportTarget.TIP:
                found_tip = tips.get(report.target_id)
                if found_tip is not None:
                    tip, subject_name = found_tip
                    reported = _person(people.get(tip.author_id))
                    tip_out = ReportedTipOut(
                        id=str(tip.id),
                        subject_name=subject_name,
                        excerpt=tip.exam_advice[:EXCERPT],
                        status=tip.status.value,
                    )
            else:
                reported = _person(people.get(uuid.UUID(report.target_id)))
            result.append(
                ReportOut(
                    id=str(report.id),
                    target_type=report.target_type,
                    reason=report.reason,
                    note=report.note,
                    status=report.status,
                    created_at=report.created_at,
                    reporter=_person(people.get(report.reporter_id))
                    if report.reporter_id
                    else None,
                    reported_user=reported,
                    message=message_out,
                    tip=tip_out,
                    handled_by=_person(people.get(report.handled_by))
                    if report.handled_by
                    else None,
                    handled_at=report.handled_at,
                    reporters=int(counts.get(report.target_id, 1)),
                )
            )
        return result
