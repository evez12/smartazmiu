import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.core.deps import RedisDep, SessionDep, StorageDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep
from app.modules.users.models import User
from app.modules.users.photos import MAX_UPLOAD_BYTES
from app.modules.users.profile import ProfileChanges, ProfileService, photo_url
from app.modules.users.schemas import MeResponse, ProfileOut, ProfileUpdate

PHOTO_UPLOADS = RateLimit("photo_upload", limit=10, window_seconds=3600)

router = APIRouter(tags=["users"], responses=COMMON_ERROR_RESPONSES)


def _profile_service(session: SessionDep, storage: StorageDep) -> ProfileService:
    return ProfileService(session, storage)


Profiles = Annotated[ProfileService, Depends(_profile_service)]


@router.get("/me", response_model=MeResponse, operation_id="readMe", summary="Signed-in user")
async def read_me(user: CurrentUserDep, profiles: Profiles) -> MeResponse:
    account = await profiles.get(user.id)
    return MeResponse(
        id=str(user.id),
        display_name=user.display_name,
        given_name=user.given_name,
        family_name=user.family_name,
        status=user.status,
        roles=sorted(user.roles),
        permissions=sorted(user.permissions),
        photo_url=photo_url(account),
    )


@router.get(
    "/me/profile", response_model=ProfileOut, operation_id="readMyProfile", summary="My profile"
)
async def read_my_profile(user: CurrentUserDep, profiles: Profiles) -> ProfileOut:
    return _profile_out(await profiles.get(user.id))


@router.patch(
    "/me/profile",
    response_model=ProfileOut,
    operation_id="updateMyProfile",
    summary="Update bio and privacy settings",
)
async def update_my_profile(
    user: CurrentUserDep, profiles: Profiles, body: ProfileUpdate
) -> ProfileOut:
    changes = ProfileChanges(
        version=body.version,
        bio=body.bio,
        dm_policy=body.dm_policy,
        contact_visibility=body.contact_visibility,
    )
    return _profile_out(await profiles.update(user.id, changes))


@router.put(
    "/me/photo",
    response_model=ProfileOut,
    operation_id="uploadMyPhoto",
    summary="Upload a profile photo (JPEG, PNG or WebP)",
    responses={
        413: COMMON_ERROR_RESPONSES[422] | {"description": "Larger than 5 MB"},
        503: COMMON_ERROR_RESPONSES[500] | {"description": "Object storage unavailable"},
    },
)
async def upload_my_photo(
    user: CurrentUserDep,
    profiles: Profiles,
    redis: RedisDep,
    file: Annotated[UploadFile, File()],
) -> ProfileOut:
    await enforce_rate_limit(redis, PHOTO_UPLOADS, str(user.id))
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("photo.too_large", 413)
    return _profile_out(await profiles.set_photo(user.id, data))


@router.delete(
    "/me/photo", response_model=ProfileOut, operation_id="deleteMyPhoto", summary="Remove my photo"
)
async def delete_my_photo(user: CurrentUserDep, profiles: Profiles) -> ProfileOut:
    return _profile_out(await profiles.remove_photo(user.id))


@router.get(
    "/users/{user_id}/photo",
    response_class=Response,
    operation_id="readUserPhoto",
    summary="A user's profile photo",
    responses={200: {"content": {"image/webp": {}}, "description": "512 px WebP"}},
)
async def read_user_photo(_: CurrentUserDep, profiles: Profiles, user_id: uuid.UUID) -> Response:
    key, data = await profiles.photo(user_id)
    return Response(
        content=data,
        media_type="image/webp",
        headers={
            # The URL changes with every new photo (?v=), so the browser may keep this one.
            "Cache-Control": "private, max-age=31536000, immutable",
            "ETag": f'"{key.rsplit("/", 1)[-1]}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


def _profile_out(user: User) -> ProfileOut:
    return ProfileOut(
        id=str(user.id),
        display_name=user.display_name,
        given_name=user.given_name,
        family_name=user.family_name,
        email=user.email,
        university_id=user.university_id,
        person_type=user.person_type,
        bio=user.bio,
        photo_url=photo_url(user),
        dm_policy=user.dm_policy,
        contact_visibility=user.contact_visibility,
        version=user.profile_version,
    )
