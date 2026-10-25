import json
import uuid
from datetime import UTC, datetime, time, timedelta

import http_ece
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.modules.notifications.delivery import MAX_ATTEMPTS, Dispatcher
from app.modules.notifications.models import (
    DeliveryChannel,
    DeliveryStatus,
    NotificationCategory,
    NotificationDelivery,
    NotificationPreference,
    PushSubscription,
    QuietHours,
)
from app.modules.notifications.preferences import QuietWindow
from app.modules.notifications.push import (
    PushOutcome,
    PushTarget,
    VapidKeys,
    WebPushSender,
    allowed_endpoint,
    b64url,
    b64url_decode,
)
from app.modules.notifications.tests.conftest import (
    FakePush,
    MakeUser,
    MemoryMailer,
    notify,
    spec,
)
from app.modules.users.models import User, UserStatus

# 10:00 in Baku, outside the default quiet hours.
MORNING = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
FCM = "https://fcm.googleapis.com/fcm/send/abc"


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class Relevance:
    def __init__(self) -> None:
        self.relevant = True
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def __call__(self, session: AsyncSession, subject: uuid.UUID, user: uuid.UUID) -> bool:
        self.calls.append((subject, user))
        return self.relevant


@pytest.fixture
def clock() -> Clock:
    return Clock(MORNING)


@pytest.fixture
def push() -> FakePush:
    return FakePush()


@pytest.fixture
def mailer() -> MemoryMailer:
    return MemoryMailer()


@pytest.fixture
def relevance() -> Relevance:
    return Relevance()


@pytest.fixture
def dispatcher(
    engine: AsyncEngine, push: FakePush, mailer: MemoryMailer, relevance: Relevance, clock: Clock
) -> Dispatcher:
    return Dispatcher(
        async_sessionmaker(engine, expire_on_commit=False),
        push=push,
        mailer=mailer,
        relevance={"announcement": relevance},
        public_url="https://smartazmiu.test/",
        clock=clock,
    )


def point(key: ec.EllipticCurvePrivateKey) -> bytes:
    """The uncompressed P-256 point a browser sends as ``p256dh``."""
    numbers = key.public_key().public_numbers()
    return bytes([4]) + numbers.x.to_bytes(32) + numbers.y.to_bytes(32)


async def statuses(db: AsyncSession) -> dict[DeliveryChannel, tuple[DeliveryStatus, str | None]]:
    rows = await db.scalars(select(NotificationDelivery).execution_options(populate_existing=True))
    return {row.channel: (row.status, row.reason) for row in rows}


async def subscribe(db: AsyncSession, user: User, endpoint: str = FCM) -> None:
    db.add(PushSubscription(user_id=user.id, endpoint=endpoint, p256dh="key", auth="secret"))
    await db.commit()


