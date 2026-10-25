import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.deps import RedisDep, SessionDep, StorageDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep
from app.core.time import baku_today
from app.modules.privacy.export import DataExportService
from app.modules.privacy.models import ConsentRecord
from app.modules.privacy.schemas import ConsentRecordOut, MyConsentsOut, NoticeAcknowledgement
from app.modules.privacy.service import PRIVACY_NOTICE_VERSION, ConsentService

EXPORTS = RateLimit("data_export", limit=5, window_seconds=3600)

router = APIRouter(tags=["privacy"], responses=COMMON_ERROR_RESPONSES)


def _consents(session: SessionDep) -> ConsentService:
    return ConsentService(session)


Consents = Annotated[ConsentService, Depends(_consents)]


@router.get(
    "/me/consents",
    response_model=MyConsentsOut,
    operation_id="readMyConsents",
    summary="My consents and the privacy notice status",
)
async def read_my_consents(user: CurrentUserDep, consents: Consents) -> MyConsentsOut:
    return await _my_consents(user.id, consents)


@router.post(
    "/me/consents/privacy-notice",
    response_model=MyConsentsOut,
    operation_id="acknowledgePrivacyNotice",
    summary="Acknowledge the current privacy notice",
)
async def acknowledge_privacy_notice(
    user: CurrentUserDep, consents: Consents, body: NoticeAcknowledgement
) -> MyConsentsOut:
    await consents.acknowledge_notice(user.id, body.version)
    return await _my_consents(user.id, consents)


@router.get(
    "/me/export",
    response_class=Response,
    operation_id="exportMyData",
    summary="Download everything stored about me (JSON)",
    responses={200: {"content": {"application/json": {}}, "description": "Personal data export"}},
)
async def export_my_data(
    user: CurrentUserDep, session: SessionDep, storage: StorageDep, redis: RedisDep
) -> Response:
    await enforce_rate_limit(redis, EXPORTS, str(user.id))
    document = await DataExportService(session, storage).export(user.id)
    file_name = f"smartazmiu-melumatlarim-{baku_today().isoformat()}.json"
    return Response(
        content=json.dumps(document, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Cache-Control": "no-store",
        },
    )


async def _my_consents(user_id: uuid.UUID, consents: ConsentService) -> MyConsentsOut:
    history = await consents.history(user_id)
    acknowledged = await consents.acknowledged_notice(user_id)
    return MyConsentsOut(
        notice_version=PRIVACY_NOTICE_VERSION,
        notice_acknowledged_at=acknowledged.recorded_at if acknowledged else None,
        history=[_record_out(record) for record in history],
    )


def _record_out(record: ConsentRecord) -> ConsentRecordOut:
    return ConsentRecordOut(
        purpose=record.purpose,
        granted=record.granted,
        policy_version=record.policy_version,
        recorded_at=record.recorded_at,
    )
