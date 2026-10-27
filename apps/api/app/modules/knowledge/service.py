"""Subject Guide cards (§5.2 flow 5, D-084): written by students who passed a subject in a semester, moderated
before anyone sees them, aggregated on the subject page and upvoted by the subject's students."""

import uuid
from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ids import uuid7
from app.core.time import baku_today, utc_now
from app.modules.academics.models import (
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
    Semester,
    Subject,
)
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.knowledge.models import CourseTip, TipStatus, TipUpvote, WeeklyHours
from app.modules.knowledge.schemas import (
    AggregatedResourceOut,
    MyTipOut,
    SubjectTipsOut,
    TipEligibilityOut,
    TipIn,
    TipModerationOut,
    TipOut,
    TipResourceOut,
    WorkloadOut,
)
from app.modules.materials.models import Material
from app.modules.mentorship.badges import term_label
from app.modules.mentorship.service import readable_subject
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.reports.models import Report, ReportTarget
from app.modules.users.models import User
from app.modules.users.service import CurrentUser

NOT_FOUND = "tips.subject_not_found"
# Students are asked for a card for this long after a semester ends (§5.2 "at semester end").
PROMPT_WINDOW = timedelta(days=90)
TOP_TIPS = 20


def passed_in(user_id: Any, subject_id: Any, semester_id: Any) -> Any:
    return exists(
        select(Enrollment.id)
        .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
        .where(
            Enrollment.user_id == user_id,
            CourseOffering.subject_id == subject_id,
            CourseOffering.semester_id == semester_id,
            Enrollment.status == EnrollmentStatus.COMPLETED,
            Enrollment.passed.is_(True),
        )
    )


def _resources(tip: CourseTip) -> list[TipResourceOut]:
    return [
        TipResourceOut(
            title=str(item.get("title", "")),
            url=item.get("url"),
            material_id=item.get("material_id"),
        )
        for item in tip.resources
    ]


