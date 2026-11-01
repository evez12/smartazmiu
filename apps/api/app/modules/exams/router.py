import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import RedisDep, SessionDep, StorageDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.core.time import utc_now
from app.modules.chat.bus import ChatBus
from app.modules.exams import ics
from app.modules.exams.papers import PastPaperService
from app.modules.exams.schemas import (
    ExamModeIn,
    ExamModeSubjectListOut,
    ExamModeSubjectOut,
    ExamSlotIn,
    ExamSlotListOut,
    ExamSlotOut,
    ExamSlotUpdateIn,
    PaperDownloadOut,
    PaperFormOut,
    PaperIn,
    PaperListOut,
    PaperOut,
    PaperReviewIn,
    PaperSubjectListOut,
    PaperUploadIn,
    PaperUploadOut,
)
from app.modules.exams.service import MANAGE, ExamService
from app.modules.users.service import CurrentUser

router = APIRouter(prefix="/exams", tags=["exams"], responses=COMMON_ERROR_RESPONSES)

Manager = Annotated[CurrentUser, Depends(require_permission(MANAGE))]


def get_exams(session: SessionDep, cache: RedisDep) -> ExamService:
    return ExamService(session, ChatBus(cache))


def get_papers(session: SessionDep, storage: StorageDep, cache: RedisDep) -> PastPaperService:
    return PastPaperService(session, storage, cache)


ExamsDep = Annotated[ExamService, Depends(get_exams)]
PapersDep = Annotated[PastPaperService, Depends(get_papers)]


@router.get(
    "/mine",
    response_model=ExamSlotListOut,
    operation_id="listMyExams",
    summary="Upcoming exams of the courses I attend or teach",
)
async def my_exams(user: CurrentUserDep, service: ExamsDep) -> ExamSlotListOut:
    return ExamSlotListOut(items=await service.my_exams(user))


@router.get(
    "/mine.ics",
    response_class=Response,
    operation_id="exportMyExams",
    summary="My upcoming exams as an iCalendar file",
    responses={200: {"content": {"text/calendar": {}}, "description": "iCalendar"}},
)
async def my_exams_ics(user: CurrentUserDep, service: ExamsDep) -> Response:
    return Response(
        content=ics.calendar(await service.my_exams(user), utc_now()),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="imtahan-cedveli.ics"'},
    )


@router.get(
    "/slots",
    response_model=ExamSlotListOut,
    operation_id="listExamSlots",
    summary="Every exam slot, with the exams it collides with",
)
async def list_slots(
    _: Manager,
    service: ExamsDep,
    include_past: Annotated[bool, Query()] = False,
) -> ExamSlotListOut:
    return ExamSlotListOut(items=await service.all_exams(include_past=include_past))


@router.post(
    "/slots",
    response_model=ExamSlotOut,
    status_code=201,
    operation_id="createExamSlot",
    summary="Add an exam slot",
)
async def create_slot(user: Manager, service: ExamsDep, body: ExamSlotIn) -> ExamSlotOut:
    return await service.create(user, body)


@router.put(
    "/slots/{slot_id}",
    response_model=ExamSlotOut,
    operation_id="updateExamSlot",
    summary="Change the time or room of an exam slot",
)
async def update_slot(
    user: Manager, service: ExamsDep, slot_id: uuid.UUID, body: ExamSlotUpdateIn
) -> ExamSlotOut:
    return await service.update(user, slot_id, body)


@router.delete(
    "/slots/{slot_id}",
    status_code=204,
    operation_id="deleteExamSlot",
    summary="Remove an exam slot",
)
async def delete_slot(user: Manager, service: ExamsDep, slot_id: uuid.UUID) -> Response:
    await service.remove(user, slot_id)
    return Response(status_code=204)


@router.get(
    "/subjects",
    response_model=ExamModeSubjectListOut,
    operation_id="listExamModeSubjects",
    summary="Subjects with an exam ahead or exam mode switched off",
)
async def exam_mode_subjects(_: Manager, service: ExamsDep) -> ExamModeSubjectListOut:
    return ExamModeSubjectListOut(items=await service.subjects())


@router.put(
    "/subjects/{subject_id}/exam-mode",
    response_model=ExamModeSubjectOut,
    operation_id="setSubjectExamMode",
    summary="Switch exam mode on or off for a subject",
)
async def set_exam_mode(
    user: Manager, service: ExamsDep, subject_id: uuid.UUID, body: ExamModeIn
) -> ExamModeSubjectOut:
    return await service.set_mode(user, subject_id, body.enabled)


@router.get(
    "/papers/subjects",
    response_model=PaperSubjectListOut,
    operation_id="listPastPaperSubjects",
    summary="Subjects whose past papers I may open",
)
async def paper_subjects(user: CurrentUserDep, service: PapersDep) -> PaperSubjectListOut:
    return await service.subjects(user)


@router.get(
    "/papers",
    response_model=PaperListOut,
    operation_id="listPastPapers",
    summary="Past papers of one subject",
)
async def list_papers(
    user: CurrentUserDep, service: PapersDep, subject_id: Annotated[uuid.UUID, Query()]
) -> PaperListOut:
    return await service.papers(user, subject_id)


@router.get(
    "/papers/form",
    response_model=PaperFormOut,
    operation_id="getPastPaperForm",
    summary="The finished semesters a paper of this subject can belong to",
)
async def paper_form(
    user: CurrentUserDep, service: PapersDep, subject_id: Annotated[uuid.UUID, Query()]
) -> PaperFormOut:
    return await service.form(user, subject_id)


@router.post(
    "/papers/uploads/presign",
    response_model=PaperUploadOut,
    operation_id="presignPastPaperUpload",
    summary="Get a short-lived address to upload a paper to",
)
async def presign_paper(
    user: CurrentUserDep, service: PapersDep, body: PaperUploadIn
) -> PaperUploadOut:
    return await service.presign(user, body)


@router.post(
    "/papers",
    response_model=PaperOut,
    status_code=201,
    operation_id="submitPastPaper",
    summary="Save an uploaded paper with its details and the consent",
)
async def submit_paper(user: CurrentUserDep, service: PapersDep, body: PaperIn) -> PaperOut:
    return await service.submit(user, body)


@router.post(
    "/papers/{paper_id}/review",
    response_model=PaperOut,
    operation_id="reviewPastPaper",
    summary="Approve or reject a paper",
)
async def review_paper(
    user: CurrentUserDep, service: PapersDep, paper_id: uuid.UUID, body: PaperReviewIn
) -> PaperOut:
    return await service.review(user, paper_id, body)


@router.get(
    "/papers/{paper_id}/download",
    response_model=PaperDownloadOut,
    operation_id="downloadPastPaper",
    summary="A short-lived address to download a paper from",
)
async def download_paper(
    user: CurrentUserDep, service: PapersDep, paper_id: uuid.UUID
) -> PaperDownloadOut:
    return await service.download(user, paper_id)
