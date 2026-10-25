from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.academics.schemas import PersonRef
from app.modules.admin.service import AssignableRole
from app.modules.audit.models import AuditAction
from app.modules.users.models import PersonType, UserStatus


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class AuditEntryOut(_Frozen):
    id: str
    occurred_at: datetime
    action: AuditAction
    actor: PersonRef | None
    """None when the system acted (identity-provider sync, seed import)."""
    target_type: str | None
    target_id: str | None
    target_label: str | None
    details: dict[str, Any]
    request_id: str | None


class AuditPageOut(_Frozen):
    items: list[AuditEntryOut]
    total: int


class AdminUserOut(_Frozen):
    """Contact details are included: administering accounts is this screen's purpose (§14)."""

    id: str
    display_name: str
    email: str | None
    university_id: str | None
    person_type: PersonType | None
    group_code: str | None
    roles: list[str]
    status: UserStatus
    linked: bool
    """Whether the person has signed in at least once; roles can only be assigned after that."""
    created_at: datetime


class AdminUserDetail(AdminUserOut):
    recent_activity: list[AuditEntryOut]
    """Latest audit entries about this user; empty without permission to read the audit log."""


class AdminUserPageOut(_Frozen):
    items: list[AdminUserOut]
    total: int


class RoleAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[AssignableRole]
