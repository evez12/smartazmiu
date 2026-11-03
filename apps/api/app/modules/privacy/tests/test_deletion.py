import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import Base
from app.modules import load_models
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.audit.service import record_audit
from app.modules.community.models import FeedPost
from app.modules.privacy.deletion import (
    PLACEHOLDER_NAME,
    REFERENCES,
    DeletionNotConfiguredError,
    Handling,
    purge_database,
    references_to_users,
    subject_hash,
)
from app.modules.privacy.models import (
    AccountDeletion,
    ConsentPurpose,
    ConsentRecord,
    DeletionReason,
)
from app.modules.users.models import Role, User, UserRole, UserStatus

PEPPER = "test-deletion-pepper-0123456789abcdef"


def test_every_reference_to_users_has_a_decision() -> None:
    """A table added later that points at users must be listed in REFERENCES, or the build fails."""
    load_models()

    in_schema = references_to_users(Base.metadata)
    assert in_schema - REFERENCES.keys() == set(), "decide what deletion does to these columns"
    assert REFERENCES.keys() - in_schema == set(), "stale entries in REFERENCES"


async def test_registry_agrees_with_the_database_rules(db: AsyncSession) -> None:
    """The ON DELETE rule is the safety net under the registry: anonymized columns are SET NULL."""
    rows = await db.execute(
        text(
            "SELECT c.conrelid::regclass::text, a.attname, c.confdeltype"
            " FROM pg_constraint c"
            " JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]"
            " WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass"
            " AND NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhrelid = c.conrelid)"
        )
    )
    rules = {f"{table}.{column}": bytes(rule).decode() for table, column, rule in rows}
    for reference, handling in REFERENCES.items():
        if handling in {Handling.ANONYMIZED, Handling.AUDIT}:
            assert rules[reference] == "n", reference  # SET NULL
        if handling is Handling.PERSONAL:
            assert rules[reference] in {"c", "a"}, reference  # CASCADE, or refused today


def test_subject_hash_is_keyed_and_stable() -> None:
    person = uuid.uuid4()
    digest = subject_hash(person, PEPPER)
    assert digest == subject_hash(person, PEPPER)
    assert len(digest) == 64
    assert str(person) not in digest
    assert digest != subject_hash(person, PEPPER + "x")
    assert digest != subject_hash(uuid.uuid4(), PEPPER)
    with pytest.raises(DeletionNotConfiguredError):
        subject_hash(person, "")


def test_production_refuses_a_short_pepper() -> None:
    with pytest.raises(ValueError, match="DELETION_PEPPER"):
        Settings(
            app_env="production",
            ticket_secret="t",
            attendance_secret="a",
            deletion_pepper="short",
            cabinet_provider="azmiu",
            cabinet_api_url="https://cabinet.example",
            cabinet_api_key="key",
        )


def _person(name: str, email: str, university_id: str) -> User:
    return User(
        idp_subject=f"kc-{uuid.uuid4()}",
        email=email,
        university_id=university_id,
        given_name=name,
        family_name="Məmmədova",
        display_name=f"{name} Məmmədova",
        search_key=f"{name} mammadova".lower(),
        bio="Mən 765a2 qrupunda oxuyuram",
        photo_key="avatars/abc",
        locale="az",
    )


def _request(person: User, reason: DeletionReason = DeletionReason.SELF_SERVICE) -> AccountDeletion:
    return AccountDeletion(
        subject_hash=subject_hash(person.id, PEPPER),
        user_id=person.id,
        reason=reason,
        purge_due_at=datetime.now(UTC),
    )


