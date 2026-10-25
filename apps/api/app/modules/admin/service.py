import uuid
from dataclasses import dataclass
from enum import StrEnum

import structlog
from sqlalchemy import Select, Uuid, delete, exists, func, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.identity_admin import IdentityAdmin, IdentityAdminUnavailableError
from app.core.text import like_pattern, normalize_az
from app.core.time import utc_now
from app.modules.academics.models import AcademicGroup
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.users.models import Role, RoleCode, User, UserRole, UserStatus
from app.modules.users.service import CurrentUser

logger = structlog.get_logger(__name__)


class AssignableRole(StrEnum):
    """Global roles an administrator may grant; `guest` is never assigned (§2)."""

    STUDENT = RoleCode.STUDENT.value
    TEACHER = RoleCode.TEACHER.value
    STAFF = RoleCode.STAFF.value
    MODERATOR = RoleCode.MODERATOR.value
    ADMIN = RoleCode.ADMIN.value


ASSIGNABLE_ROLES = frozenset(role.value for role in AssignableRole)


@dataclass(frozen=True, slots=True)
class UserRow:
    user: User
    group_code: str | None
    roles: list[str]


@dataclass(frozen=True, slots=True)
class UserPage:
    items: list[UserRow]
    total: int


class UserAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def page(
        self,
        *,
        query: str | None,
        role: AssignableRole | None,
        status: UserStatus | None,
        offset: int,
        limit: int,
    ) -> UserPage:
        statement: Select[User, str | None] = select(User, AcademicGroup.code).outerjoin(
            AcademicGroup, AcademicGroup.id == User.academic_group_id
        )
        if query and (needle := normalize_az(query).folded):
            # Diacritic-insensitive: "memmedova" finds "Məmmədova" (§13.1).
            statement = statement.where(User.search_key.like(like_pattern(needle), escape="\\"))
        if role is not None:
            statement = statement.where(
                exists()
                .where(UserRole.user_id == User.id, UserRole.role_id == Role.id)
                .where(Role.code == role.value)
            )
        if status is not None:
            statement = statement.where(User.status == status)

        total = await self.session.scalar(select(func.count()).select_from(statement.subquery()))
        rows = (
            await self.session.execute(
                statement.order_by(User.family_name, User.given_name, User.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        roles = await self._roles([user.id for user, _ in rows])
        return UserPage(
            items=[UserRow(user, group_code, roles.get(user.id, [])) for user, group_code in rows],
            total=total or 0,
        )

    async def get(self, user_id: uuid.UUID) -> UserRow:
        row = (
            await self.session.execute(
                select(User, AcademicGroup.code)
                .outerjoin(AcademicGroup, AcademicGroup.id == User.academic_group_id)
                .where(User.id == user_id)
            )
        ).one_or_none()
        if row is None:
            raise AppError("request.not_found", 404)
        user, group_code = row
        return UserRow(user, group_code, (await self._roles([user.id])).get(user.id, []))

    async def set_roles(
        self,
        actor: CurrentUser,
        user_id: uuid.UUID,
        roles: set[AssignableRole],
        identity: IdentityAdmin,
    ) -> UserRow:
        """Write the roles to Keycloak first, then mirror them here and audit the change (D-016, D-028)."""
        user = await self.session.get(User, user_id, with_for_update=True, populate_existing=True)
        if user is None:
            raise AppError("request.not_found", 404)
        if user.idp_subject is None:
            # Imported but never signed in: there is no Keycloak account to give roles to yet.
            raise AppError("admin.user_not_linked", 409)
        desired = {role.value for role in roles}
        if user.id == actor.id and AssignableRole.ADMIN.value not in desired:
            raise AppError("admin.own_admin_role", 409)

        try:
            current = await identity.realm_roles(user.idp_subject) & ASSIGNABLE_ROLES
            added, removed = desired - current, current - desired
            if added or removed:
                await identity.change_realm_roles(user.idp_subject, add=added, remove=removed)
        except IdentityAdminUnavailableError as exc:
            raise AppError("identity.unavailable", 503) from exc

        await self.session.execute(delete(UserRole).where(UserRole.user_id == user.id))
        if desired:
            await self.session.execute(
                insert(UserRole).from_select(
                    ["user_id", "role_id"],
                    select(literal(user.id, Uuid()), Role.id).where(Role.code.in_(desired)),
                )
            )
        user.roles_synced_at = utc_now()
        if added or removed:
            record_audit(
                self.session,
                AuditAction.ROLES_CHANGED,
                actor_id=actor.id,
                target_type="user",
                target_id=user.id,
                details={"added": sorted(added), "removed": sorted(removed)},
            )
            logger.info("roles_changed", target=str(user.id))
        await self.session.commit()
        return await self.get(user.id)

    async def _roles(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
        if not user_ids:
            return {}
        rows = await self.session.execute(
            select(UserRole.user_id, Role.code)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
        )
        order = {code.value: index for index, code in enumerate(RoleCode)}
        result: dict[uuid.UUID, list[str]] = {}
        for user_id, code in rows:
            result.setdefault(user_id, []).append(code)
        return {key: sorted(codes, key=order.__getitem__) for key, codes in result.items()}
