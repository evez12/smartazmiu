import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.core.deps import JobsDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep, require_permission
from app.modules.announcements.models import Announcement
from app.modules.announcements.schemas import (
    AnnouncementIn,
    AnnouncementOut,
    AnnouncementPageOut,
    AnnouncementUpdateIn,
    ManagedAnnouncementOut,
    ManagedAnnouncementPageOut,
)
from app.modules.announcements.service import MAX_PAGE, AnnouncementDraft, AnnouncementService
from app.modules.audiences.router import audience_out, parse_audience
from app.modules.audiences.service import Audience, AudienceOption, Audiences
from app.modules.users.service import CurrentUser

PUBLISH_PERMISSION = "announcements.publish"
MANAGED_PAGE_SIZE = 25

router = APIRouter(tags=["announcements"], responses=COMMON_ERROR_RESPONSES)
Publisher = Annotated[CurrentUser, Depends(require_permission(PUBLISH_PERMISSION))]
IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key", max_length=100, description="Repeating it returns the first result"
    ),
]


async def _out(session: SessionDep, items: list[Announcement]) -> list[AnnouncementOut]:
    labels = await Audiences(session).labels([item.audience for item in items])
    return [_announcement_out(item, labels) for item in items]


def _announcement_out(
    item: Announcement, labels: dict[Audience, AudienceOption]
) -> AnnouncementOut:
    return AnnouncementOut(
        id=str(item.id),
        title=item.title,
        body=item.body,
        status=item.status,
        audience=audience_out(item.audience, labels),
        published_at=item.published_at,
        expires_at=item.expires_at,
        version=item.version,
    )


@router.get(
    "/announcements",
    response_model=AnnouncementPageOut,
    operation_id="listMyAnnouncements",
    summary="Active announcements addressed to me, newest first",
)
async def list_my_announcements(
    user: CurrentUserDep,
    session: SessionDep,
    before: Annotated[uuid.UUID | None, Query(description="Cursor from `next_before`")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 20,
) -> AnnouncementPageOut:
    page = await AnnouncementService(session).for_user(user.id, before, limit)
    return AnnouncementPageOut(
        items=await _out(session, page.items),
        next_before=str(page.next_before) if page.next_before else None,
    )


@router.get(
    "/announcements/managed",
    response_model=ManagedAnnouncementPageOut,
    operation_id="listManagedAnnouncements",
    summary="Every announcement with its reach (staff)",
)
async def list_managed_announcements(
    _: Publisher, session: SessionDep, page: Annotated[int, Query(ge=1)] = 1
) -> ManagedAnnouncementPageOut:
    rows, total = await AnnouncementService(session).managed(page, MANAGED_PAGE_SIZE)
    labels = await Audiences(session).labels([item.audience for item, _ in rows])
    return ManagedAnnouncementPageOut(
        items=[
            ManagedAnnouncementOut(
                **_announcement_out(item, labels).model_dump(), recipients=recipients
            )
            for item, recipients in rows
        ],
        total=total,
        page=page,
        page_size=MANAGED_PAGE_SIZE,
    )


@router.get(
    "/announcements/{announcement_id}",
    response_model=AnnouncementOut,
    operation_id="readAnnouncement",
    summary="One announcement addressed to me (staff who publish: any)",
)
async def read_announcement(
    user: CurrentUserDep, session: SessionDep, announcement_id: uuid.UUID
) -> AnnouncementOut:
    item = await AnnouncementService(session).visible(
        announcement_id, user.id, user.has_permission(PUBLISH_PERMISSION)
    )
    return (await _out(session, [item]))[0]


@router.post(
    "/announcements",
    response_model=AnnouncementOut,
    status_code=201,
    operation_id="publishAnnouncement",
    summary="Publish an announcement to an audience and notify it",
)
async def publish_announcement(
    user: Publisher,
    session: SessionDep,
    jobs: JobsDep,
    body: AnnouncementIn,
    idempotency_key: IdempotencyKey = None,
) -> AnnouncementOut:
    draft = AnnouncementDraft(
        title=body.title,
        body=body.body,
        audience=parse_audience(body.audience),
        expires_at=body.expires_at,
    )
    item, created = await AnnouncementService(session).publish(draft, user.id, idempotency_key)
    if created:
        await jobs.dispatch_notifications()
    return (await _out(session, [item]))[0]


@router.patch(
    "/announcements/{announcement_id}",
    response_model=AnnouncementOut,
    operation_id="updateAnnouncement",
    summary="Correct the text or end time (the audience cannot change; nobody is notified again)",
)
async def update_announcement(
    user: Publisher, session: SessionDep, announcement_id: uuid.UUID, body: AnnouncementUpdateIn
) -> AnnouncementOut:
    item = await AnnouncementService(session).update(
        announcement_id,
        body.version,
        title=body.title,
        body=body.body,
        expires_at=body.expires_at,
        actor_id=user.id,
    )
    return (await _out(session, [item]))[0]


@router.post(
    "/announcements/{announcement_id}/archive",
    response_model=AnnouncementOut,
    operation_id="archiveAnnouncement",
    summary="Take an announcement down (idempotent)",
)
async def archive_announcement(
    user: Publisher, session: SessionDep, announcement_id: uuid.UUID
) -> AnnouncementOut:
    item = await AnnouncementService(session).archive(announcement_id, user.id)
    return (await _out(session, [item]))[0]