async def test_purge_leaves_a_tombstone_and_hashes_the_audit_trail(
    db: AsyncSession, settings: Settings
) -> None:
    aysel = _person("Aysel", "aysel.mammadova@smartazmiu.test", "2025076501")
    orxan = _person("Orxan", "orxan.rzayev@smartazmiu.test", "2025076502")
    db.add_all([aysel, orxan])
    role = Role(code="purge-test-role")
    db.add(role)
    await db.flush()
    db.add_all(
        [
            UserRole(user_id=aysel.id, role_id=role.id),
            UserRole(user_id=orxan.id, role_id=role.id),
            ConsentRecord(user_id=aysel.id, purpose=ConsentPurpose.PRIVACY_NOTICE, granted=True),
            ConsentRecord(user_id=orxan.id, purpose=ConsentPurpose.PRIVACY_NOTICE, granted=True),
            FeedPost(author_id=aysel.id, body="Sabah kollokvium var"),
        ]
    )
    record_audit(
        db, AuditAction.ROLES_CHANGED, actor_id=aysel.id, target_type="user", target_id=orxan.id
    )
    record_audit(
        db,
        AuditAction.ROLES_CHANGED,
        actor_id=orxan.id,
        target_type="user",
        target_id=aysel.id,
        details={"before": [], "after": [], "user": str(aysel.id)},
    )
    now = datetime.now(UTC)
    aysel.status = UserStatus.PENDING_DELETION
    aysel.deleted_at, aysel.purge_at = now - timedelta(days=30), now
    deletion = _request(aysel)
    db.add(deletion)
    await db.commit()

    counts = await purge_database(db, deletion, settings)
    await db.commit()

    assert counts is not None
    assert counts.deleted >= 2  # the role and the consent record
    await db.refresh(aysel)
    assert aysel.status is UserStatus.DELETED
    assert aysel.display_name == PLACEHOLDER_NAME
    assert (aysel.email, aysel.university_id, aysel.idp_subject, aysel.photo_key) == (None,) * 4
    assert (aysel.given_name, aysel.family_name, aysel.bio, aysel.search_key) == ("",) * 4
    assert aysel.purge_at is None
    assert deletion.database_purged_at is not None

    # Personal rows are gone, content others read stays without an author, the other person is untouched.
    assert list(await db.scalars(select(UserRole.user_id))) == [orxan.id]
    assert list(await db.scalars(select(ConsentRecord.user_id))) == [orxan.id]
    post = await db.scalar(select(FeedPost))
    assert post is not None
    assert (post.author_id, post.body) == (None, "Sabah kollokvium var")
    await db.refresh(orxan)
    assert orxan.email == "orxan.rzayev@smartazmiu.test"

    # The audit trail holds the keyed hash, not the id.
    digest = subject_hash(aysel.id, PEPPER)
    entries = list(await db.scalars(select(AuditLog).order_by(AuditLog.occurred_at)))
    by_actor = next(entry for entry in entries if entry.actor_hash == digest)
    assert by_actor.actor_id is None
    by_target = next(entry for entry in entries if entry.target_type == "deleted_user")
    assert by_target.target_id == digest
    assert by_target.details["user"] == digest
    dump = " ".join(f"{e.actor_id} {e.target_id} {e.details}" for e in entries)
    assert str(aysel.id) not in dump


async def test_purge_database_runs_once(db: AsyncSession, settings: Settings) -> None:
    person = _person("Nigar", "nigar.aliyeva@smartazmiu.test", "2025076503")
    db.add(person)
    await db.flush()
    deletion = _request(person, DeletionReason.STAFF)
    db.add(deletion)
    await db.commit()

    first = await purge_database(db, deletion, settings)
    second = await purge_database(db, deletion, settings)

    assert first is not None
    assert second is None  # a retry after a later step failed neither repeats nor fails


async def test_purge_needs_the_pepper(db: AsyncSession, settings: Settings) -> None:
    person = _person("Elvin", "elvin.hasanov@smartazmiu.test", "2025076504")
    db.add(person)
    await db.flush()
    deletion = _request(person)
    db.add(deletion)
    await db.commit()

    with pytest.raises(DeletionNotConfiguredError):
        await purge_database(db, deletion, settings.model_copy(update={"deletion_pepper": ""}))
    await db.rollback()
    await db.refresh(person)
    assert person.status is UserStatus.ACTIVE  # nothing was changed
