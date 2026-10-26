"""The guide badge in subject communities (§5.2): "Bələdçi · 2025 Payız", never the grade."""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academics.models import Semester
from app.modules.audiences.service import TERM_NAMES
from app.modules.chat.models import Channel, ChannelType
from app.modules.mentorship.models import MentorProfile


def term_label(semester: Semester) -> str:
    return f"{semester.year} {TERM_NAMES[semester.term]}"


async def guide_terms(
    session: AsyncSession, pairs: Iterable[tuple[uuid.UUID, uuid.UUID]]
) -> dict[tuple[uuid.UUID, uuid.UUID], str]:
    """For (channel_id, user_id) pairs: the guide's semester label where the channel is the community of a subject
    the person guides (profile not revoked)."""
    pairs = set(pairs)
    if not pairs:
        return {}
    channel_ids = {channel_id for channel_id, _ in pairs}
    user_ids = {user_id for _, user_id in pairs}
    rows = await session.execute(
        select(Channel.id, MentorProfile.user_id, Semester)
        .join(MentorProfile, MentorProfile.subject_id == Channel.subject_id)
        .join(Semester, Semester.id == MentorProfile.semester_taken_id)
        .where(
            Channel.id.in_(channel_ids),
            Channel.type == ChannelType.SUBJECT_COMMUNITY,
            MentorProfile.user_id.in_(user_ids),
            MentorProfile.revoked_at.is_(None),
        )
    )
    return {
        (channel_id, user_id): term_label(semester)
        for channel_id, user_id, semester in rows
        if (channel_id, user_id) in pairs
    }
