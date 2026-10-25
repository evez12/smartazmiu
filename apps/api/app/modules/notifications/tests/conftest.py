import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.mail import MailUnavailableError
from app.modules.notifications.models import NotificationCategory, NotificationKind
from app.modules.notifications.push import PushOutcome, PushTarget
from app.modules.notifications.service import NotificationSpec, Notifier
from app.modules.users.models import User
from tests.support import TokenFactory

MakeUser = Callable[..., Awaitable[User]]


@pytest.fixture
def make_user(db: AsyncSession) -> MakeUser:
    async def create(given: str, family: str, email: str | None = None, **fields: object) -> User:
        user = User(
            given_name=given,
            family_name=family,
            display_name=f"{given} {family}",
            email=email,
            idp_subject=str(uuid.uuid4()),
            **fields,
        )
        db.add(user)
        await db.commit()
        return user

    return create


def spec(subject_id: uuid.UUID | None = None, **overrides: object) -> NotificationSpec:
    subject = subject_id or uuid.uuid4()
    values: dict[str, object] = {
        "category": NotificationCategory.ANNOUNCEMENTS,
        "kind": NotificationKind.ANNOUNCEMENT_PUBLISHED,
        "subject_type": "announcement",
        "subject_id": subject,
        "dedupe_key": f"announcement:{subject}",
        "title": "Qış imtahan sessiyasının cədvəli dərc olundu",
        "link": f"/announcements/{subject}",
    }
    values.update(overrides)
    return NotificationSpec(**values)  # type: ignore[arg-type]


async def notify(db: AsyncSession, users: list[User], notification: NotificationSpec) -> int:
    ids = [user.id for user in users]
    created = await Notifier(db).notify(select(User.id).where(User.id.in_(ids)), notification)
    await db.commit()
    return created


def headers_for(tokens: TokenFactory, user: User) -> dict[str, str]:
    token = tokens.issue(
        user.idp_subject,
        ["student"],
        given_name=user.given_name,
        family_name=user.family_name,
        email=user.email,
    )
    return {"Authorization": f"Bearer {token}"}


@dataclass
class FakePush:
    outcome: PushOutcome = PushOutcome.SENT
    sent: list[tuple[PushTarget, bytes]] = field(default_factory=list)

    async def send(self, target: PushTarget, payload: bytes, ttl_seconds: int) -> PushOutcome:
        self.sent.append((target, payload))
        return self.outcome


@dataclass
class MemoryMailer:
    available: bool = True
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    async def send(self, to: str, subject: str, text: str) -> None:
        if not self.available:
            raise MailUnavailableError("down")
        self.sent.append((to, subject, text))
