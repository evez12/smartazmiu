import io
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimit
from app.modules.privacy.models import ConsentRecord
from app.modules.users import photos
from app.modules.users import router as users_router
from tests.support import MemoryStorage, TokenFactory


@pytest.fixture
def headers(tokens: TokenFactory) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens.issue(str(uuid.uuid4()), ['student'])}"}


def image_bytes(
    image_format: str, size: tuple[int, int] = (800, 600), mode: str = "RGB", **save: Any
) -> bytes:
    image = Image.new(mode, size, (30, 60, 90, 0) if mode == "RGBA" else (30, 60, 90))
    buffer = io.BytesIO()
    image.save(buffer, image_format, **save)
    return buffer.getvalue()


async def profile(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/api/v1/me/profile", headers=headers)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def upload(client: AsyncClient, headers: dict[str, str], data: bytes, name: str = "foto.jpg"):  # type: ignore[no-untyped-def]
    return await client.put(
        "/api/v1/me/photo", headers=headers, files={"file": (name, data, "image/jpeg")}
    )


async def consents(db: AsyncSession) -> list[tuple[str, bool]]:
    rows = await db.execute(
        select(ConsentRecord.purpose, ConsentRecord.granted).order_by(
            ConsentRecord.recorded_at, ConsentRecord.id
        )
    )
    return [(purpose.value, granted) for purpose, granted in rows]


async def test_profile_defaults_are_the_most_private(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    body = await profile(client, headers)
    assert body["email"] == "aysel.mammadova@smartazmiu.test"
    assert body["bio"] == ""
    assert body["photo_url"] is None
    assert body["dm_policy"] == "shared_context"
    assert body["contact_visibility"] == "hidden"
    assert body["version"] == 1


async def test_update_records_contact_consent(
    client: AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    first = await client.patch(
        "/api/v1/me/profile",
        headers=headers,
        json={
            "version": 1,
            "bio": "  İqtisadiyyat, 2-ci kurs. Statistika üzrə suallara kömək edə bilərəm.\n ",
            "dm_policy": "guides_and_teachers",
            "contact_visibility": "shared_context",
        },
    )
    assert first.status_code == 200
    assert (
        first.json()["bio"]
        == "İqtisadiyyat, 2-ci kurs. Statistika üzrə suallara kömək edə bilərəm."
    )
    assert first.json()["version"] == 2

    # The same visibility again records nothing; hiding the e-mail withdraws the consent.
    await client.patch(
        "/api/v1/me/profile",
        headers=headers,
        json={"version": 2, "contact_visibility": "shared_context", "dm_policy": "nobody"},
    )
    last = await client.patch(
        "/api/v1/me/profile", headers=headers, json={"version": 3, "contact_visibility": "hidden"}
    )

    assert last.json()["dm_policy"] == "nobody"
    assert last.json()["version"] == 4
    assert await consents(db) == [("contact_sharing", True), ("contact_sharing", False)]


async def test_stale_edit_is_rejected(client: AsyncClient, headers: dict[str, str]) -> None:
    await client.patch("/api/v1/me/profile", headers=headers, json={"version": 1, "bio": "Bir"})
    stale = await client.patch(
        "/api/v1/me/profile", headers=headers, json={"version": 1, "bio": "İki"}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "profile.version_conflict"
    assert stale.json()["error"]["details"] == {"version": 2}
    assert (await profile(client, headers))["bio"] == "Bir"


@pytest.mark.parametrize(
    "body",
    [
        {"version": 1, "bio": "ə" * 301},
        {"version": 1, "bio": "Salam\u0007"},
        {"version": 1, "email": "x@smartazmiu.test"},
        {"version": 1, "dm_policy": "friends"},
        {"bio": "Salam"},
    ],
)
async def test_invalid_updates(
    client: AsyncClient, headers: dict[str, str], body: dict[str, Any]
) -> None:
    response = await client.patch("/api/v1/me/profile", headers=headers, json=body)
    assert response.status_code == 422


async def test_photo_is_re_encoded_without_metadata(
    client: AsyncClient, headers: dict[str, str], storage: MemoryStorage, db: AsyncSession
) -> None:
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (40.0, 22.0, 0.0)}  # GPS position of the camera
    exif[0x0112] = 6  # rotate 90° on display
    response = await upload(client, headers, image_bytes("JPEG", (800, 600), exif=exif.tobytes()))

    assert response.status_code == 200
    body = response.json()
    assert body["photo_url"].startswith(f"/api/v1/users/{body['id']}/photo?v=")
    [(stored, content_type)] = storage.objects.values()
    assert content_type == "image/webp"
    with Image.open(io.BytesIO(stored)) as image:
        assert (image.format, image.size) == ("WEBP", (512, 512))
        assert not image.getexif()
    assert await consents(db) == [("profile_photo", True)]

    served = await client.get(body["photo_url"], headers=headers)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert served.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert served.content == stored
    me = await client.get("/api/v1/me", headers=headers)
    assert me.json()["photo_url"] == body["photo_url"]


async def test_new_photo_replaces_the_old_object(
    client: AsyncClient, headers: dict[str, str], storage: MemoryStorage
) -> None:
    first = (await upload(client, headers, image_bytes("PNG"), "a.png")).json()["photo_url"]
    second = (await upload(client, headers, image_bytes("WEBP"), "b.webp")).json()["photo_url"]
    assert first != second
    assert len(storage.objects) == 1


async def test_transparent_png_gets_a_white_background(
    client: AsyncClient, headers: dict[str, str], storage: MemoryStorage
) -> None:
    await upload(client, headers, image_bytes("PNG", (64, 64), "RGBA"), "logo.png")
    [(stored, _)] = storage.objects.values()
    with Image.open(io.BytesIO(stored)) as image:
        red, green, blue = image.convert("RGB").getpixel((256, 256))  # type: ignore[misc]
    assert min(red, green, blue) > 240


@pytest.mark.parametrize(
    ("data", "name"),
    [
        (b"university_id,family_name\n", "foto.jpg"),
        (image_bytes("GIF"), "animasiya.gif"),
        (image_bytes("JPEG")[:200], "kesik.jpg"),
    ],
)
async def test_invalid_photos_are_rejected(
    client: AsyncClient, headers: dict[str, str], storage: MemoryStorage, data: bytes, name: str
) -> None:
    response = await upload(client, headers, data, name)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "photo.invalid_image"
    assert storage.objects == {}


async def test_oversized_photos_are_rejected(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(photos, "MAX_PIXELS", 100)
    too_many_pixels = await upload(client, headers, image_bytes("PNG", (20, 20)), "a.png")
    assert too_many_pixels.json()["error"]["code"] == "photo.invalid_image"

    monkeypatch.setattr(users_router, "MAX_UPLOAD_BYTES", 10)
    too_large = await upload(client, headers, image_bytes("PNG", (8, 8)), "a.png")
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "photo.too_large"


async def test_storage_outage_leaves_the_profile_unchanged(
    client: AsyncClient, headers: dict[str, str], storage: MemoryStorage
) -> None:
    storage.available = False
    response = await upload(client, headers, image_bytes("JPEG"))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage.unavailable"
    assert (await profile(client, headers))["photo_url"] is None


async def test_removing_the_photo(
    client: AsyncClient, headers: dict[str, str], storage: MemoryStorage, db: AsyncSession
) -> None:
    url = (await upload(client, headers, image_bytes("JPEG"))).json()["photo_url"]
    removed = await client.delete("/api/v1/me/photo", headers=headers)
    again = await client.delete("/api/v1/me/photo", headers=headers)

    assert removed.json()["photo_url"] is None
    assert again.status_code == 200
    assert storage.objects == {}
    assert (await client.get(url, headers=headers)).status_code == 404
    assert await consents(db) == [("profile_photo", True), ("profile_photo", False)]


async def test_photos_need_a_signed_in_user_and_an_existing_photo(
    client: AsyncClient, headers: dict[str, str], tokens: TokenFactory
) -> None:
    url = (await upload(client, headers, image_bytes("JPEG"))).json()["photo_url"]
    classmate = {
        "Authorization": f"Bearer {tokens.issue(str(uuid.uuid4()), email='ramin.aliyev@smartazmiu.test')}"
    }
    assert (await client.get(url, headers=classmate)).status_code == 200
    assert (await client.get(url)).status_code == 401
    missing = await client.get(f"/api/v1/users/{uuid.uuid4()}/photo", headers=headers)
    assert missing.status_code == 404


async def test_photo_uploads_are_rate_limited(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(users_router, "PHOTO_UPLOADS", RateLimit(f"t{uuid.uuid4()}", 1, 60))
    assert (await upload(client, headers, image_bytes("JPEG"))).status_code == 200
    assert (await upload(client, headers, image_bytes("JPEG"))).status_code == 429
