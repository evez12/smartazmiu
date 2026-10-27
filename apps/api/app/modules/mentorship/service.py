"""Guides and advice requests (§5.2, D-004, D-083).

Request state machine: open → accepted → resolved; open → declined; open → expired (72 h). Accepting locks the
request row and then the guide's profile row, so two accepts of one request, or accepts that would push a guide
past ``max_open_requests``, are serialised: only one wins.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.time import BAKU, utc_now
from app.modules.academics.models import (
    AcademicGroup,
    CourseOffering,
    CourseOfferingTeacher,
    Enrollment,
    EnrollmentStatus,
    Semester,
    Specialty,
    Subject,
)
from app.modules.chat.channels import ChannelService
from app.modules.chat.models import Channel, ChannelTopic, ChannelType, Message, UserBlock
from app.modules.mentorship.badges import term_label
from app.modules.mentorship.eligibility import eligible_pairs, qualification
from app.modules.mentorship.models import (
    Availability,
    GradeVisibility,
    MentorProfile,
    MentorRequest,
    RequestFeedback,
    RequestStatus,
    RequestTopic,
)
from app.modules.mentorship.schemas import (
    EligibleSubjectOut,
    FeedbackNoteOut,
    FilterOptionOut,
    GradeRange,
    GuideDirectoryOut,
    GuideOut,
    GuideProfileIn,
    GuideProfilePatch,
    GuideStatsOut,
    MentorPersonOut,
    MentorRequestOut,
    MyGuideProfileOut,
)
from app.modules.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationKind,
)
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.users.models import User, UserStatus
from app.modules.users.profile import photo_url
from app.modules.users.service import CurrentUser

logger = structlog.get_logger(__name__)

EXPIRES_AFTER = timedelta(hours=72)
REQUEST_LIMIT = RateLimit("mentor_request", limit=10, window_seconds=3600)
ADVICE_DAILY_CAP = 5
ADVICE_WINDOW = timedelta(hours=6)
STAFF_ROLES = frozenset({"staff", "admin"})
SUBJECT_TYPE_INVITATION = "mentor_invitation"
SUBJECT_TYPE_REQUEST = "mentor_request"
SUBJECT_TYPE_ADVICE = "advice_post"


def person(user: User) -> MentorPersonOut:
    return MentorPersonOut(
        id=str(user.id), display_name=user.display_name, photo_url=photo_url(user)
    )


def stats(profile: MentorProfile) -> GuideStatsOut:
    rated = profile.helpful_count + profile.unhelpful_count
    return GuideStatsOut(
        helped_count=profile.helped_count,
        helpful_count=profile.helpful_count,
        unhelpful_count=profile.unhelpful_count,
        helpful_rate=round(profile.helpful_count / rated, 3) if rated else None,
        avg_response_minutes=profile.avg_response_minutes,
    )


def grade_range(grade: int | None) -> GradeRange | None:
    if grade is None or grade < 51:
        return None
    if grade <= 70:
        return "51-70"
    if grade <= 90:
        return "71-90"
    return "91-100"


def active_guide(user_id: Any, subject_id: Any) -> ColumnElement[bool]:
    return exists().where(
        MentorProfile.user_id == user_id,
        MentorProfile.subject_id == subject_id,
        MentorProfile.revoked_at.is_(None),
    )


def _blocked_either(a: Any, b: Any) -> ColumnElement[bool]:
    return exists().where(
        or_(
            and_(UserBlock.blocker_id == a, UserBlock.blocked_id == b),
            and_(UserBlock.blocker_id == b, UserBlock.blocked_id == a),
        )
    )


def _load(mentor_id: Any) -> Select[int]:
    """Requests a guide is carrying: accepted ones (live conversations)."""
    return select(func.count()).where(
        MentorRequest.mentor_id == mentor_id, MentorRequest.status == RequestStatus.ACCEPTED
    )


def _addressed_open(mentor_id: Any) -> Select[int]:
    return select(func.count()).where(
        MentorRequest.mentor_id == mentor_id,
        MentorRequest.status.in_([RequestStatus.OPEN, RequestStatus.ACCEPTED]),
    )


@dataclass(frozen=True, slots=True)
class SyncReport:
    revoked: int
    closed_requests: int
    invited: int


async def readable_subject(
    session: AsyncSession, user: CurrentUser, subject_id: uuid.UUID, not_found: str
) -> Subject:
    """The subject if the person studies it (any enrollment that is not dropped), guides it, or is staff;
    otherwise the same 404 as an unknown subject (§14)."""
    subject = await session.get(Subject, subject_id)
    if subject is None:
        raise AppError(not_found, 404)
    if user.roles & STAFF_ROLES:
        return subject
    enrolled = exists(
        select(Enrollment.id)
        .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
        .where(
            Enrollment.user_id == user.id,
            CourseOffering.subject_id == subject_id,
            Enrollment.status != EnrollmentStatus.DROPPED,
        )
    )
    if not await session.scalar(select(or_(enrolled, active_guide(user.id, subject_id)))):
        raise AppError(not_found, 404)
    return subject


class MentorshipService:
    def __init__(self, session: AsyncSession, cache: Redis | None = None) -> None:
        self.session = session
        self.cache = cache

    # --- access ---------------------------------------------------------------------------------------------

    async def _subject(self, user: CurrentUser, subject_id: uuid.UUID) -> Subject:
        return await readable_subject(
            self.session, user, subject_id, "mentorship.subject_not_found"
        )

    # --- guides -----------------------------------------------------------------------------------------------

    async def eligible_subjects(self, user: CurrentUser) -> list[EligibleSubjectOut]:
        query = eligible_pairs()
        pairs = query.where(query.selected_columns[0] == user.id).subquery()
        subject_ids = list(await self.session.scalars(select(pairs.c.subject_id)))
        out: list[EligibleSubjectOut] = []
        for subject_id in subject_ids:
            found = await qualification(self.session, user.id, subject_id)
            subject = await self.session.get(Subject, subject_id)
            semester = await self.session.get(Semester, found.semester_id) if found else None
            if found is None or subject is None or semester is None:
                continue
            teacher = await self.session.get(User, found.teacher_id) if found.teacher_id else None
            profile = await self._profile(user.id, subject_id)
            out.append(
                EligibleSubjectOut(
                    subject_id=str(subject_id),
                    subject_code=subject.code,
                    subject_name=subject.name_az,
                    semester=term_label(semester),
                    teacher_name=teacher.display_name if teacher else None,
                    grade=found.grade,
                    opted_in=profile is not None and profile.revoked_at is None,
                )
            )
        return sorted(out, key=lambda item: item.subject_name)

    async def _profile(self, user_id: uuid.UUID, subject_id: uuid.UUID) -> MentorProfile | None:
        return await self.session.scalar(
            select(MentorProfile).where(
                MentorProfile.user_id == user_id, MentorProfile.subject_id == subject_id
            )
        )

    async def opt_in(
        self, user: CurrentUser, subject_id: uuid.UUID, body: GuideProfileIn
    ) -> MyGuideProfileOut:
        """Becomes a guide for the subject: explicit consent and eligibility checked now (§5.2)."""
        if not body.consent:
            raise AppError("mentorship.consent_required", 422)
        found = await qualification(self.session, user.id, subject_id)
        if found is None:
            raise AppError("mentorship.not_eligible", 403)
        profile = await self._profile(user.id, subject_id)
        if profile is None:
            profile = MentorProfile(user_id=user.id, subject_id=subject_id)
            self.session.add(profile)
        profile.semester_taken_id = found.semester_id
        profile.teacher_taken_with_id = found.teacher_id
        profile.grade_visibility = body.grade_visibility
        profile.show_teacher = body.show_teacher
        profile.bio = body.bio.strip()
        profile.availability = body.availability
        profile.max_open_requests = body.max_open_requests
        profile.consented_at = utc_now()
        profile.revoked_at = None
        await self.session.commit()
        return await self.my_profile(user, subject_id)

    async def update_profile(
        self, user: CurrentUser, subject_id: uuid.UUID, body: GuideProfilePatch
    ) -> MyGuideProfileOut:
        profile = await self._profile(user.id, subject_id)
        if profile is None or profile.revoked_at is not None:
            raise AppError("mentorship.profile_not_found", 404)
        for field in ("grade_visibility", "show_teacher", "availability", "max_open_requests"):
            value = getattr(body, field)
            if value is not None:
                setattr(profile, field, value)
        if body.bio is not None:
            profile.bio = body.bio.strip()
        await self.session.commit()
        return await self.my_profile(user, subject_id)

    async def my_profile(self, user: CurrentUser, subject_id: uuid.UUID) -> MyGuideProfileOut:
        profile = await self._profile(user.id, subject_id)
        if profile is None:
            raise AppError("mentorship.profile_not_found", 404)
        subject = await self.session.get(Subject, subject_id)
        semester = await self.session.get(Semester, profile.semester_taken_id)
        assert subject is not None
        assert semester is not None
        return MyGuideProfileOut(
            subject_id=str(subject_id),
            subject_name=subject.name_az,
            semester=term_label(semester),
            grade_visibility=profile.grade_visibility,
            show_teacher=profile.show_teacher,
            bio=profile.bio,
            availability=profile.availability,
            max_open_requests=profile.max_open_requests,
            active=profile.revoked_at is None,
            stats=stats(profile),
        )

    async def directory(
        self,
        user: CurrentUser,
        subject_id: uuid.UUID,
        specialty_id: uuid.UUID | None = None,
        semester_id: uuid.UUID | None = None,
        teacher_id: uuid.UUID | None = None,
    ) -> GuideDirectoryOut:
        """Available guides, ranked: same teacher, same specialty, most recent semester, helpful rate (§5.2)."""
        subject = await self._subject(user, subject_id)
        my_teachers = set(
            await self.session.scalars(
                select(CourseOfferingTeacher.teacher_id)
                .join(CourseOffering, CourseOffering.id == CourseOfferingTeacher.course_offering_id)
                .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
                .where(
                    Enrollment.user_id == user.id,
                    CourseOffering.subject_id == subject_id,
                    Enrollment.status != EnrollmentStatus.DROPPED,
                )
            )
        )
        my_specialty = await self.session.scalar(
            select(AcademicGroup.specialty_id)
            .join(User, User.academic_group_id == AcademicGroup.id)
            .where(User.id == user.id)
        )
        teacher = aliased(User)
        rows = await self.session.execute(
            select(MentorProfile, User, Semester, teacher, Specialty, func.max(Enrollment.grade))
            .join(User, User.id == MentorProfile.user_id)
            .join(Semester, Semester.id == MentorProfile.semester_taken_id)
            .outerjoin(teacher, teacher.id == MentorProfile.teacher_taken_with_id)
            .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
            .outerjoin(Specialty, Specialty.id == AcademicGroup.specialty_id)
            .outerjoin(
                CourseOffering,
                and_(
                    CourseOffering.subject_id == MentorProfile.subject_id,
                    CourseOffering.semester_id == MentorProfile.semester_taken_id,
                ),
            )
            .outerjoin(
                Enrollment,
                and_(
                    Enrollment.course_offering_id == CourseOffering.id,
                    Enrollment.user_id == MentorProfile.user_id,
                    Enrollment.passed.is_(True),
                ),
            )
            .where(
                MentorProfile.subject_id == subject_id,
                MentorProfile.revoked_at.is_(None),
                MentorProfile.availability == Availability.AVAILABLE,
                MentorProfile.user_id != user.id,
                User.status == UserStatus.ACTIVE,
                ~_blocked_either(MentorProfile.user_id, user.id),
            )
            .group_by(MentorProfile.id, User.id, Semester.id, teacher.id, Specialty.id)
        )
        guides: list[tuple[tuple[bool, bool, int, float, str], GuideOut]] = []
        specialties: dict[str, str] = {}
        semesters: dict[str, tuple[date, str]] = {}
        teachers: dict[str, str] = {}
        for profile, guide, semester, taught_by, specialty, grade in rows:
            shown_teacher = taught_by if profile.show_teacher else None
            if specialty is not None:
                specialties[str(specialty.id)] = specialty.name_az
            semesters[str(semester.id)] = (semester.ends_on, term_label(semester))
            if shown_teacher is not None:
                teachers[str(shown_teacher.id)] = shown_teacher.display_name
            if specialty_id and (specialty is None or specialty.id != specialty_id):
                continue
            if semester_id and semester.id != semester_id:
                continue
            if teacher_id and (shown_teacher is None or shown_teacher.id != teacher_id):
                continue
            same_teacher = profile.teacher_taken_with_id in my_teachers
            same_specialty = specialty is not None and specialty.id == my_specialty
            out_stats = stats(profile)
            out = GuideOut(
                user=person(guide),
                semester=term_label(semester),
                semester_id=str(semester.id),
                teacher_name=shown_teacher.display_name if shown_teacher else None,
                teacher_id=str(shown_teacher.id) if shown_teacher else None,
                specialty_name=specialty.name_az if specialty else None,
                specialty_id=str(specialty.id) if specialty else None,
                grade_exact=grade if profile.grade_visibility is GradeVisibility.EXACT else None,
                grade_range=grade_range(grade)
                if profile.grade_visibility is GradeVisibility.RANGE
                else None,
                bio=profile.bio,
                availability=profile.availability,
                same_teacher=same_teacher,
                same_specialty=same_specialty,
                stats=out_stats,
            )
            key = (
                not same_teacher,
                not same_specialty,
                -semester.ends_on.toordinal(),
                -(out_stats.helpful_rate or 0.0),
                guide.display_name,
            )
            guides.append((key, out))
        guides.sort(key=lambda item: item[0])
        return GuideDirectoryOut(
            subject_id=str(subject.id),
            subject_name=subject.name_az,
            subject_code=subject.code,
            guides=[guide for _, guide in guides],
            specialties=[
                FilterOptionOut(id=key, label=label) for key, label in sorted(specialties.items())
            ],
            semesters=[
                FilterOptionOut(id=key, label=label)
                for key, (_, label) in sorted(
                    semesters.items(), key=lambda item: item[1][0], reverse=True
                )
            ],
            teachers=[FilterOptionOut(id=key, label=label) for key, label in teachers.items()],
            i_am_guide=bool(await self.session.scalar(select(active_guide(user.id, subject_id)))),
        )

    async def guide_stats(self, user_id: uuid.UUID) -> list[MyGuideProfileOut]:
        """A person's active guide profiles with their stats, for their profile page."""
        rows = await self.session.execute(
            select(MentorProfile, Subject, Semester)
            .join(Subject, Subject.id == MentorProfile.subject_id)
            .join(Semester, Semester.id == MentorProfile.semester_taken_id)
            .where(MentorProfile.user_id == user_id, MentorProfile.revoked_at.is_(None))
            .order_by(Subject.name_az)
        )
        return [
            MyGuideProfileOut(
                subject_id=str(subject.id),
                subject_name=subject.name_az,
                semester=term_label(semester),
                grade_visibility=profile.grade_visibility,
                show_teacher=profile.show_teacher,
                bio=profile.bio,
                availability=profile.availability,
                max_open_requests=profile.max_open_requests,
                active=True,
                stats=stats(profile),
            )
            for profile, subject, semester in rows
        ]

    # --- requests ---------------------------------------------------------------------------------------------

    async def create_request(
        self,
        user: CurrentUser,
        subject_id: uuid.UUID,
        mentor_id: uuid.UUID | None,
        topic: RequestTopic,
        body: str,
    ) -> MentorRequestOut:
        await self._subject(user, subject_id)
        if not body.strip():
            raise AppError("mentorship.body_required", 422)
        if self.cache is not None:
            await enforce_rate_limit(self.cache, REQUEST_LIMIT, str(user.id))
        if mentor_id is not None:
            if mentor_id == user.id:
                raise AppError("mentorship.self_request", 422)
            profile = await self.session.scalar(
                select(MentorProfile).where(
                    MentorProfile.user_id == mentor_id,
                    MentorProfile.subject_id == subject_id,
                    MentorProfile.revoked_at.is_(None),
                )
            )
            # A block either way reads like an unavailable guide, so it cannot be inferred (D-062).
            blocked = await self.session.scalar(select(_blocked_either(mentor_id, user.id)))
            if profile is None or blocked:
                raise AppError("mentorship.guide_unavailable", 409)
            carried = await self.session.scalar(_addressed_open(mentor_id)) or 0
            if (
                profile.availability is not Availability.AVAILABLE
                or carried >= profile.max_open_requests
            ):
                raise AppError("mentorship.guide_unavailable", 409)
        request = MentorRequest(
            subject_id=subject_id,
            requester_id=user.id,
            mentor_id=mentor_id,
            topic=topic,
            body=body.strip(),
        )
        self.session.add(request)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError("mentorship.request_exists", 409) from exc
        recipients: Select[uuid.UUID]
        if mentor_id is not None:
            recipients = select(User.id).where(User.id == mentor_id)
        else:
            # Unaddressed: every available guide of the subject may take it (D-004).
            recipients = select(MentorProfile.user_id).where(
                MentorProfile.subject_id == subject_id,
                MentorProfile.revoked_at.is_(None),
                MentorProfile.availability == Availability.AVAILABLE,
                MentorProfile.user_id != user.id,
                ~_blocked_either(MentorProfile.user_id, user.id),
            )
        subject = await self.session.get(Subject, subject_id)
        assert subject is not None
        await Notifier(self.session).notify(
            recipients,
            NotificationSpec(
                category=NotificationCategory.MENTORSHIP,
                kind=NotificationKind.MENTORSHIP_REQUEST_RECEIVED,
                subject_type=SUBJECT_TYPE_REQUEST,
                subject_id=request.id,
                dedupe_key=f"mentorship.request:{request.id}",
                title=subject.name_az,
                link="/guides/requests",
            ),
        )
        await self.session.commit()
        return await self.request_out(user, request.id)

    async def _locked_request(self, request_id: uuid.UUID) -> MentorRequest:
        request = await self.session.scalar(
            select(MentorRequest).where(MentorRequest.id == request_id).with_for_update()
        )
        if request is None:
            raise AppError("mentorship.request_not_found", 404)
        return request

    async def accept(
        self, user: CurrentUser, request_id: uuid.UUID, channels: ChannelService
    ) -> MentorRequestOut:
        request = await self._locked_request(request_id)
        if request.status is not RequestStatus.OPEN:
            if request.requester_id == user.id or request.mentor_id == user.id:
                raise AppError("mentorship.request_closed", 409)
            raise AppError("mentorship.request_not_found", 404)
        if request.mentor_id is not None and request.mentor_id != user.id:
            raise AppError("mentorship.request_not_found", 404)
        # The profile row serialises accepts by the same guide, so capacity is never exceeded.
        profile = await self.session.scalar(
            select(MentorProfile)
            .where(
                MentorProfile.user_id == user.id,
                MentorProfile.subject_id == request.subject_id,
                MentorProfile.revoked_at.is_(None),
            )
            .with_for_update()
        )
        if profile is None or request.requester_id == user.id:
            raise AppError("mentorship.request_not_found", 404)
        if await qualification(self.session, user.id, request.subject_id) is None:
            raise AppError("mentorship.not_eligible", 403)
        if profile.availability is not Availability.AVAILABLE:
            raise AppError("mentorship.not_available", 409)
        if (await self.session.scalar(_load(user.id)) or 0) >= profile.max_open_requests:
            raise AppError("mentorship.capacity_reached", 409)
        if await self.session.scalar(select(_blocked_either(user.id, request.requester_id))):
            raise AppError("mentorship.request_not_found", 404)
        now = utc_now()
        request.mentor_id = user.id
        request.status = RequestStatus.ACCEPTED
        request.accepted_at = now
        request.dm_channel_id = await channels.ensure_dm(user.id, request.requester_id)
        minutes = max(0, int((now - request.created_at).total_seconds() // 60))
        accepted_before = (
            await self.session.scalar(
                select(func.count()).where(
                    MentorRequest.mentor_id == user.id, MentorRequest.accepted_at.is_not(None)
                )
            )
            or 0
        )
        previous = profile.avg_response_minutes
        # Running mean over every accepted request (this one is already counted by the query above).
        profile.avg_response_minutes = (
            minutes
            if previous is None or accepted_before <= 1
            else round(previous + (minutes - previous) / accepted_before)
        )
        subject = await self.session.get(Subject, request.subject_id)
        assert subject is not None
        await Notifier(self.session).notify(
            select(User.id).where(User.id == request.requester_id),
            NotificationSpec(
                category=NotificationCategory.MENTORSHIP,
                kind=NotificationKind.MENTORSHIP_REQUEST_ACCEPTED,
                subject_type=SUBJECT_TYPE_REQUEST,
                subject_id=request.id,
                dedupe_key=f"mentorship.accepted:{request.id}",
                title=subject.name_az,
                link=f"/chat/{request.dm_channel_id}",
            ),
        )
        await self.session.commit()
        await channels.bus.membership_changed(
            [(request.dm_channel_id, user.id), (request.dm_channel_id, request.requester_id)], []
        )
        return await self.request_out(user, request.id)

    async def decline(self, user: CurrentUser, request_id: uuid.UUID) -> MentorRequestOut:
        request = await self._locked_request(request_id)
        if request.mentor_id != user.id:
            raise AppError("mentorship.request_not_found", 404)
        if request.status is not RequestStatus.OPEN:
            raise AppError("mentorship.request_closed", 409)
        request.status = RequestStatus.DECLINED
        request.closed_at = utc_now()
        subject = await self.session.get(Subject, request.subject_id)
        assert subject is not None
        await Notifier(self.session).notify(
            select(User.id).where(User.id == request.requester_id),
            NotificationSpec(
                category=NotificationCategory.MENTORSHIP,
                kind=NotificationKind.MENTORSHIP_REQUEST_DECLINED,
                subject_type=SUBJECT_TYPE_REQUEST,
                subject_id=request.id,
                dedupe_key=f"mentorship.declined:{request.id}",
                title=subject.name_az,
                link="/guides/requests",
            ),
        )
        await self.session.commit()
        return await self.request_out(user, request.id)

    async def resolve(self, user: CurrentUser, request_id: uuid.UUID) -> MentorRequestOut:
        request = await self._locked_request(request_id)
        if user.id not in (request.requester_id, request.mentor_id):
            raise AppError("mentorship.request_not_found", 404)
        if request.status is not RequestStatus.ACCEPTED:
            raise AppError("mentorship.request_closed", 409)
        request.status = RequestStatus.RESOLVED
        request.closed_at = utc_now()
        await self.session.execute(
            update(MentorProfile)
            .where(
                MentorProfile.user_id == request.mentor_id,
                MentorProfile.subject_id == request.subject_id,
            )
            .values(helped_count=MentorProfile.helped_count + 1)
        )
        await self.session.commit()
        return await self.request_out(user, request.id)

    async def give_feedback(
        self, user: CurrentUser, request_id: uuid.UUID, feedback: RequestFeedback, note: str
    ) -> MentorRequestOut:
        """Once, by the requester, after resolution; the conditional update makes a second call a no-op."""
        request = await self.session.get(MentorRequest, request_id)
        if request is None or request.requester_id != user.id:
            raise AppError("mentorship.request_not_found", 404)
        if request.status is not RequestStatus.RESOLVED:
            raise AppError("mentorship.request_not_resolved", 409)
        updated = await self.session.scalar(
            update(MentorRequest)
            .where(MentorRequest.id == request_id, MentorRequest.feedback.is_(None))
            .values(feedback=feedback, feedback_note=note.strip(), feedback_at=utc_now())
            .returning(MentorRequest.id)
        )
        if updated is None:
            raise AppError("mentorship.feedback_exists", 409)
        counter = (
            MentorProfile.helpful_count
            if feedback is RequestFeedback.HELPFUL
            else MentorProfile.unhelpful_count
        )
        await self.session.execute(
            update(MentorProfile)
            .where(
                MentorProfile.user_id == request.mentor_id,
                MentorProfile.subject_id == request.subject_id,
            )
            .values({counter.key: counter + 1})
        )
        await self.session.commit()
        self.session.expire_all()
        return await self.request_out(user, request_id)

    async def requests(
        self, user: CurrentUser, channel_id: uuid.UUID | None = None
    ) -> list[MentorRequestOut]:
        """Mine as requester, as guide, and unaddressed open ones I could take; or those of one DM."""
        mine = or_(MentorRequest.requester_id == user.id, MentorRequest.mentor_id == user.id)
        candidate = and_(
            MentorRequest.status == RequestStatus.OPEN,
            MentorRequest.mentor_id.is_(None),
            MentorRequest.requester_id != user.id,
            active_guide(user.id, MentorRequest.subject_id),
            ~_blocked_either(user.id, MentorRequest.requester_id),
        )
        query = select(MentorRequest.id).order_by(MentorRequest.created_at.desc()).limit(100)
        if channel_id is not None:
            query = query.where(MentorRequest.dm_channel_id == channel_id, mine)
        else:
            query = query.where(or_(mine, candidate))
        return [
            await self.request_out(user, request_id)
            for request_id in await self.session.scalars(query)
        ]

    async def request_out(self, user: CurrentUser, request_id: uuid.UUID) -> MentorRequestOut:
        request = await self.session.get(MentorRequest, request_id, populate_existing=True)
        assert request is not None
        requester = await self.session.get(User, request.requester_id)
        mentor = await self.session.get(User, request.mentor_id) if request.mentor_id else None
        subject = await self.session.get(Subject, request.subject_id)
        assert requester is not None
        assert subject is not None
        role = (
            "requester"
            if request.requester_id == user.id
            else "mentor"
            if request.mentor_id == user.id
            else "candidate"
        )
        is_open = request.status is RequestStatus.OPEN
        return MentorRequestOut(
            id=str(request.id),
            subject_id=str(subject.id),
            subject_name=subject.name_az,
            requester=person(requester),
            mentor=person(mentor) if mentor else None,
            topic=request.topic,
            body=request.body,
            status=request.status,
            dm_channel_id=str(request.dm_channel_id) if request.dm_channel_id else None,
            feedback=request.feedback,
            created_at=request.created_at,
            expires_at=request.created_at + EXPIRES_AFTER if is_open else None,
            role=role,
            can_accept=is_open and role != "requester",
            can_decline=is_open and role == "mentor",
            can_resolve=request.status is RequestStatus.ACCEPTED and role != "candidate",
            can_give_feedback=request.status is RequestStatus.RESOLVED
            and role == "requester"
            and request.feedback is None,
        )

    async def feedback_notes(self, offset: int, limit: int) -> tuple[list[FeedbackNoteOut], int]:
        """Feedback with a private note, newest first, for staff (§5.2)."""
        has_note = and_(MentorRequest.feedback.is_not(None), MentorRequest.feedback_note != "")
        total = await self.session.scalar(select(func.count()).where(has_note)) or 0
        rows = await self.session.execute(
            select(MentorRequest, Subject, User)
            .join(Subject, Subject.id == MentorRequest.subject_id)
            .outerjoin(User, User.id == MentorRequest.mentor_id)
            .where(has_note)
            .order_by(MentorRequest.feedback_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = []
        for request, subject, mentor in rows:
            assert request.feedback is not None
            assert request.feedback_at is not None
            items.append(
                FeedbackNoteOut(
                    request_id=str(request.id),
                    subject_name=subject.name_az,
                    mentor=person(mentor) if mentor else None,
                    feedback=request.feedback,
                    note=request.feedback_note,
                    created_at=request.feedback_at,
                )
            )
        return items, total

    # --- jobs -------------------------------------------------------------------------------------------------

    async def expire(self, now: datetime | None = None) -> int:
        """Open requests older than 72 h become expired; idempotent (§5.2)."""
        now = now or utc_now()
        expired = list(
            await self.session.execute(
                update(MentorRequest)
                .where(
                    MentorRequest.status == RequestStatus.OPEN,
                    MentorRequest.created_at < now - EXPIRES_AFTER,
                )
                .values(status=RequestStatus.EXPIRED, closed_at=now)
                .returning(MentorRequest.id, MentorRequest.requester_id, MentorRequest.subject_id)
            )
        )
        for request_id, requester_id, subject_id in expired:
            subject = await self.session.get(Subject, subject_id)
            await Notifier(self.session).notify(
                select(User.id).where(User.id == requester_id),
                NotificationSpec(
                    category=NotificationCategory.MENTORSHIP,
                    kind=NotificationKind.MENTORSHIP_REQUEST_EXPIRED,
                    subject_type=SUBJECT_TYPE_REQUEST,
                    subject_id=request_id,
                    dedupe_key=f"mentorship.expired:{request_id}",
                    title=subject.name_az if subject else "",
                    link="/guides/requests",
                ),
                deliver=False,
            )
        await self.session.commit()
        return len(expired)

    async def sync(self) -> SyncReport:
        """After results imports: revoke guides who are no longer eligible (closing requests addressed to them that
        are still open), and invite newly eligible people once (§5.2)."""
        eligible = eligible_pairs().subquery()
        still = exists().where(
            eligible.c.user_id == MentorProfile.user_id,
            eligible.c.subject_id == MentorProfile.subject_id,
        )
        now = utc_now()
        revoked = list(
            await self.session.execute(
                update(MentorProfile)
                .where(MentorProfile.revoked_at.is_(None), ~still)
                .values(revoked_at=now)
                .returning(MentorProfile.user_id, MentorProfile.subject_id)
            )
        )
        closed = 0
        for user_id, subject_id in revoked:
            result = await self.session.execute(
                update(MentorRequest)
                .where(
                    MentorRequest.mentor_id == user_id,
                    MentorRequest.subject_id == subject_id,
                    MentorRequest.status == RequestStatus.OPEN,
                )
                .values(status=RequestStatus.DECLINED, closed_at=now)
                .returning(MentorRequest.id)
            )
            closed += len(list(result))
        if revoked:
            logger.info("guides_revoked", count=len(revoked), closed_requests=closed)

        invited = 0
        pending = eligible_pairs().subquery()
        subjects = await self.session.execute(
            select(Subject.id, Subject.name_az)
            .where(Subject.id.in_(select(pending.c.subject_id)))
            .order_by(Subject.code)
        )
        for subject_id, subject_name in subjects:
            fresh = eligible_pairs().subquery()
            recipients = select(fresh.c.user_id).where(
                fresh.c.subject_id == subject_id,
                ~exists().where(
                    MentorProfile.user_id == fresh.c.user_id,
                    MentorProfile.subject_id == subject_id,
                ),
            )
            invited += await Notifier(self.session).notify(
                recipients,
                NotificationSpec(
                    category=NotificationCategory.MENTORSHIP,
                    kind=NotificationKind.MENTORSHIP_INVITATION,
                    subject_type=SUBJECT_TYPE_INVITATION,
                    subject_id=subject_id,
                    dedupe_key=f"mentorship.invitation:{subject_id}",
                    title=subject_name,
                    link=f"/guides/opt-in/{subject_id}",
                ),
            )
        await self.session.commit()
        return SyncReport(len(revoked), closed, invited)

    async def notify_advice_posts(self, now: datetime | None = None) -> int:
        """New unanswered top-level posts in a community's #məsləhət reach the subject's guides, at most five per
        guide per Baku day (§5.2, D-083). Dedupe per post makes reruns harmless."""
        now = now or utc_now()
        since = now - ADVICE_WINDOW
        midnight = now.astimezone(BAKU).replace(hour=0, minute=0, second=0, microsecond=0)
        reply = aliased(Message)
        posts = await self.session.execute(
            select(
                Message.id, Message.created_at, Message.author_id, Channel.subject_id, Channel.id
            )
            .join(Channel, Channel.id == Message.channel_id)
            .join(ChannelTopic, ChannelTopic.id == Message.topic_id)
            .where(
                Channel.type == ChannelType.SUBJECT_COMMUNITY,
                ChannelTopic.slug == "meslehet",
                Message.parent_id.is_(None),
                Message.deleted_at.is_(None),
                Message.created_at >= since,
                ~exists().where(
                    reply.parent_id == Message.id,
                    reply.deleted_at.is_(None),
                    reply.created_at >= since,
                ),
            )
            .order_by(Message.created_at)
        )
        sent = 0
        for message_id, _, author_id, subject_id, channel_id in posts:
            today_count = (
                select(func.count())
                .where(
                    Notification.user_id == MentorProfile.user_id,
                    Notification.kind == NotificationKind.MENTORSHIP_ADVICE_POST,
                    Notification.created_at >= midnight,
                )
                .correlate(MentorProfile)
                .scalar_subquery()
            )
            recipients = select(MentorProfile.user_id).where(
                MentorProfile.subject_id == subject_id,
                MentorProfile.revoked_at.is_(None),
                MentorProfile.availability != Availability.PAUSED,
                MentorProfile.user_id != author_id,
                today_count < ADVICE_DAILY_CAP,
            )
            subject = await self.session.get(Subject, subject_id)
            sent += await Notifier(self.session).notify(
                recipients,
                NotificationSpec(
                    category=NotificationCategory.MENTORSHIP,
                    kind=NotificationKind.MENTORSHIP_ADVICE_POST,
                    subject_type=SUBJECT_TYPE_ADVICE,
                    subject_id=channel_id,
                    dedupe_key=f"mentorship.advice:{message_id}",
                    title=subject.name_az if subject else "",
                    link=f"/chat/{channel_id}",
                ),
            )
            await self.session.flush()
        await self.session.commit()
        return sent


async def still_relevant(session: AsyncSession, subject_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """For the delivery worker: mentorship notices are worth sending while the person is still active."""
    return bool(
        await session.scalar(
            select(exists().where(User.id == user_id, User.status == UserStatus.ACTIVE))
        )
    )
