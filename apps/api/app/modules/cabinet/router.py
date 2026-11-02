from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.deps import JobsDep, RedisDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.cabinet.schemas import (
    AppealListOut,
    ConflictListOut,
    SyncRequestedOut,
    SyncRunListOut,
    TranscriptOut,
)
from app.modules.cabinet.service import MANAGE, CabinetReadService
from app.modules.users.service import CurrentUser

# Grades are personal data (§5.4): the screens need a few reads per visit, not a feed to scrape.
READS = RateLimit("cabinet_read", limit=60, window_seconds=300)
SYNC_REQUESTS = RateLimit("cabinet_sync_request", limit=6, window_seconds=3600)

# Under /me/transcript, so the offline policy of the service worker already refuses to store it (D-117).
student_router = APIRouter(
    prefix="/me/transcript", tags=["cabinet"], responses=COMMON_ERROR_RESPONSES
)
staff_router = APIRouter(prefix="/cabinet", tags=["cabinet"], responses=COMMON_ERROR_RESPONSES)

Manager = Annotated[CurrentUser, Depends(require_permission(MANAGE))]


def get_reader(session: SessionDep) -> CabinetReadService:
    return CabinetReadService(session)


Reader = Annotated[CabinetReadService, Depends(get_reader)]


def _never_cached(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@student_router.get(
    "",
    response_model=TranscriptOut,
    operation_id="readMyTranscript",
    summary="My transcript from the personal cabinet mirror",
)
async def my_transcript(
    user: CurrentUserDep,
    reader: Reader,
    session: SessionDep,
    redis: RedisDep,
    response: Response,
) -> TranscriptOut:
    await enforce_rate_limit(redis, READS, str(user.id))
    _never_cached(response)
    result = await reader.transcript(user.id)
    # Which kind of data was read, not what it said.
    record_audit(
        session,
        AuditAction.CABINET_VIEWED,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        details={"kind": "transcript"},
    )
    await session.commit()
    return result


@student_router.get(
    "/appeals",
    response_model=AppealListOut,
    operation_id="listMyAppeals",
    summary="The status of my appeals, from the personal cabinet mirror",
)
async def my_appeals(
    user: CurrentUserDep,
    reader: Reader,
    session: SessionDep,
    redis: RedisDep,
    response: Response,
) -> AppealListOut:
    await enforce_rate_limit(redis, READS, str(user.id))
    _never_cached(response)
    result = await reader.appeals(user.id)
    record_audit(
        session,
        AuditAction.CABINET_VIEWED,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        details={"kind": "appeals"},
    )
    await session.commit()
    return result


@staff_router.get(
    "/sync-runs",
    response_model=SyncRunListOut,
    operation_id="listCabinetSyncRuns",
    summary="Recent personal cabinet sync runs: outcome and counts only",
)
async def sync_runs(_: Manager, reader: Reader, response: Response) -> SyncRunListOut:
    _never_cached(response)
    return await reader.runs()


@staff_router.post(
    "/sync-runs",
    status_code=202,
    response_model=SyncRequestedOut,
    operation_id="requestCabinetSync",
    summary="Start a personal cabinet sync now",
)
async def request_sync(
    user: Manager, session: SessionDep, redis: RedisDep, jobs: JobsDep
) -> SyncRequestedOut:
    await enforce_rate_limit(redis, SYNC_REQUESTS, str(user.id))
    record_audit(session, AuditAction.CABINET_SYNC_REQUESTED, actor_id=user.id)
    await session.commit()
    await jobs.sync_cabinet(str(user.id))
    return SyncRequestedOut(queued=True)


@staff_router.get(
    "/conflicts",
    response_model=ConflictListOut,
    operation_id="listCabinetConflicts",
    summary="Courses where the registry and the cabinet mirror disagree, without any grade",
)
async def conflicts(
    user: Manager, reader: Reader, session: SessionDep, response: Response
) -> ConflictListOut:
    _never_cached(response)
    items = await reader.conflicts()
    record_audit(
        session,
        AuditAction.CABINET_CONFLICTS_VIEWED,
        actor_id=user.id,
        details={"count": len(items)},
    )
    await session.commit()
    return ConflictListOut(items=items)
