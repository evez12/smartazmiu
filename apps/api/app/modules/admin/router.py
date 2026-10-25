import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import IdentityAdminDep, SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import require_permission
from app.modules.academics.schemas import PersonRef
from app.modules.admin.schemas import (
    AdminUserDetail,
    AdminUserOut,
    AdminUserPageOut,
    AuditEntryOut,
    AuditPageOut,
    RoleAssignment,
)
from app.modules.admin.service import AssignableRole, UserAdminService, UserRow
from app.modules.audit.models import AuditAction
from app.modules.audit.service import AuditEntry, AuditFilter, AuditLogService
from app.modules.users.models import UserStatus
from app.modules.users.service import CurrentUser

USERS_READ = "admin.users.read"
ROLES_ASSIGN = "admin.roles.assign"
AUDIT_READ = "admin.audit.read"
RECENT_ACTIVITY = 20

router = APIRouter(prefix="/admin", tags=["admin"], responses=COMMON_ERROR_RESPONSES)
UserReader = Annotated[CurrentUser, Depends(require_permission(USERS_READ))]
RoleAssigner = Annotated[CurrentUser, Depends(require_permission(ROLES_ASSIGN))]
AuditReader = Annotated[CurrentUser, Depends(require_permission(AUDIT_READ))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/users", response_model=AdminUserPageOut, operation_id="listUsers", summary="Users")
async def list_users(
    _: UserReader,
    session: SessionDep,
    q: Annotated[
        str | None, Query(max_length=100, description="Name, e-mail or university ID")
    ] = None,
    role: AssignableRole | None = None,
    status: UserStatus | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
) -> AdminUserPageOut:
    page = await UserAdminService(session).page(
        query=q, role=role, status=status, offset=offset, limit=limit
    )
    return AdminUserPageOut(items=[_user_out(row) for row in page.items], total=page.total)


@router.get(
    "/users/{user_id}", response_model=AdminUserDetail, operation_id="readUser", summary="User"
)
async def read_user(actor: UserReader, session: SessionDep, user_id: uuid.UUID) -> AdminUserDetail:
    return await _detail(session, actor, await UserAdminService(session).get(user_id))


@router.put(
    "/users/{user_id}/roles",
    response_model=AdminUserDetail,
    operation_id="setUserRoles",
    summary="Replace a user's global roles",
    responses={503: COMMON_ERROR_RESPONSES[500] | {"description": "Identity provider unavailable"}},
)
async def set_user_roles(
    actor: RoleAssigner,
    session: SessionDep,
    identity: IdentityAdminDep,
    user_id: uuid.UUID,
    body: RoleAssignment,
) -> AdminUserDetail:
    row = await UserAdminService(session).set_roles(actor, user_id, set(body.roles), identity)
    return await _detail(session, actor, row)


@router.get(
    "/audit-logs", response_model=AuditPageOut, operation_id="listAuditLogs", summary="Audit log"
)
async def list_audit_logs(
    _: AuditReader,
    session: SessionDep,
    action: AuditAction | None = None,
    actor_id: uuid.UUID | None = None,
    target_id: Annotated[str | None, Query(max_length=64)] = None,
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    offset: Offset = 0,
    limit: Limit = 50,
) -> AuditPageOut:
    filters = AuditFilter(
        action=action,
        actor_id=actor_id,
        target_id=target_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    page = await AuditLogService(session).page(filters, offset=offset, limit=limit)
    return AuditPageOut(items=[_audit_out(entry) for entry in page.items], total=page.total)


async def _detail(session: SessionDep, actor: CurrentUser, row: UserRow) -> AdminUserDetail:
    activity: list[AuditEntryOut] = []
    if actor.has_permission(AUDIT_READ):
        page = await AuditLogService(session).page(
            AuditFilter(target_id=str(row.user.id)), offset=0, limit=RECENT_ACTIVITY
        )
        activity = [_audit_out(entry) for entry in page.items]
    return AdminUserDetail(**_user_out(row).model_dump(), recent_activity=activity)


def _user_out(row: UserRow) -> AdminUserOut:
    user = row.user
    return AdminUserOut(
        id=str(user.id),
        display_name=user.display_name,
        email=user.email,
        university_id=user.university_id,
        person_type=user.person_type,
        group_code=row.group_code,
        roles=row.roles,
        status=user.status,
        linked=user.idp_subject is not None,
        created_at=user.created_at,
    )


def _audit_out(entry: AuditEntry) -> AuditEntryOut:
    log = entry.log
    return AuditEntryOut(
        id=str(log.id),
        occurred_at=log.occurred_at,
        action=AuditAction(log.action),
        actor=PersonRef(id=str(log.actor_id), display_name=entry.actor_name or "")
        if log.actor_id
        else None,
        target_type=log.target_type,
        target_id=log.target_id,
        target_label=entry.target_label,
        details=log.details,
        request_id=log.request_id,
    )
