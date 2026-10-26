import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import RedisDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.chat.deps import ChannelsDep
from app.modules.mentorship.schemas import (
    EligibleSubjectOut,
    FeedbackNotePageOut,
    GuideDirectoryOut,
    GuideProfileIn,
    GuideProfilePatch,
    MentorFeedbackIn,
    MentorRequestIn,
    MentorRequestListOut,
    MentorRequestOut,
    MyGuideProfileOut,
)
from app.modules.mentorship.service import MentorshipService
from app.modules.users.service import CurrentUser

router = APIRouter(tags=["mentorship"], responses=COMMON_ERROR_RESPONSES)
# Private feedback notes go to the same staff who read reports (§5.2).
ReportReader = Annotated[CurrentUser, Depends(require_permission("admin.reports.read"))]


def get_mentorship(session: SessionDep, cache: RedisDep) -> MentorshipService:
    return MentorshipService(session, cache)


MentorshipDep = Annotated[MentorshipService, Depends(get_mentorship)]


def _uuid(value: str, code: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise AppError(code, 404) from exc


@router.get(
    "/guides/eligible",
    response_model=list[EligibleSubjectOut],
    operation_id="listGuideEligibility",
    summary="Subjects I may guide (past, passed, not retaking)",
)
async def eligible(user: CurrentUserDep, mentorship: MentorshipDep) -> list[EligibleSubjectOut]:
    return await mentorship.eligible_subjects(user)


@router.get(
    "/guides/me",
    response_model=list[MyGuideProfileOut],
    operation_id="listMyGuideProfiles",
    summary="My active guide profiles with their stats",
)
async def my_profiles(user: CurrentUserDep, mentorship: MentorshipDep) -> list[MyGuideProfileOut]:
    return await mentorship.guide_stats(user.id)


@router.get(
    "/subjects/{subject_id}/guides",
    response_model=GuideDirectoryOut,
    operation_id="listSubjectGuides",
    summary="Available guides of a subject, ranked (§5.2)",
)
async def guides(
    user: CurrentUserDep,
    mentorship: MentorshipDep,
    subject_id: uuid.UUID,
    specialty: uuid.UUID | None = None,
    semester: uuid.UUID | None = None,
    teacher: uuid.UUID | None = None,
) -> GuideDirectoryOut:
    return await mentorship.directory(user, subject_id, specialty, semester, teacher)


@router.get(
    "/subjects/{subject_id}/guides/me",
    response_model=MyGuideProfileOut,
    operation_id="getMyGuideProfile",
    summary="My guide profile for a subject",
)
async def get_my_profile(
    user: CurrentUserDep, mentorship: MentorshipDep, subject_id: uuid.UUID
) -> MyGuideProfileOut:
    return await mentorship.my_profile(user, subject_id)


@router.post(
    "/subjects/{subject_id}/guides/me",
    response_model=MyGuideProfileOut,
    operation_id="optInAsGuide",
    summary="Become a guide for a subject (eligibility and consent checked)",
)
async def opt_in(
    user: CurrentUserDep, mentorship: MentorshipDep, subject_id: uuid.UUID, body: GuideProfileIn
) -> MyGuideProfileOut:
    return await mentorship.opt_in(user, subject_id, body)


@router.patch(
    "/subjects/{subject_id}/guides/me",
    response_model=MyGuideProfileOut,
    operation_id="updateMyGuideProfile",
    summary="Change my guide profile",
)
async def update_my_profile(
    user: CurrentUserDep,
    mentorship: MentorshipDep,
    subject_id: uuid.UUID,
    body: GuideProfilePatch,
) -> MyGuideProfileOut:
    return await mentorship.update_profile(user, subject_id, body)


@router.get(
    "/mentor-requests",
    response_model=MentorRequestListOut,
    operation_id="listMentorRequests",
    summary="My advice requests, as requester or guide; or those of one DM",
)
async def list_requests(
    user: CurrentUserDep, mentorship: MentorshipDep, channel_id: uuid.UUID | None = None
) -> MentorRequestListOut:
    return MentorRequestListOut(items=await mentorship.requests(user, channel_id))


@router.post(
    "/mentor-requests",
    response_model=MentorRequestOut,
    status_code=201,
    operation_id="createMentorRequest",
    summary="Ask a guide, or any guide of the subject, for advice",
)
async def create_request(
    user: CurrentUserDep, mentorship: MentorshipDep, body: MentorRequestIn
) -> MentorRequestOut:
    return await mentorship.create_request(
        user,
        _uuid(body.subject_id, "mentorship.subject_not_found"),
        _uuid(body.mentor_id, "mentorship.guide_unavailable") if body.mentor_id else None,
        body.topic,
        body.body,
    )


@router.post(
    "/mentor-requests/{request_id}/accept",
    response_model=MentorRequestOut,
    operation_id="acceptMentorRequest",
    summary="Accept a request and open the DM with the requester",
)
async def accept(
    user: CurrentUserDep, mentorship: MentorshipDep, channels: ChannelsDep, request_id: uuid.UUID
) -> MentorRequestOut:
    return await mentorship.accept(user, request_id, channels)


@router.post(
    "/mentor-requests/{request_id}/decline",
    response_model=MentorRequestOut,
    operation_id="declineMentorRequest",
    summary="Decline a request addressed to me",
)
async def decline(
    user: CurrentUserDep, mentorship: MentorshipDep, request_id: uuid.UUID
) -> MentorRequestOut:
    return await mentorship.decline(user, request_id)


@router.post(
    "/mentor-requests/{request_id}/resolve",
    response_model=MentorRequestOut,
    operation_id="resolveMentorRequest",
    summary="Mark an accepted request as resolved",
)
async def resolve(
    user: CurrentUserDep, mentorship: MentorshipDep, request_id: uuid.UUID
) -> MentorRequestOut:
    return await mentorship.resolve(user, request_id)


@router.post(
    "/mentor-requests/{request_id}/feedback",
    response_model=MentorRequestOut,
    operation_id="giveMentorFeedback",
    summary="Rate a resolved request once (requester only)",
)
async def feedback(
    user: CurrentUserDep, mentorship: MentorshipDep, request_id: uuid.UUID, body: MentorFeedbackIn
) -> MentorRequestOut:
    return await mentorship.give_feedback(user, request_id, body.feedback, body.note)


@router.get(
    "/moderation/mentor-feedback",
    response_model=FeedbackNotePageOut,
    operation_id="listMentorFeedbackNotes",
    summary="Private feedback notes on guides, newest first",
)
async def feedback_notes(
    _: ReportReader,
    mentorship: MentorshipDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FeedbackNotePageOut:
    items, total = await mentorship.feedback_notes(offset, limit)
    return FeedbackNotePageOut(items=items, total=total)
