import datetime as dt
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.modules.notifications.models import NotificationCategory, NotificationKind

Base64Url = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+={0,2}$")]
ClockTime = Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$", examples=["23:00"])]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class NotificationOut(_Frozen):
    id: str
    category: NotificationCategory
    kind: NotificationKind
    title: str
    link: str
    """Path inside the app."""
    created_at: dt.datetime
    read_at: dt.datetime | None


class NotificationPageOut(_Frozen):
    items: list[NotificationOut]
    next_before: str | None
    """Cursor for the next (older) page; null on the last page."""


class UnreadCountOut(_Frozen):
    count: int


class CategoryChannels(_Frozen):
    category: NotificationCategory
    push: bool
    email: bool


class QuietHoursIn(_Frozen):
    enabled: bool
    starts_at: ClockTime
    """Baku time, ``HH:MM``."""
    ends_at: ClockTime


class NotificationSettingsIn(_Frozen):
    categories: list[CategoryChannels] = Field(max_length=len(NotificationCategory))
    quiet_hours: QuietHoursIn


class NotificationSettingsOut(_Frozen):
    categories: list[CategoryChannels]
    quiet_hours: QuietHoursIn
    push_public_key: str | None
    """VAPID application server key for ``PushManager.subscribe``; null when push is not configured."""
    devices: int
    """Browsers registered for push."""


class PushKeys(_Frozen):
    p256dh: Base64Url = Field(max_length=100)
    auth: Base64Url = Field(max_length=50)


class PushSubscriptionIn(_Frozen):
    endpoint: str = Field(max_length=2000)
    keys: PushKeys
