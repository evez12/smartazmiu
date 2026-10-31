import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import JobsDep, RedisDep, SessionDep, StorageDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep
from app.modules.assignments.schemas import (
    AssignmentCreateIn,
    AssignmentDetailOut,
    AssignmentGradeIn,
    AssignmentListOut,
    AssignmentPresignIn,
    AssignmentPresignOut,
    AssignmentSubmissionIn,
    CourseOfferingListOut,
    FileDownloadOut,
    SubmissionDetailOut,
    SubmissionListOut,
)
from app.modules.assignments.service import AssignmentService

router = APIRouter(tags=["assignments"], responses=COMMON_ERROR_RESPONSES)


def get_assignments(
    session: SessionDep, storage: StorageDep, cache: RedisDep, jobs: JobsDep
) -> AssignmentService:
    return AssignmentService(session, storage, cache, jobs)


AssignmentsDep = Annotated[AssignmentService, Depends(get_assignments)]


@router.get(
    "/coursework/offerings",
    response_model=CourseOfferingListOut,
    operation_id="listCourseworkOfferings",
    summary="Offerings I may add assignments and quizzes to",
)
async def list_offerings(user: CurrentUserDep, service: AssignmentsDep) -> CourseOfferingListOut:
    return CourseOfferingListOut(items=await service.offerings_for_creation(user))


@router.get("/assignments", response_model=AssignmentListOut, operation_id="listAssignments")
async def list_assignments(
    user: CurrentUserDep,
    service: AssignmentsDep,
    offering_id: Annotated[uuid.UUID | None, Query()] = None,
) -> AssignmentListOut:
    return AssignmentListOut(items=await service.assignments(user, offering_id))


@router.post(
    "/assignments",
    response_model=AssignmentDetailOut,
    status_code=201,
    operation_id="createAssignment",
)
async def create_assignment(
    user: CurrentUserDep, service: AssignmentsDep, body: AssignmentCreateIn
) -> AssignmentDetailOut:
    return await service.create(user, body)


@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentDetailOut,
    operation_id="getAssignment",
)
async def get_assignment(
    user: CurrentUserDep, service: AssignmentsDep, assignment_id: uuid.UUID
) -> AssignmentDetailOut:
    return await service.detail(user, assignment_id)


@router.post(
    "/assignments/{assignment_id}/uploads/presign",
    response_model=AssignmentPresignOut,
    operation_id="presignAssignmentUpload",
    summary="Reserve a submission upload: a ten-minute URL to PUT one file to (25 MB)",
)
async def presign_upload(
    user: CurrentUserDep,
    service: AssignmentsDep,
    assignment_id: uuid.UUID,
    body: AssignmentPresignIn,
) -> AssignmentPresignOut:
    return await service.presign(user, assignment_id, body.filename, body.mime, body.size)


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=AssignmentDetailOut,
    status_code=201,
    operation_id="submitAssignment",
    summary="Submit the uploaded file; sending the same upload again returns the same result",
)
async def submit_assignment(
    user: CurrentUserDep,
    service: AssignmentsDep,
    assignment_id: uuid.UUID,
    body: AssignmentSubmissionIn,
) -> AssignmentDetailOut:
    return await service.submit(user, assignment_id, body.upload_id)


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionListOut,
    operation_id="listAssignmentSubmissions",
    summary="Every student of the offering with their submission, for the people who manage it",
)
async def list_submissions(
    user: CurrentUserDep, service: AssignmentsDep, assignment_id: uuid.UUID
) -> SubmissionListOut:
    return SubmissionListOut(items=await service.submissions(user, assignment_id))


@router.get(
    "/assignment-submissions/{submission_id}",
    response_model=SubmissionDetailOut,
    operation_id="getAssignmentSubmission",
)
async def get_submission(
    user: CurrentUserDep, service: AssignmentsDep, submission_id: uuid.UUID
) -> SubmissionDetailOut:
    return await service.submission(user, submission_id)


@router.post(
    "/assignment-submissions/{submission_id}/grade",
    response_model=SubmissionDetailOut,
    operation_id="gradeAssignmentSubmission",
)
async def grade_submission(
    user: CurrentUserDep,
    service: AssignmentsDep,
    submission_id: uuid.UUID,
    body: AssignmentGradeIn,
) -> SubmissionDetailOut:
    return await service.grade(user, submission_id, body)


@router.get(
    "/assignment-files/{file_id}/download",
    response_model=FileDownloadOut,
    operation_id="downloadAssignmentFile",
    summary="A one-minute link to a scanned submission file",
)
async def download_file(
    user: CurrentUserDep,
    service: AssignmentsDep,
    file_id: uuid.UUID,
    inline: bool = False,
) -> FileDownloadOut:
    return await service.download(user, file_id, inline=inline)
