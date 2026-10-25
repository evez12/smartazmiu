import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
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


# Bumped whenever the privacy notice text changes; users are asked to read the new version.
PRIVACY_NOTICE_VERSION = "2026-10"


class ConsentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def history(self, user_id: uuid.UUID) -> list[ConsentRecord]:
        """Newest first."""
        records = await self.session.scalars(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.recorded_at.desc(), ConsentRecord.id.desc())
        )
        return list(records)

    async def acknowledged_notice(self, user_id: uuid.UUID) -> ConsentRecord | None:
        """The acknowledgement of the current notice version, if the user gave one."""
        record: ConsentRecord | None = await self.session.scalar(
            select(ConsentRecord)
            .where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.purpose == ConsentPurpose.PRIVACY_NOTICE,
                ConsentRecord.policy_version == PRIVACY_NOTICE_VERSION,
                ConsentRecord.granted.is_(True),
            )
            .order_by(ConsentRecord.recorded_at.desc())
            .limit(1)
        )
        return record

    async def acknowledge_notice(self, user_id: uuid.UUID, version: str) -> ConsentRecord:
        """Idempotent: acknowledging the same version twice keeps the first record."""
        if version != PRIVACY_NOTICE_VERSION:
            raise AppError("privacy.notice_outdated", 409, {"version": PRIVACY_NOTICE_VERSION})
        existing = await self.acknowledged_notice(user_id)
        if existing is not None:
            return existing
        record = record_consent(
            self.session,
            user_id,
            ConsentPurpose.PRIVACY_NOTICE,
            granted=True,
            policy_version=PRIVACY_NOTICE_VERSION,
        )
        await self.session.commit()
        await self.session.refresh(record)
        return record