class TipService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def eligible(self, user: CurrentUser) -> list[TipEligibilityOut]:
        rows = await self.session.execute(
            select(Subject, Semester, CourseTip.status)
            .select_from(Enrollment)
            .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
            .join(Subject, Subject.id == CourseOffering.subject_id)
            .join(Semester, Semester.id == CourseOffering.semester_id)
            .outerjoin(
                CourseTip,
                and_(
                    CourseTip.author_id == user.id,
                    CourseTip.subject_id == Subject.id,
                    CourseTip.semester_taken_id == Semester.id,
                ),
            )
            .where(
                Enrollment.user_id == user.id,
                Enrollment.status == EnrollmentStatus.COMPLETED,
                Enrollment.passed.is_(True),
            )
            .order_by(Semester.ends_on.desc(), Subject.name_az)
        )
        return [
            TipEligibilityOut(
                subject_id=str(subject.id),
                subject_name=subject.name_az,
                semester_id=str(semester.id),
                semester=term_label(semester),
                tip_status=status,
            )
            for subject, semester, status in rows
        ]

    async def upsert(self, user: CurrentUser, subject_id: uuid.UUID, body: TipIn) -> MyTipOut:
        """One card per subject and semester: writing again edits it, and an edit goes back to moderation."""
        try:
            semester_id = uuid.UUID(body.semester_id)
        except ValueError as exc:
            raise AppError("tips.not_eligible", 403) from exc
        if not await self.session.scalar(select(passed_in(user.id, subject_id, semester_id))):
            raise AppError("tips.not_eligible", 403)
        resources = await self._clean_resources(subject_id, body)
        values = {
            "difficulty": body.difficulty,
            "weekly_hours": body.weekly_hours,
            "key_topics": body.key_topics.strip(),
            "resources": resources,
            "exam_advice": body.exam_advice.strip(),
            "retrospective": body.retrospective.strip(),
            "status": TipStatus.PENDING,
            "moderation_note": "",
            "reviewed_by": None,
            "reviewed_at": None,
            "updated_at": utc_now(),
        }
        statement = insert(CourseTip).values(
            id=uuid7(),
            subject_id=subject_id,
            author_id=user.id,
            semester_taken_id=semester_id,
            **values,
        )
        tip_id = await self.session.scalar(
            statement.on_conflict_do_update(
                index_elements=["author_id", "subject_id", "semester_taken_id"], set_=values
            ).returning(CourseTip.id)
        )
        await self.session.commit()
        assert tip_id is not None
        return await self._mine(tip_id)

    async def _clean_resources(self, subject_id: uuid.UUID, body: TipIn) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for resource in body.resources:
            url = (resource.url or "").strip() or None
            if url is not None and not url.lower().startswith(("https://", "http://")):
                raise AppError("tips.invalid_link", 422)
            material_id = None
            if resource.material_id:
                try:
                    material_id = uuid.UUID(resource.material_id)
                except ValueError as exc:
                    raise AppError("tips.invalid_material", 422) from exc
                found = await self.session.scalar(
                    select(Material.id).where(
                        Material.id == material_id,
                        Material.subject_id == subject_id,
                        Material.hidden_at.is_(None),
                    )
                )
                if found is None:
                    raise AppError("tips.invalid_material", 422)
            cleaned.append(
                {
                    "title": resource.title.strip(),
                    "url": url,
                    "material_id": str(material_id) if material_id else None,
                }
            )
        return cleaned

    async def _mine(self, tip_id: uuid.UUID) -> MyTipOut:
        tip = await self.session.get(CourseTip, tip_id, populate_existing=True)
        assert tip is not None
        semester = await self.session.get(Semester, tip.semester_taken_id)
        assert semester is not None
        return MyTipOut(
            id=str(tip.id),
            subject_id=str(tip.subject_id),
            semester_id=str(tip.semester_taken_id),
            semester=term_label(semester),
            status=tip.status,
            difficulty=tip.difficulty,
            weekly_hours=tip.weekly_hours,
            key_topics=tip.key_topics,
            resources=_resources(tip),
            exam_advice=tip.exam_advice,
            retrospective=tip.retrospective,
            updated_at=tip.updated_at,
        )

    async def my_tips(self, user: CurrentUser, subject_id: uuid.UUID) -> list[MyTipOut]:
        ids = await self.session.scalars(
            select(CourseTip.id).where(
                CourseTip.author_id == user.id, CourseTip.subject_id == subject_id
            )
        )
        return [await self._mine(tip_id) for tip_id in ids]

    async def subject_page(self, user: CurrentUser, subject_id: uuid.UUID) -> SubjectTipsOut:
        """Published cards only, aggregated; nothing about authors beyond the semester (D-084)."""
        subject = await readable_subject(self.session, user, subject_id, NOT_FOUND)
        rows = list(
            await self.session.execute(
                select(CourseTip, Semester)
                .join(Semester, Semester.id == CourseTip.semester_taken_id)
                .where(CourseTip.subject_id == subject_id, CourseTip.status == TipStatus.PUBLISHED)
                .order_by(CourseTip.upvotes.desc(), CourseTip.updated_at.desc())
            )
        )
        mine = set(
            await self.session.scalars(
                select(TipUpvote.tip_id).where(
                    TipUpvote.user_id == user.id,
                    TipUpvote.tip_id.in_([tip.id for tip, _ in rows]),
                )
            )
        )
        bands = Counter(tip.weekly_hours for tip, _ in rows)
        resources: dict[tuple[str | None, str | None, str], int] = Counter()
        for tip, _ in rows:
            for item in tip.resources:
                key = (item.get("url"), item.get("material_id"), str(item.get("title", "")))
                resources[key] += 1
        return SubjectTipsOut(
            subject_id=str(subject.id),
            subject_name=subject.name_az,
            subject_code=subject.code,
            tip_count=len(rows),
            average_difficulty=round(sum(tip.difficulty for tip, _ in rows) / len(rows), 1)
            if rows
            else None,
            workload=[
                WorkloadOut(weekly_hours=band, count=bands[band])
                for band in WeeklyHours
                if bands[band]
            ],
            resources=[
                AggregatedResourceOut(title=title, url=url, material_id=material, mentions=count)
                for (url, material, title), count in sorted(
                    resources.items(), key=lambda item: (-item[1], item[0][2])
                )[:20]
            ],
            tips=[
                TipOut(
                    id=str(tip.id),
                    semester=term_label(semester),
                    difficulty=tip.difficulty,
                    weekly_hours=tip.weekly_hours,
                    key_topics=tip.key_topics,
                    resources=_resources(tip),
                    exam_advice=tip.exam_advice,
                    retrospective=tip.retrospective,
                    upvotes=tip.upvotes,
                    upvoted=tip.id in mine,
                    mine=tip.author_id == user.id,
                    updated_at=tip.updated_at,
                )
                for tip, semester in rows[:TOP_TIPS]
            ],
        )

    async def _readable_tip(self, user: CurrentUser, tip_id: uuid.UUID) -> CourseTip:
        tip = await self.session.get(CourseTip, tip_id)
        if tip is None or tip.status is not TipStatus.PUBLISHED:
            raise AppError("tips.not_found", 404)
        try:
            await readable_subject(self.session, user, tip.subject_id, "tips.not_found")
        except AppError as exc:
            raise AppError("tips.not_found", 404) from exc
        return tip

    async def upvote(self, user: CurrentUser, tip_id: uuid.UUID, on: bool) -> int:
        """Idempotent either way; the counter moves only when a row was really added or removed, so concurrent
        clicks keep it exact. Authors cannot upvote their own card (D-084)."""
        tip = await self._readable_tip(user, tip_id)
        if tip.author_id == user.id:
            raise AppError("tips.own_tip", 422)
        if on:
            changed = await self.session.scalar(
                insert(TipUpvote)
                .values(tip_id=tip_id, user_id=user.id)
                .on_conflict_do_nothing()
                .returning(TipUpvote.tip_id)
            )
            delta = 1
        else:
            changed = await self.session.scalar(
                delete(TipUpvote)
                .where(TipUpvote.tip_id == tip_id, TipUpvote.user_id == user.id)
                .returning(TipUpvote.tip_id)
            )
            delta = -1
        if changed is not None:
            await self.session.execute(
                update(CourseTip)
                .where(CourseTip.id == tip_id)
                .values(upvotes=CourseTip.upvotes + delta)
            )
        await self.session.commit()
        count = await self.session.scalar(select(CourseTip.upvotes).where(CourseTip.id == tip_id))
        return count or 0

    # --- moderation -------------------------------------------------------------------------------------------

    async def moderation_page(
        self, status: TipStatus | None, offset: int, limit: int
    ) -> tuple[list[TipModerationOut], int]:
        query = select(CourseTip, Subject, Semester, User).join(
            Subject, Subject.id == CourseTip.subject_id
        )
        query = query.join(Semester, Semester.id == CourseTip.semester_taken_id).outerjoin(
            User, User.id == CourseTip.author_id
        )
        count_query = select(func.count()).select_from(CourseTip)
        if status is not None:
            query = query.where(CourseTip.status == status)
            count_query = count_query.where(CourseTip.status == status)
        total = await self.session.scalar(count_query) or 0
        rows = list(
            await self.session.execute(
                query.order_by(CourseTip.updated_at.asc()).offset(offset).limit(limit)
            )
        )
        reports = dict(
            (
                await self.session.execute(
                    select(Report.target_id, func.count())
                    .where(
                        Report.target_type == ReportTarget.TIP,
                        Report.target_id.in_([str(tip.id) for tip, *_ in rows]),
                    )
                    .group_by(Report.target_id)
                )
            ).all()
        )
        return [
            TipModerationOut(
                id=str(tip.id),
                subject_name=subject.name_az,
                semester=term_label(semester),
                author_name=author.display_name if author else None,
                status=tip.status,
                difficulty=tip.difficulty,
                weekly_hours=tip.weekly_hours,
                key_topics=tip.key_topics,
                resources=_resources(tip),
                exam_advice=tip.exam_advice,
                retrospective=tip.retrospective,
                moderation_note=tip.moderation_note,
                upvotes=tip.upvotes,
                reports=reports.get(str(tip.id), 0),
                updated_at=tip.updated_at,
            )
            for tip, subject, semester, author in rows
        ], total

    async def review(
        self, actor: CurrentUser, tip_id: uuid.UUID, status: TipStatus, note: str
    ) -> None:
        """Approve, reject, hide or restore (publish again); nothing is deleted."""
        if status is TipStatus.PENDING:
            raise AppError("tips.invalid_status", 422)
        tip = await self.session.get(CourseTip, tip_id, with_for_update=True)
        if tip is None:
            raise AppError("tips.not_found", 404)
        tip.status = status
        tip.moderation_note = note.strip()
        tip.reviewed_by = actor.id
        tip.reviewed_at = utc_now()
        record_audit(
            self.session,
            AuditAction.TIP_REVIEWED,
            actor_id=actor.id,
            target_type="tip",
            target_id=tip.id,
            details={"status": status.value},
        )
        await self.session.commit()

    # --- jobs -------------------------------------------------------------------------------------------------

    async def prompt_authors(self) -> int:
        """Asks people who passed a subject in a semester that ended in the last 90 days for a card, once per
        subject and semester (§5.2 "at semester end")."""
        today = baku_today()
        recent = list(
            await self.session.execute(
                select(Subject.id, Subject.name_az, Semester.id)
                .select_from(CourseOffering)
                .join(Subject, Subject.id == CourseOffering.subject_id)
                .join(Semester, Semester.id == CourseOffering.semester_id)
                .where(Semester.ends_on < today, Semester.ends_on >= today - PROMPT_WINDOW)
                .distinct()
            )
        )
        sent = 0
        for subject_id, subject_name, semester_id in recent:
            recipients = (
                select(Enrollment.user_id)
                .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
                .where(
                    CourseOffering.subject_id == subject_id,
                    CourseOffering.semester_id == semester_id,
                    Enrollment.status == EnrollmentStatus.COMPLETED,
                    Enrollment.passed.is_(True),
                    ~exists().where(
                        CourseTip.author_id == Enrollment.user_id,
                        CourseTip.subject_id == subject_id,
                        CourseTip.semester_taken_id == semester_id,
                    ),
                )
            )
            sent += await Notifier(self.session).notify(
                recipients,
                NotificationSpec(
                    category=NotificationCategory.MENTORSHIP,
                    kind=NotificationKind.MENTORSHIP_TIP_PROMPT,
                    subject_type="mentor_invitation",
                    subject_id=subject_id,
                    dedupe_key=f"tips.prompt:{subject_id}:{semester_id}",
                    title=subject_name,
                    link=f"/guides/tips/{subject_id}?semester={semester_id}",
                ),
                deliver=False,
            )
        await self.session.commit()
        return sent
