"""The pilot feedback form (D-074): anyone signed in may send feedback; staff list it and close it."""

import uuid

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.time import utc_now
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.feedback.models import Feedback, FeedbackCategory, FeedbackStatus
from app.modules.feedback.schemas import FeedbackOut, FeedbackPerson
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

# Generous for a person with several things to say, small enough that a script cannot flood the list (§14).
FEEDBACK_LIMIT = RateLimit("feedback_create", limit=10, window_seconds=3600)


def _page(path: str) -> str:
    """Keeps the app path only: queries and fragments can carry ids or search terms the sender did not mean to send."""
    path = path.strip().split("?", 1)[0].split("#", 1)[0]
    return path if path.startswith("/") else ""


class FeedbackService:
    def __init__(self, session: AsyncSession, cache: Redis) -> None:
        self.session = session
        self.cache = cache

    async def create(
        self,
        user: CurrentUser,
        category: FeedbackCategory,
        message: str,
        page: str,
        contact_ok: bool,
    ) -> Feedback:
        if not message.strip():
            raise AppError("feedback.message_required", 422)
        await enforce_rate_limit(self.cache, FEEDBACK_LIMIT, str(user.id))
        feedback = Feedback(
            user_id=user.id,
            category=category,
            message=message.strip(),
            page=_page(page),
            contact_ok=contact_ok,
        )
        self.session.add(feedback)
        await self.session.commit()
        return feedback

    async def page(
        self, status: FeedbackStatus | None, offset: int, limit: int
    ) -> tuple[list[FeedbackOut], int]:
        query = select(Feedback)
        count = select(func.count()).select_from(Feedback)
        if status is not None:
            query = query.where(Feedback.status == status)
            count = count.where(Feedback.status == status)
        items = list(
            await self.session.scalars(
                query.order_by(Feedback.created_at.desc(), Feedback.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return await self._out(items), int(await self.session.scalar(count) or 0)

    async def set_status(
        self, actor: CurrentUser, feedback_id: uuid.UUID, status: FeedbackStatus
    ) -> FeedbackOut:
        feedback = await self.session.get(Feedback, feedback_id, with_for_update=True)
        if feedback is None:
            raise AppError("feedback.not_found", 404)
        if feedback.status is not status:
            closed = status is FeedbackStatus.CLOSED
            feedback.status = status
            feedback.handled_by = actor.id if closed else None
            feedback.handled_at = utc_now() if closed else None
            record_audit(
                self.session,
                AuditAction.FEEDBACK_HANDLED,
                actor_id=actor.id,
                target_type="feedback",
                target_id=feedback.id,
                details={"to": status.value},
            )
            await self.session.commit()
        return (await self._out([feedback]))[0]

    async def _out(self, items: list[Feedback]) -> list[FeedbackOut]:
        ids = {f.user_id for f in items} | {f.handled_by for f in items}
        ids.discard(None)
        people = (
            {u.id: u for u in await self.session.scalars(select(User).where(User.id.in_(ids)))}
            if ids
            else {}
        )
        result = []
        for feedback in items:
            sender = people.get(feedback.user_id) if feedback.user_id else None
            handler = people.get(feedback.handled_by) if feedback.handled_by else None
            result.append(
                FeedbackOut(
                    id=str(feedback.id),
                    category=feedback.category,
                    message=feedback.message,
                    page=feedback.page,
                    contact_ok=feedback.contact_ok,
                    status=feedback.status,
                    sender=FeedbackPerson(
                        id=str(sender.id),
                        display_name=sender.display_name,
                        email=sender.email if feedback.contact_ok else None,
                    )
                    if sender
                    else None,
                    handled_by=handler.display_name if handler else None,
                    handled_at=feedback.handled_at,
                    created_at=feedback.created_at,
                )
            )
        return result
