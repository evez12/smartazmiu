"""Announcements (§6, §6.1): published to an audience, which is resolved at publication and again for people
who join it while the announcement is still active."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, and_, exists, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import utc_now
from app.modules.announcements.models import (
    Announcement,
    AnnouncementRecipient,
    AnnouncementStatus,
)
from app.modules.audiences.service import Audience, Audiences, is_member, members
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier

SUBJECT_TYPE = "announcement"
MAX_PAGE = 50


@dataclass(frozen=True, slots=True)
class AnnouncementDraft:
    title: str
    body: str
    audience: Audience
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class AnnouncementPage:
    items: list[Announcement]
    next_before: uuid.UUID | None


def is_active(now: datetime) -> ColumnElement[bool]:
    return and_(
        Announcement.status == AnnouncementStatus.PUBLISHED,
        or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
    )


def _spec(announcement: Announcement) -> NotificationSpec:
    return NotificationSpec(
        category=NotificationCategory.ANNOUNCEMENTS,
        kind=NotificationKind.ANNOUNCEMENT_PUBLISHED,
        subject_type=SUBJECT_TYPE,
        subject_id=announcement.id,
        dedupe_key=f"announcement:{announcement.id}",
        title=announcement.title,
        link=f"/announcements/{announcement.id}",
    )


class AnnouncementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish(
        self, draft: AnnouncementDraft, author_id: uuid.UUID, idempotency_key: str | None
    ) -> tuple[Announcement, bool]:
        """Publishes and notifies the audience; returns the announcement and whether it is new.

        A repeated request with the same ``Idempotency-Key`` returns the first result (§4.2).
        """
        if idempotency_key:
            existing = await self.session.scalar(
                select(Announcement).where(
                    Announcement.created_by == author_id,
                    Announcement.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return existing, False
        _check_expiry(draft.expires_at)
        await Audiences(self.session).validate(draft.audience)
        announcement = Announcement(
            title=draft.title,
            body=draft.body,
            expires_at=draft.expires_at,
            created_by=author_id,
            idempotency_key=idempotency_key,
            published_at=utc_now(),
        )
        announcement.set_audience(draft.audience)
        self.session.add(announcement)
        await self.session.flush()
        await self._add_recipients(announcement)
        record_audit(
            self.session,
            AuditAction.ANNOUNCEMENT_PUBLISHED,
            actor_id=author_id,
            target_type=SUBJECT_TYPE,
            target_id=announcement.id,
            details={"audience": draft.audience.type.value},
        )
        await self.session.commit()
        return announcement, True

    async def _add_recipients(self, announcement: Announcement) -> int:
        """Adds audience members who are not recipients yet and notifies exactly those."""
        audience = members(announcement.audience).subquery()
        added = await self.session.scalars(
            insert(AnnouncementRecipient)
            .from_select(
                ["announcement_id", "user_id"],
                select(
                    literal(
                        announcement.id, AnnouncementRecipient.__table__.c.announcement_id.type
                    ),
                    audience.c[0],
                ),
            )
            .on_conflict_do_nothing()
            .returning(AnnouncementRecipient.user_id)
        )
        new = list(added)
        if new:
            await Notifier(self.session).notify(
                select(AnnouncementRecipient.user_id).where(
                    AnnouncementRecipient.announcement_id == announcement.id,
                    AnnouncementRecipient.user_id.in_(new),
                ),
                _spec(announcement),
            )
        return len(new)

    async def sync_recipients(self) -> int:
        """People who joined an audience after publication (group transfer, late enrollment) receive the
        announcements that are still active (§6.1). Idempotent: run after imports and on a schedule."""
        added = 0
        for announcement in await self.session.scalars(
            select(Announcement).where(is_active(utc_now()))
        ):
            added += await self._add_recipients(announcement)
        await self.session.commit()
        return added

    async def update(
        self,
        announcement_id: uuid.UUID,
        version: int,
        *,
        title: str,
        body: str,
        expires_at: datetime | None,
        actor_id: uuid.UUID,
    ) -> Announcement:
        """Corrects text or expiry. The audience is fixed and nobody is notified again."""
        announcement = await self._locked(announcement_id)
        if announcement.version != version:
            raise AppError(
                "announcements.version_conflict", 409, details={"version": announcement.version}
            )
        if announcement.status is not AnnouncementStatus.PUBLISHED:
            raise AppError("announcements.archived", 409)
        if expires_at != announcement.expires_at:
            _check_expiry(expires_at)
        announcement.title, announcement.body, announcement.expires_at = title, body, expires_at
        announcement.version += 1
        record_audit(
            self.session,
            AuditAction.ANNOUNCEMENT_EDITED,
            actor_id=actor_id,
            target_type=SUBJECT_TYPE,
            target_id=announcement.id,
        )
        await self.session.commit()
        return announcement

    async def archive(self, announcement_id: uuid.UUID, actor_id: uuid.UUID) -> Announcement:
        announcement = await self._locked(announcement_id)
        if announcement.status is AnnouncementStatus.PUBLISHED:
            announcement.status = AnnouncementStatus.ARCHIVED
            announcement.version += 1
            record_audit(
                self.session,
                AuditAction.ANNOUNCEMENT_ARCHIVED,
                actor_id=actor_id,
                target_type=SUBJECT_TYPE,
                target_id=announcement.id,
            )
            await self.session.commit()
        return announcement

    async def _locked(self, announcement_id: uuid.UUID) -> Announcement:
        announcement = await self.session.scalar(
            select(Announcement).where(Announcement.id == announcement_id).with_for_update()
        )
        if announcement is None:
            raise AppError("request.not_found", 404)
        return announcement

    async def for_user(
        self, user_id: uuid.UUID, before: uuid.UUID | None, limit: int
    ) -> AnnouncementPage:
        """Active announcements the user received, newest first; filtered by recipient in SQL."""
        query = select(Announcement).where(
            is_active(utc_now()),
            exists().where(
                AnnouncementRecipient.announcement_id == Announcement.id,
                AnnouncementRecipient.user_id == user_id,
            ),
        )
        if before is not None:
            query = query.where(Announcement.id < before)
        rows = list(
            await self.session.scalars(query.order_by(Announcement.id.desc()).limit(limit + 1))
        )
        items = rows[:limit]
        return AnnouncementPage(items, items[-1].id if len(rows) > limit else None)

    async def visible(
        self, announcement_id: uuid.UUID, user_id: uuid.UUID, manager: bool
    ) -> Announcement:
        """One announcement: staff who publish see every one; others only active ones they received."""
        query = select(Announcement).where(Announcement.id == announcement_id)
        if not manager:
            query = query.where(
                is_active(utc_now()),
                exists().where(
                    AnnouncementRecipient.announcement_id == Announcement.id,
                    AnnouncementRecipient.user_id == user_id,
                ),
            )
        announcement = await self.session.scalar(query)
        if announcement is None:
            raise AppError("request.not_found", 404)
        return announcement

    async def managed(
        self, page: int, page_size: int
    ) -> tuple[list[tuple[Announcement, int]], int]:
        """Every announcement with its recipient count, for the staff table (offset paging, §4.2)."""
        recipients = (
            select(func.count())
            .where(AnnouncementRecipient.announcement_id == Announcement.id)
            .scalar_subquery()
        )
        rows = await self.session.execute(
            select(Announcement, recipients)
            .order_by(Announcement.published_at.desc(), Announcement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        total = await self.session.scalar(select(func.count()).select_from(Announcement))
        return [(announcement, count) for announcement, count in rows], total or 0


async def still_addressed(
    session: AsyncSession, announcement_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Delivery-time check (§5.6): still active and the user still belongs to its audience."""
    announcement = await session.get(Announcement, announcement_id)
    if announcement is None or announcement.status is not AnnouncementStatus.PUBLISHED:
        return False
    if announcement.expires_at is not None and announcement.expires_at <= utc_now():
        return False
    return bool(await session.scalar(is_member(announcement.audience, user_id)))


def _check_expiry(expires_at: datetime | None) -> None:
    if expires_at is not None and expires_at <= utc_now():
        raise AppError("announcements.expiry_in_past", 422)
