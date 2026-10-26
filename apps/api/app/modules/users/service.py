import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import Uuid, case, delete, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ids import uuid7
from app.core.security import TokenClaims
from app.core.text import search_key
from app.modules.audit.models import AuditAction
from app.modules.audit.service import record_audit
from app.modules.users.models import (
    Permission,
    Role,
    RoleCode,
    RolePermission,
    User,
    UserRole,
    UserStatus,
)

logger = structlog.get_logger(__name__)

# Global roles the identity provider may grant; anything else in the token is ignored.
IDP_MANAGED_ROLES = frozenset(code.value for code in RoleCode if code is not RoleCode.GUEST)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: uuid.UUID
    display_name: str
    given_name: str
    family_name: str
    status: UserStatus
    roles: frozenset[str]
    permissions: frozenset[str]

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    def has_permission(self, code: str) -> bool:
        return code in self.permissions


def user_search_key(user: User) -> str:
    return search_key(user.given_name, user.family_name, user.email, user.university_id)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sync_from_claims(self, claims: TokenClaims) -> CurrentUser:
        """Provision the user on first sign-in and mirror profile and roles from the identity provider.

        Keycloak is authoritative for global role membership (DECISIONS D-016); the database holds the
        role-to-permission bundles. Writes happen only when something changed, so the common path is
        two reads.
        """
        try:
            return await self._sync(claims)
        except IntegrityError:
            await self.session.rollback()
        # A concurrent first request for the same subject can lose the insert race on the e-mail index
        # instead of the subject index; once the winner has committed, the retry takes the update path.
        try:
            return await self._sync(claims)
        except IntegrityError as exc:
            await self.session.rollback()
            # Another account already owns this e-mail: never merge identities silently (§13.1).
            logger.warning("identity_conflict", subject=claims.subject)
            raise AppError("auth.identity_conflict", 409) from exc

    async def _sync(self, claims: TokenClaims) -> CurrentUser:
        user = await self.session.scalar(select(User).where(User.idp_subject == claims.subject))
        if user is None:
            user = await self._link_imported_person(claims)
        if user is None or _profile_differs(user, claims):
            user = await self._upsert_profile(claims)

        desired_roles = claims.roles & IDP_MANAGED_ROLES
        current_roles = await self._role_codes(user.id)
        token_predates_roles = (
            user.roles_synced_at is not None and claims.issued_at < user.roles_synced_at.timestamp()
        )
        if current_roles != desired_roles and not token_predates_roles:
            await self._replace_roles(user.id, desired_roles)
            record_audit(
                self.session,
                AuditAction.ROLES_SYNCED,
                actor_id=None,
                target_type="user",
                target_id=user.id,
                details={
                    "added": sorted(desired_roles - current_roles),
                    "removed": sorted(current_roles - desired_roles),
                },
            )
            current_roles = set(desired_roles)
            # The token's own issue time, not now: another token from the same second is not "older".
            user.roles_synced_at = datetime.fromtimestamp(claims.issued_at, UTC)
        await self.session.commit()

        return CurrentUser(
            id=user.id,
            display_name=user.display_name,
            given_name=user.given_name,
            family_name=user.family_name,
            status=user.status,
            roles=frozenset(current_roles),
            permissions=await self._permission_codes(user.id),
        )

    async def current(self, user_id: uuid.UUID) -> CurrentUser | None:
        """The account as stored now, for connections that outlive the request that authenticated them."""
        user = await self.session.get(User, user_id, populate_existing=True)
        if user is None:
            return None
        return CurrentUser(
            id=user.id,
            display_name=user.display_name,
            given_name=user.given_name,
            family_name=user.family_name,
            status=user.status,
            roles=frozenset(await self._role_codes(user.id)),
            permissions=await self._permission_codes(user.id),
        )

    async def _link_imported_person(self, claims: TokenClaims) -> User | None:
        """Attach a first sign-in to the person imported with the same verified e-mail (D-029).

        The conditional update makes concurrent first requests safe: only one of them sees the row
        without a subject; the others fall through to the upsert, which then finds the linked row.
        """
        if not claims.email or not claims.email_verified:
            return None
        user = await self.session.scalar(
            update(User)
            .where(User.email == claims.email, User.idp_subject.is_(None))
            .values(idp_subject=claims.subject)
            .returning(User)
            .execution_options(populate_existing=True)
        )
        if user is not None:
            record_audit(
                self.session,
                AuditAction.ACCOUNT_LINKED,
                actor_id=None,
                target_type="user",
                target_id=user.id,
            )
            logger.info("account_linked", user_id=str(user.id))
        return user

    async def _upsert_profile(self, claims: TokenClaims) -> User:
        names = {
            "given_name": claims.given_name,
            "family_name": claims.family_name,
            "display_name": claims.display_name,
        }
        insert_user = insert(User).values(
            id=uuid7(),
            idp_subject=claims.subject,
            email=claims.email,
            search_key=search_key(claims.given_name, claims.family_name, claims.email),
            **names,
        )
        # Names of people in the university registry come from the academic import, not the token.
        registry_managed = User.university_id.is_not(None)
        upsert = insert_user.on_conflict_do_update(
            index_elements=[User.idp_subject],
            set_={
                "email": insert_user.excluded.email,
                **{
                    column: case(
                        (registry_managed, getattr(User, column)),
                        else_=getattr(insert_user.excluded, column),
                    )
                    for column in names
                },
            },
        ).returning(User)
        user = await self.session.scalar(upsert.execution_options(populate_existing=True))
        assert user is not None
        expected_key = user_search_key(user)
        if user.search_key != expected_key:
            user.search_key = expected_key
            await self.session.flush()
        return user

    async def _role_codes(self, user_id: uuid.UUID) -> set[str]:
        rows = await self.session.scalars(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return set(rows)

    async def _replace_roles(self, user_id: uuid.UUID, codes: frozenset[str]) -> None:
        role_ids = select(Role.id).where(Role.code.in_(codes))
        await self.session.execute(
            delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id.not_in(role_ids))
        )
        if codes:
            await self.session.execute(
                insert(UserRole)
                .from_select(
                    ["user_id", "role_id"],
                    select(literal(user_id, Uuid()), Role.id).where(Role.code.in_(codes)),
                )
                .on_conflict_do_nothing()
            )

    async def _permission_codes(self, user_id: uuid.UUID) -> frozenset[str]:
        rows = await self.session.scalars(
            select(Permission.code)
            .distinct()
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
        )
        return frozenset(rows)


def _profile_differs(user: User, claims: TokenClaims) -> bool:
    if user.email != claims.email:
        return True
    if user.university_id is not None:
        return False
    return (user.given_name, user.family_name, user.display_name) != (
        claims.given_name,
        claims.family_name,
        claims.display_name,
    )
