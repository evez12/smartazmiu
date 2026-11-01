"""Exam windows for chat authorization, read from the exam slots at authorization time (D-059, D-097)."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import CourseOffering
from app.modules.chat.models import Channel, ChannelType
from app.modules.chat.policy import ExamWindow
from app.modules.exams.models import ExamSlot

LEAD = timedelta(minutes=15)
"""Exam mode starts this long before the exam does (§5.2)."""


class DatabaseExamWindows:
    """Windows start at the lead, not at the exam: the caller treats a window as the time exam mode applies.

    A course channel follows the exams of its offering; a subject community follows the exams of every offering
    of its subject, so overlapping windows merge in the caller (D-003)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def windows(self, channel_ids: list[uuid.UUID], at: datetime) -> list[ExamWindow]:
        if not channel_ids:
            return []
        rows = await self.session.execute(
            select(Channel.id, ExamSlot.starts_at, ExamSlot.ends_at)
            .select_from(Channel)
            .join(ExamSlot, true())
            .join(CourseOffering, CourseOffering.id == ExamSlot.course_offering_id)
            .where(
                Channel.id.in_(channel_ids),
                or_(
                    and_(
                        Channel.type == ChannelType.COURSE_OFFERING,
                        Channel.course_offering_id == ExamSlot.course_offering_id,
                    ),
                    and_(
                        Channel.type == ChannelType.SUBJECT_COMMUNITY,
                        Channel.subject_id == CourseOffering.subject_id,
                    ),
                ),
                ExamSlot.starts_at - LEAD <= at,
                ExamSlot.ends_at > at,
            )
        )
        return [
            ExamWindow(channel_id=channel_id, starts_at=starts_at - LEAD, ends_at=ends_at)
            for channel_id, starts_at, ends_at in rows
        ]