async def test_sends_push_and_email_with_links(
    db: AsyncSession,
    make_user: MakeUser,
    dispatcher: Dispatcher,
    push: FakePush,
    mailer: MemoryMailer,
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    await subscribe(db, aysel)
    announcement = spec()
    await notify(db, [aysel], announcement)

    assert await dispatcher.run() == 2
    assert await statuses(db) == {
        DeliveryChannel.PUSH: (DeliveryStatus.SENT, None),
        DeliveryChannel.EMAIL: (DeliveryStatus.SENT, None),
    }
    payload = json.loads(push.sent[0][1])
    assert payload["title"] == "Yeni elan"
    assert payload["body"] == announcement.title
    assert payload["url"] == f"https://smartazmiu.test{announcement.link}"
    to, subject, text = mailer.sent[0]
    assert to == "aysel.mammadova@smartazmiu.test"
    assert subject == f"Yeni elan: {announcement.title}"
    assert "Hörmətli Aysel Məmmədova," in text
    assert "https://smartazmiu.test/notifications/settings" in text
    # Nothing is due any more: a second run (a retried job) sends nothing again.
    assert await dispatcher.run() == 0
    assert len(push.sent) == 1


async def test_quiet_hours_suppress_push_but_not_email(
    db: AsyncSession,
    make_user: MakeUser,
    dispatcher: Dispatcher,
    clock: Clock,
    mailer: MemoryMailer,
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    await subscribe(db, aysel)
    await notify(db, [aysel], spec())
    clock.now = datetime(2026, 11, 2, 19, 30, tzinfo=UTC)  # 23:30 in Baku

    await dispatcher.run()
    assert (await statuses(db))[DeliveryChannel.PUSH] == (DeliveryStatus.SUPPRESSED, "quiet_hours")
    assert (await statuses(db))[DeliveryChannel.EMAIL] == (DeliveryStatus.SENT, None)
    assert len(mailer.sent) == 1


async def test_preferences_and_membership_are_checked_when_sending(
    db: AsyncSession,
    make_user: MakeUser,
    dispatcher: Dispatcher,
    relevance: Relevance,
    push: FakePush,
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    ramin = await make_user("Ramin", "Əliyev", "ramin.aliyev@smartazmiu.test")
    await subscribe(db, aysel)
    await notify(db, [aysel], spec())
    # Switched off after the notification was created: the stored delivery is not sent.
    db.add(
        NotificationPreference(
            user_id=aysel.id, category=NotificationCategory.ANNOUNCEMENTS, push=False, email=True
        )
    )
    await db.commit()
    await dispatcher.run()
    assert (await statuses(db))[DeliveryChannel.PUSH] == (
        DeliveryStatus.SUPPRESSED,
        "preference_off",
    )
    assert push.sent == []

    # Left the audience (e.g. transferred to another group) before the worker got to it.
    await db.execute(delete(NotificationDelivery))
    await notify(db, [ramin], spec())
    relevance.relevant = False
    await dispatcher.run()
    assert set((await statuses(db)).values()) == {(DeliveryStatus.SUPPRESSED, "not_relevant")}
    assert relevance.calls
    assert relevance.calls[-1][1] == ramin.id


async def test_inactive_accounts_and_missing_devices_or_addresses(
    db: AsyncSession, make_user: MakeUser, dispatcher: Dispatcher
) -> None:
    leyla = await make_user("Leyla", "Həsənova", None)
    await notify(db, [leyla], spec())
    await dispatcher.run()
    assert await statuses(db) == {
        DeliveryChannel.PUSH: (DeliveryStatus.SUPPRESSED, "no_device"),
        DeliveryChannel.EMAIL: (DeliveryStatus.SUPPRESSED, "no_address"),
    }

    await db.execute(delete(NotificationDelivery))
    orxan = await make_user("Orxan", "Rzayev", "orxan.rzayev@smartazmiu.test")
    await notify(db, [orxan], spec())
    orxan.status = UserStatus.INACTIVE
    await db.commit()
    await dispatcher.run()
    assert set((await statuses(db)).values()) == {(DeliveryStatus.SUPPRESSED, "inactive")}


async def test_expired_subscriptions_are_removed(
    db: AsyncSession, make_user: MakeUser, dispatcher: Dispatcher, push: FakePush
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    await subscribe(db, aysel)
    await notify(db, [aysel], spec())
    push.outcome = PushOutcome.GONE
    await dispatcher.run()
    assert (await statuses(db))[DeliveryChannel.PUSH] == (DeliveryStatus.SUPPRESSED, "no_device")
    assert list(await db.scalars(select(PushSubscription))) == []


async def test_failures_are_retried_with_backoff_then_given_up(
    db: AsyncSession,
    make_user: MakeUser,
    dispatcher: Dispatcher,
    mailer: MemoryMailer,
    clock: Clock,
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    db.add(
        NotificationPreference(
            user_id=aysel.id, category=NotificationCategory.ANNOUNCEMENTS, push=False, email=True
        )
    )
    await db.commit()
    await notify(db, [aysel], spec())
    mailer.available = False

    await dispatcher.run()
    email = await db.scalar(
        select(NotificationDelivery)
        .where(NotificationDelivery.channel == DeliveryChannel.EMAIL)
        .execution_options(populate_existing=True)
    )
    assert email is not None
    assert (email.status, email.attempts) == (DeliveryStatus.PENDING, 1)
    assert email.not_before == MORNING + timedelta(minutes=2)
    # Not due yet: nothing happens until the backoff has passed.
    assert await dispatcher.run() == 0

    for _ in range(MAX_ATTEMPTS):
        clock.now += timedelta(hours=1)
        await dispatcher.run()
    email = await db.get(NotificationDelivery, email.id, populate_existing=True)
    assert email is not None
    assert (email.status, email.reason, email.attempts) == (
        DeliveryStatus.FAILED,
        "gave_up",
        MAX_ATTEMPTS,
    )


async def test_stored_quiet_hours_apply(
    db: AsyncSession, make_user: MakeUser, dispatcher: Dispatcher, clock: Clock
) -> None:
    aysel = await make_user("Aysel", "Məmmədova", "aysel.mammadova@smartazmiu.test")
    await subscribe(db, aysel)
    db.add(QuietHours(user_id=aysel.id, enabled=True, starts_at=time(9, 0), ends_at=time(11, 0)))
    await db.commit()
    await notify(db, [aysel], spec())
    await dispatcher.run()  # 10:00 in Baku
    assert (await statuses(db))[DeliveryChannel.PUSH] == (DeliveryStatus.SUPPRESSED, "quiet_hours")


@pytest.mark.parametrize(
    ("window", "baku", "covered"),
    [
        (QuietWindow(True, time(23, 0), time(8, 0)), "23:00", True),
        (QuietWindow(True, time(23, 0), time(8, 0)), "03:15", True),
        (QuietWindow(True, time(23, 0), time(8, 0)), "08:00", False),
        (QuietWindow(True, time(23, 0), time(8, 0)), "22:59", False),
        (QuietWindow(True, time(13, 0), time(14, 0)), "13:30", True),
        (QuietWindow(True, time(13, 0), time(14, 0)), "14:00", False),
        (QuietWindow(False, time(23, 0), time(8, 0)), "02:00", False),
    ],
)
def test_quiet_window_in_baku_time(window: QuietWindow, baku: str, covered: bool) -> None:
    hour, minute = map(int, baku.split(":"))
    moment = datetime(2026, 11, 2, hour, minute, tzinfo=UTC) - timedelta(hours=4)
    assert window.covers(moment) is covered


def test_endpoint_allowlist() -> None:
    hosts = Settings().push_service_hosts
    assert allowed_endpoint("https://fcm.googleapis.com/fcm/send/x", hosts)
    assert allowed_endpoint("https://wns2-am3p.notify.windows.com/w/?token=x", hosts)
    assert not allowed_endpoint("https://notify.windows.com.example/w", hosts)
    assert not allowed_endpoint("https://localhost/push", hosts)
    assert not allowed_endpoint("ftp://fcm.googleapis.com/x", hosts)


async def test_web_push_message_decrypts_with_the_reference_implementation() -> None:
    """RFC 8291 encryption checked against ``http_ece``, and the VAPID token against our public key."""
    browser = ec.generate_private_key(ec.SECP256R1())
    browser_public = point(browser)
    auth_secret = b"0123456789abcdef"
    captured: list[httpx.Request] = []

    def service(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(201)

    keys = VapidKeys("test-vapid-secret", "mailto:it@smartazmiu.test")
    async with httpx.AsyncClient(transport=httpx.MockTransport(service)) as http:
        sender = WebPushSender(http, keys, ["fcm.googleapis.com"])
        target = PushTarget(FCM, b64url(browser_public), b64url(auth_secret))
        payload = json.dumps({"title": "Yeni elan", "body": "Şənbə günü dərs olmayacaq"}).encode()
        assert await sender.send(target, payload, 3600) is PushOutcome.SENT

    request = captured[0]
    assert request.headers["Content-Encoding"] == "aes128gcm"
    assert request.headers["TTL"] == "3600"
    plain = http_ece.decrypt(
        request.content, private_key=browser, dh=None, auth_secret=auth_secret, version="aes128gcm"
    )
    assert plain == payload

    scheme, _, credentials = request.headers["Authorization"].partition(" ")
    assert scheme == "vapid"
    fields = dict(part.strip().split("=", 1) for part in credentials.split(","))
    assert fields["k"] == keys.public_key
    public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), b64url_decode(fields["k"])
    )
    claims = jwt.decode(
        fields["t"], public, algorithms=["ES256"], audience="https://fcm.googleapis.com"
    )
    assert claims["sub"] == "mailto:it@smartazmiu.test"
    # The key pair is stable for a secret, so existing browser subscriptions keep working after restarts.
    assert VapidKeys("test-vapid-secret", "mailto:x@y.z").public_key == keys.public_key
    assert VapidKeys("another-secret", "mailto:x@y.z").public_key != keys.public_key


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (410, PushOutcome.GONE),
        (404, PushOutcome.GONE),
        (429, PushOutcome.RETRY),
        (503, PushOutcome.RETRY),
    ],
)
async def test_push_service_answers(status: int, outcome: PushOutcome) -> None:
    browser = ec.generate_private_key(ec.SECP256R1())
    transport = httpx.MockTransport(lambda request: httpx.Response(status))
    async with httpx.AsyncClient(transport=transport) as http:
        sender = WebPushSender(http, VapidKeys("s", "mailto:a@b.c"), ["fcm.googleapis.com"])
        target = PushTarget(FCM, b64url(point(browser)), b64url(b"0123456789abcdef"))
        assert await sender.send(target, b"{}", 60) is outcome
        # Garbage keys from a browser, or an endpoint off the allowlist, never reach the network.
        assert await sender.send(PushTarget(FCM, "AAAA", "AAAA"), b"{}", 60) is PushOutcome.GONE
        evil = PushTarget("https://10.0.0.5/push", target.p256dh, target.auth)
        assert await sender.send(evil, b"{}", 60) is PushOutcome.GONE
