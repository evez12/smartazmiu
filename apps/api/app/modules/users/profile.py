import secrets
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.storage import ObjectStorage, StorageUnavailableError
from app.core.time import utc_now
from app.modules.privacy.models import ConsentPurpose
from app.modules.privacy.service import record_consent
from app.modules.users.models import ContactVisibility, DmPolicy, User
from app.modules.users.photos import InvalidPhotoError, normalize_photo

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProfileChanges:
    version: int
    """The profile version the client edited; a newer stored version means someone saved in between."""
    bio: str | None = None
    dm_policy: DmPolicy | None = None
    contact_visibility: ContactVisibility | None = None


def photo_url(user: User) -> str | None:
    """Versioned by the object key, so a new photo gets a new URL and caches never serve the old one."""
    if user.photo_key is None:
        return None
    version = user.photo_key.rsplit("/", 1)[-1].removesuffix(".webp")
    return f"/api/v1/users/{user.id}/photo?v={version}"


class ProfileService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage) -> None:
        self.session = session
        self.storage = storage

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise AppError("request.not_found", 404)
        return user

    async def set_onboarded(self, user_id: uuid.UUID, done: bool) -> None:
        user = await self.get(user_id)
        # The first finish is kept: repeating it does not move the timestamp.
        if done and user.onboarded_at is None:
            user.onboarded_at = utc_now()
        elif not done:
            user.onboarded_at = None
        await self.session.commit()

    async def update(self, user_id: uuid.UUID, changes: ProfileChanges) -> User:
        user = await self._locked(user_id)
        if changes.version != user.profile_version:
            raise AppError("profile.version_conflict", 409, {"version": user.profile_version})
        if changes.bio is not None:
            user.bio = changes.bio.strip()
        if changes.dm_policy is not None:
            user.dm_policy = changes.dm_policy
        visibility = changes.contact_visibility
        if visibility is not None and visibility is not user.contact_visibility:
            # Showing the e-mail to others is a disclosure the user consents to; hiding it withdraws it.
            record_consent(
                self.session,
                user.id,
                ConsentPurpose.CONTACT_SHARING,
                granted=visibility is not ContactVisibility.HIDDEN,
            )
            user.contact_visibility = visibility
        user.profile_version += 1
        await self.session.commit()
        return user

    async def set_photo(self, user_id: uuid.UUID, data: bytes) -> User:
        try:
            image = normalize_photo(data)
        except InvalidPhotoError as exc:
            raise AppError("photo.invalid_image", 422) from exc
        key = f"avatars/{user_id}/{secrets.token_hex(16)}.webp"
        await self._store(key, image)

        user = await self._locked(user_id)
        previous = user.photo_key
        user.photo_key = key
        record_consent(self.session, user.id, ConsentPurpose.PROFILE_PHOTO, granted=True)
        await self.session.commit()
        if previous:
            await self._discard(previous)
        return user

    async def remove_photo(self, user_id: uuid.UUID) -> User:
        user = await self._locked(user_id)
        previous = user.photo_key
        if previous is None:
            # Nothing to remove; committing releases the row lock without expiring the loaded user.
            await self.session.commit()
            return user
        user.photo_key = None
        record_consent(self.session, user.id, ConsentPurpose.PROFILE_PHOTO, granted=False)
        await self.session.commit()
        await self._discard(previous)
        return user

    async def photo(self, user_id: uuid.UUID) -> tuple[str, bytes]:
        user = await self.session.get(User, user_id)
        if user is None or user.photo_key is None:
            raise AppError("request.not_found", 404)
        try:
            data = await self.storage.get(user.photo_key)
        except StorageUnavailableError as exc:
            raise AppError("storage.unavailable", 503) from exc
        if data is None:
            raise AppError("request.not_found", 404)
        return user.photo_key, data

    async def _locked(self, user_id: uuid.UUID) -> User:
        user = await self.session.get(User, user_id, with_for_update=True, populate_existing=True)
        if user is None:
            raise AppError("request.not_found", 404)
        return user

    async def _store(self, key: str, image: bytes) -> None:
        try:
            await self.storage.put(key, image, "image/webp")
        except StorageUnavailableError as exc:
            raise AppError("storage.unavailable", 503) from exc

    async def _discard(self, key: str) -> None:
        # The database no longer points at the object; a failed delete only leaves an orphan behind.
        try:
            await self.storage.delete(key)
        except StorageUnavailableError:
            logger.warning("photo_orphaned")
