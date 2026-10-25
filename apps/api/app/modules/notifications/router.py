import uuid
from datetime import time
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.core.deps import RedisDep, SessionDep, SettingsDep
from app.core.errors import COMMON_ERROR_RESPONSES, AppError
from app.core.ratelimit import RateLimit, enforce_rate_limit
from app.core.rbac import CurrentUserDep
from app.modules.notifications.models import Notification, NotificationCategory
from app.modules.notifications.preferences import (
    Channels,
    NotificationSettings,
    Preferences,
    QuietWindow,
)
from app.modules.notifications.push import VapidKeys
from app.modules.notifications.schemas import (
    CategoryChannels,
    NotificationOut,
    NotificationPageOut,
    NotificationSettingsIn,
    NotificationSettingsOut,
    PushSubscriptionIn,
    QuietHoursIn,
    UnreadCountOut,
)
from app.modules.notifications.service import MAX_PAGE, Inbox

router = APIRouter(prefix="/me", tags=["notifications"], responses=COMMON_ERROR_RESPONSES)

PUSH_REGISTRATIONS = RateLimit("push_subscription", limit=30, window_seconds=3600)


def _out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=str(notification.id),
        category=notification.category,
        kind=notification.kind,
        title=notification.title,
        link=notification.link,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


def _clock(value: time) -> str:
    return f"{value:%H:%M}"


def _settings_out(
    settings: NotificationSettings, public_key: str | None
) -> NotificationSettingsOut:
    return NotificationSettingsOut(
        categories=[
            CategoryChannels(category=category, push=channels.push, email=channels.email)
            for category, channels in settings.channels.items()
        ],
        quiet_hours=QuietHoursIn(
            enabled=settings.quiet_hours.enabled,
            starts_at=_clock(settings.quiet_hours.starts_at),
            ends_at=_clock(settings.quiet_hours.ends_at),
        ),
        push_public_key=public_key,
        devices=settings.devices,
    )


@router.get(
    "/notifications",
    response_model=NotificationPageOut,
    operation_id="listMyNotifications",
    summary="My notifications, newest first",
)
async def list_my_notifications(
    user: CurrentUserDep,
    session: SessionDep,
    before: Annotated[uuid.UUID | None, Query(description="Cursor from `next_before`")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 20,
) -> NotificationPageOut:
    page = await Inbox(session, user.id).page(before, limit)
    return NotificationPageOut(
        items=[_out(item) for item in page.items],
        next_before=str(page.next_before) if page.next_before else None,
    )


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCountOut,
    operation_id="countMyUnreadNotifications",
    summary="Number of unread notifications (the bell badge)",
)
async def count_unread(user: CurrentUserDep, session: SessionDep) -> UnreadCountOut:
    return UnreadCountOut(count=await Inbox(session, user.id).unread_count())


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationOut,
    operation_id="markNotificationRead",
    summary="Mark one notification as read (idempotent)",
    responses={404: COMMON_ERROR_RESPONSES[403] | {"description": "Not one of my notifications"}},
)
async def mark_read(
    user: CurrentUserDep, session: SessionDep, notification_id: uuid.UUID
) -> NotificationOut:
    notification = await Inbox(session, user.id).mark_read(notification_id)
    if notification is None:
        raise AppError("request.not_found", 404)
    return _out(notification)


@router.post(
    "/notifications/read-all",
    response_model=UnreadCountOut,
    operation_id="markAllNotificationsRead",
    summary="Mark every notification as read; returns the remaining unread count (0)",
)
async def mark_all_read(user: CurrentUserDep, session: SessionDep) -> UnreadCountOut:
    inbox = Inbox(session, user.id)
    await inbox.mark_all_read()
    return UnreadCountOut(count=await inbox.unread_count())


def _public_key(settings: SettingsDep) -> str | None:
    if not settings.vapid_secret:
        return None
    return VapidKeys(settings.vapid_secret, settings.vapid_subject).public_key


@router.get(
    "/notification-settings",
    response_model=NotificationSettingsOut,
    operation_id="readMyNotificationSettings",
    summary="Channels per category, quiet hours and the push key",
)
async def read_settings(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep
) -> NotificationSettingsOut:
    return _settings_out(await Preferences(session, user.id).read(), _public_key(settings))


@router.put(
    "/notification-settings",
    response_model=NotificationSettingsOut,
    operation_id="updateMyNotificationSettings",
    summary="Replace channels per category and quiet hours",
)
async def update_settings(
    user: CurrentUserDep, session: SessionDep, settings: SettingsDep, body: NotificationSettingsIn
) -> NotificationSettingsOut:
    channels: dict[NotificationCategory, Channels] = {
        item.category: Channels(item.push, item.email) for item in body.categories
    }
    quiet = body.quiet_hours
    updated = await Preferences(session, user.id).update(
        channels,
        QuietWindow(
            quiet.enabled, time.fromisoformat(quiet.starts_at), time.fromisoformat(quiet.ends_at)
        ),
    )
    return _settings_out(updated, _public_key(settings))


@router.put(
    "/push-subscriptions",
    status_code=204,
    response_class=Response,
    operation_id="registerPushSubscription",
    summary="Register this browser for Web Push",
)
async def register_push_subscription(
    user: CurrentUserDep,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
    body: PushSubscriptionIn,
) -> Response:
    if not settings.vapid_secret:
        raise AppError("notifications.push_unavailable", 409)
    await enforce_rate_limit(redis, PUSH_REGISTRATIONS, str(user.id))
    await Preferences(session, user.id).subscribe(
        body.endpoint, body.keys.p256dh, body.keys.auth, settings.push_service_hosts
    )
    return Response(status_code=204)


@router.delete(
    "/push-subscriptions",
    status_code=204,
    response_class=Response,
    operation_id="removePushSubscription",
    summary="Stop Web Push for this browser",
)
async def remove_push_subscription(
    user: CurrentUserDep,
    session: SessionDep,
    endpoint: Annotated[str, Query(max_length=2000)],
) -> Response:
    await Preferences(session, user.id).unsubscribe(endpoint)
    return Response(status_code=204)
