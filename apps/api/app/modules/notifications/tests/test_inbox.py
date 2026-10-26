from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import (
    DeliveryChannel,
    Notification,
    NotificationCategory,
    NotificationDelivery,
    NotificationKind,
    NotificationPreference,
    PushSubscription,
)
from app.modules.notifications.tests.conftest import MakeUser, headers_for, notify, spec
from tests.support import TokenFactory

FCM = "https://fcm.googleapis.com/fcm/send/dJ8kZ1qXm"
KEYS = {
    "p256dh": "BOr4T0Pm2M6Bx4pV4W6e0D0Zb0Ojq5yZbqv8XcWl0J3oGx0Kx7Q0n1pYw8mX2fH3q3m6V8k7s1d0a9c8b7e6f5g",
    "auth": "k9Q2xV7mL1pR4tY6uW8zAa",
}


async def deliveries(db: AsyncSession) -> set[tuple[str, DeliveryChannel]]:
    rows = await db.execute(
        select(Notification.title, NotificationDelivery.channel).join(
            Notification, Notification.id == NotificationDelivery.notification_id
        )
    )
    return {(title, channel) for title, channel in rows}


async def test_fan_out_is_deduplicated_and_follows_channel_preferences(
    db: AsyncSession, make_user: MakeUser
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    ramin = await make_user("Ramin", "Əliyev", "ramin.aliyev@smartazmiu.test")
    db.add(
        NotificationPreference(
            user_id=ramin.id, category=NotificationCategory.ANNOUNCEMENTS, push=False, email=False
        )
    )
    await db.commit()
    announcement = spec()

    assert await notify(db, [aysel, ramin], announcement) == 2
    # The same event again (a retried job, a re-run sync) notifies nobody twice (§5.6).
    assert await notify(db, [aysel, ramin], announcement) == 0
    assert await db.scalar(select(func.count()).select_from(Notification)) == 2

    # Announcements default to push and e-mail; Ramin switched both off, so he gets the bell only.
    owners = await db.execute(
        select(Notification.user_id, NotificationDelivery.channel).join(
            Notification, Notification.id == NotificationDelivery.notification_id
        )
    )
    assert set(owners) == {
        (aysel.id, DeliveryChannel.PUSH),
        (aysel.id, DeliveryChannel.EMAIL),
    }

    # Events default to push only.
    event = spec(
        category=NotificationCategory.EVENTS,
        kind=NotificationKind.EVENT_PUBLISHED,
        subject_type="event",
        title="Kitab sərgisi",
    )
    await notify(db, [aysel], event)
    assert ("Kitab sərgisi", DeliveryChannel.PUSH) in await deliveries(db)
    assert ("Kitab sərgisi", DeliveryChannel.EMAIL) not in await deliveries(db)


async def test_inbox_pages_counts_and_marks_read(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser, tokens: TokenFactory
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    ramin = await make_user("Ramin", "Əliyev", "ramin.aliyev@smartazmiu.test")
    for number in range(5):
        await notify(db, [aysel], spec(title=f"Elan {number}"))
    await notify(db, [ramin], spec(title="Raminin elanı"))
    headers = headers_for(tokens, aysel)

    first = (await client.get("/api/v1/me/notifications?limit=3", headers=headers)).json()
    assert [item["title"] for item in first["items"]] == ["Elan 4", "Elan 3", "Elan 2"]
    assert first["items"][0]["kind"] == "announcement.published"
    second = (
        await client.get(
            f"/api/v1/me/notifications?limit=3&before={first['next_before']}", headers=headers
        )
    ).json()
    assert [item["title"] for item in second["items"]] == ["Elan 1", "Elan 0"]
    assert second["next_before"] is None

    count = await client.get("/api/v1/me/notifications/unread-count", headers=headers)
    assert count.json() == {"count": 5}
    newest = first["items"][0]["id"]
    read = await client.post(f"/api/v1/me/notifications/{newest}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    again = await client.post(f"/api/v1/me/notifications/{newest}/read", headers=headers)
    assert again.json()["read_at"] == read.json()["read_at"]
    assert (await client.get("/api/v1/me/notifications/unread-count", headers=headers)).json() == {
        "count": 4
    }

    # Someone else's notification is not found, and never listed.
    other = await db.scalar(select(Notification.id).where(Notification.user_id == ramin.id))
    missing = await client.post(f"/api/v1/me/notifications/{other}/read", headers=headers)
    assert missing.status_code == 404
    titles = {item["title"] for item in first["items"] + second["items"]}
    assert "Raminin elanı" not in titles

    everything = await client.post("/api/v1/me/notifications/read-all", headers=headers)
    assert everything.json() == {"count": 0}
    assert (
        await db.scalar(
            select(func.count()).select_from(Notification).where(Notification.read_at.is_(None))
        )
        == 1
    )


async def test_settings_default_update_and_validate(
    client: AsyncClient, make_user: MakeUser, tokens: TokenFactory
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    headers = headers_for(tokens, aysel)

    defaults = (await client.get("/api/v1/me/notification-settings", headers=headers)).json()
    assert defaults["quiet_hours"] == {"enabled": True, "starts_at": "23:00", "ends_at": "08:00"}
    assert {c["category"]: (c["push"], c["email"]) for c in defaults["categories"]} == {
        "announcements": (True, True),
        "events": (True, False),
        "schedule": (True, False),
        "chat": (True, False),
    }
    assert defaults["push_public_key"].startswith("B")
    assert defaults["devices"] == 0

    body = {
        "categories": [
            {"category": "announcements", "push": False, "email": True},
            {"category": "chat", "push": False, "email": True},
        ],
        "quiet_hours": {"enabled": True, "starts_at": "22:30", "ends_at": "07:15"},
    }
    updated = await client.put("/api/v1/me/notification-settings", json=body, headers=headers)
    assert updated.status_code == 200, updated.text
    settings = updated.json()
    assert settings["quiet_hours"] == body["quiet_hours"]
    assert {"category": "announcements", "push": False, "email": True} in settings["categories"]
    assert {"category": "events", "push": True, "email": False} in settings["categories"]
    # Chat has no e-mail until the digest exists (D-067).
    assert {"category": "chat", "push": False, "email": False} in settings["categories"]

    empty = {**body, "quiet_hours": {"enabled": True, "starts_at": "22:00", "ends_at": "22:00"}}
    rejected = await client.put("/api/v1/me/notification-settings", json=empty, headers=headers)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "notifications.quiet_hours_empty"
    malformed = {**body, "quiet_hours": {"enabled": True, "starts_at": "24:00", "ends_at": "8"}}
    invalid = await client.put("/api/v1/me/notification-settings", json=malformed, headers=headers)
    assert invalid.status_code == 422


async def test_push_subscriptions_are_limited_to_known_push_services(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser, tokens: TokenFactory
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    ramin = await make_user("Ramin", "Əliyev", "ramin.aliyev@smartazmiu.test")
    headers = headers_for(tokens, aysel)

    # The worker posts to this URL, so internal or plain-HTTP addresses are refused (SSRF, §14).
    for endpoint in (
        "http://fcm.googleapis.com/fcm/send/x",
        "https://169.254.169.254/latest/meta-data",
        "https://fcm.googleapis.com.evil.example/x",
        "https://user:pass@fcm.googleapis.com/x",
    ):
        response = await client.put(
            "/api/v1/me/push-subscriptions",
            json={"endpoint": endpoint, "keys": KEYS},
            headers=headers,
        )
        assert response.status_code == 422, endpoint
        assert response.json()["error"]["code"] == "notifications.push_endpoint_rejected"

    mozilla = "https://updates.push.services.mozilla.com/wpush/v2/gAAAA"
    for endpoint in (FCM, mozilla, FCM):
        response = await client.put(
            "/api/v1/me/push-subscriptions",
            json={"endpoint": endpoint, "keys": KEYS},
            headers=headers,
        )
        assert response.status_code == 204
    settings = (await client.get("/api/v1/me/notification-settings", headers=headers)).json()
    assert settings["devices"] == 2

    # A browser profile now used by someone else moves to them; it never notifies both.
    await client.put(
        "/api/v1/me/push-subscriptions",
        json={"endpoint": FCM, "keys": KEYS},
        headers=headers_for(tokens, ramin),
    )
    owner = await db.scalar(
        select(PushSubscription.user_id).where(PushSubscription.endpoint == FCM)
    )
    assert owner == ramin.id

    removed = await client.delete(
        "/api/v1/me/push-subscriptions", params={"endpoint": mozilla}, headers=headers
    )
    assert removed.status_code == 204
    assert (await client.get("/api/v1/me/notification-settings", headers=headers)).json()[
        "devices"
    ] == 0


async def test_older_devices_are_dropped_beyond_ten(
    client: AsyncClient, db: AsyncSession, make_user: MakeUser, tokens: TokenFactory
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    headers = headers_for(tokens, aysel)
    for number in range(12):
        await client.put(
            "/api/v1/me/push-subscriptions",
            json={"endpoint": f"{FCM}{number}", "keys": KEYS},
            headers=headers,
        )
    endpoints = set(await db.scalars(select(PushSubscription.endpoint)))
    assert len(endpoints) == 10
    assert f"{FCM}0" not in endpoints
    assert f"{FCM}11" in endpoints


async def test_notification_endpoints_require_sign_in(client: AsyncClient) -> None:
    for path in ("/api/v1/me/notifications", "/api/v1/me/notification-settings"):
        assert (await client.get(path)).status_code == 401
