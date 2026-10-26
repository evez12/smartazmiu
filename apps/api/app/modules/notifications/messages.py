"""Push and e-mail wording per notification kind, in Azerbaijani (the in-app text lives in the web app)."""

from dataclasses import dataclass

from app.modules.notifications.models import Notification, NotificationKind

KIND_LABELS: dict[NotificationKind, str] = {
    NotificationKind.ANNOUNCEMENT_PUBLISHED: "Yeni elan",
    NotificationKind.EVENT_PUBLISHED: "Yeni tədbir",
    NotificationKind.EVENT_CHANGED: "Tədbirdə dəyişiklik",
    NotificationKind.EVENT_CANCELLED: "Tədbir ləğv edildi",
    NotificationKind.SCHEDULE_CHANGED: "Dərs cədvəlində dəyişiklik",
    NotificationKind.CHAT_MENTION: "Sizi çatda qeyd etdilər",
    NotificationKind.CHAT_REPLY: "Mesajınıza cavab yazdılar",
    NotificationKind.CHAT_ATTACHMENT_REJECTED: "Fayl göstərilmir",
    NotificationKind.MATERIAL_VERSION_REJECTED: "Material versiyası qəbul olunmadı",
}


@dataclass(frozen=True, slots=True)
class Email:
    subject: str
    text: str


def push_payload(notification: Notification, url: str) -> dict[str, str]:
    # Lock screens show this text, so it carries no more than the in-app row does.
    return {
        "title": KIND_LABELS[notification.kind],
        "body": notification.title,
        "url": url,
        "tag": str(notification.id),
    }


def email(notification: Notification, recipient_name: str, url: str, settings_url: str) -> Email:
    label = KIND_LABELS[notification.kind]
    return Email(
        subject=f"{label}: {notification.title}",
        text=(
            f"Hörmətli {recipient_name},\n\n"
            f"{label}: {notification.title}\n\n"
            f"Ətraflı məlumat: {url}\n\n"
            "Bu məktub SmartAzMİU tərəfindən avtomatik göndərilib; cavab yazmağa ehtiyac yoxdur.\n"
            f"Bildiriş ayarlarınızı dəyişmək üçün: {settings_url}\n"
        ),
    )
