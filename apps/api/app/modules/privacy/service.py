import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.privacy.models import ConsentPurpose, ConsentRecord


def record_consent(
    session: AsyncSession,
    user_id: uuid.UUID,
    purpose: ConsentPurpose,
    *,
    granted: bool,
    policy_version: str | None = None,
) -> ConsentRecord:
    """Add a consent record to the caller's transaction, together with the change it permits."""
    record = ConsentRecord(
        user_id=user_id, purpose=purpose, granted=granted, policy_version=policy_version
    )
    session.add(record)
    return record
